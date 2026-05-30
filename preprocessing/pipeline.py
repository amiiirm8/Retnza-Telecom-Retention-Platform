"""Task 2: canonical cleaned dataset (standardized business layer only).

Pipeline position:
  Entry point for preprocessing. Orchestrates raw CSV loading, column
  renaming, categorical mapping, target encoding, QC flag addition,
  validation, and parquet output.

Workflow stage:
  **Training** — produces the one canonical cleaned frame that all
  downstream modeling pipelines consume. Also usable during inference
  with the same transforms (no fit step).

Key invariants:
  - No winsorization, no sklearn fit, no model features, no spend imputation.
  - All Persian tokens are mapped to English canonical values.
  - QC/operational flags are added but never modify observed spend.
  - The validation policy is configurable but defaults to strict (fail-fast).
  - Output parquet uses deterministic column order (CLEANED_COLUMN_ORDER).
  - A preprocessing manifest is written alongside the cleaned data for audit.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from preprocessing.config import (
    APP_PERSIAN_TO_ENGLISH,
    CLEANED_DIR,
    CLEANED_DTYPE_CONTRACT,
    COLUMN_RENAME,
    DEFAULT_RAW_CSV,
    GENDER_MAP,
    RAW_DIR,
    SCHEMA_VERSION,
    SIM_TYPE_MAP,
    TARGET_MAP,
    TRI_PERSIAN_TO_ENGLISH,
    TRI_STATE_COLUMNS,
)
from preprocessing.labels import dumps_display_label_bundle
from preprocessing.qc import QCReporter
from preprocessing.text import normalize_column_name, normalize_series_tokens
from preprocessing.validators import (
    ValidationPolicy,
    ValidationReport,
    apply_duplicate_subscriber_policy,
    validate_cleaned_frame,
    validate_mapped_categoricals,
    validate_raw_schema,
)
import time

logger = logging.getLogger(__name__)

CLEANED_MANIFEST_PATH = CLEANED_DIR / "preprocessing_manifest.json"
DISPLAY_LABELS_PATH = CLEANED_DIR / "display_labels.json"

CLEANED_COLUMN_SCHEMA: list[dict[str, str]] = [
    # Identifier column — not a feature.
    {"name": "subscriber_id", "role": "id", "dtype": "int64"},
    # Categorical features.
    {"name": "gender", "role": "feature", "dtype": "string", "values": "male|female"},
    {"name": "age", "role": "feature", "dtype": "int64"},
    {
        "name": "birth_month_persian",
        "role": "feature",
        "dtype": "string",
        "note": "Persian month retained for BI; ordinal only in modeling",
    },
    {"name": "sim_tenure_months", "role": "feature", "dtype": "int64"},
    {"name": "mobile_data_generation", "role": "feature", "dtype": "string", "values": "2G|3G|4G|5G"},
    # Tri-state VAS/data columns.
    {"name": "intl_roaming_package", "role": "feature", "dtype": "tri_state"},
    {"name": "operator_cloud_storage", "role": "feature", "dtype": "tri_state"},
    {"name": "night_data_package", "role": "feature", "dtype": "tri_state"},
    {"name": "volte_service", "role": "feature", "dtype": "tri_state"},
    {"name": "superapp_social", "role": "feature", "dtype": "tri_state"},
    {"name": "superapp_financial", "role": "feature", "dtype": "tri_state"},
    # Binary categorical features.
    {"name": "sim_card_type", "role": "feature", "dtype": "string", "values": "prepaid|postpaid"},
    {"name": "operator_app_usage", "role": "feature", "dtype": "string", "values": "yes|no"},
    # Numeric spend features — intentionally not imputed or winsorized.
    {"name": "monthly_spend_toman", "role": "feature", "dtype": "int64"},
    {"name": "cumulative_spend_toman", "role": "feature", "dtype": "int64"},
    # QC / operational flags.
    {"name": "tenure_zero_flag", "role": "qc_flag", "dtype": "int8"},
    {"name": "billing_definition_ambiguous_flag", "role": "qc_flag", "dtype": "int8"},
    {"name": "is_data_capable", "role": "operational_flag", "dtype": "int8"},
    # Target variable for modeling.
    {"name": "churn_binary", "role": "target", "dtype": "int8"},
]

CLEANED_COLUMN_ORDER: list[str] = [c["name"] for c in CLEANED_COLUMN_SCHEMA]
"""Deterministic column ordering enforced on the cleaned parquet output."""


def _map_normalized_tokens(series: pd.Series, lookup: dict[str, str]) -> pd.Series:
    """Map a series of Persian/normalized tokens to English canonicals.

    Args:
        series: Column values that may contain Unicode variant characters.
        lookup: Dict of normalized_key -> canonical_value (built via
            build_normalized_lookup).

    Returns:
        Series with values replaced by canonical English tokens.
        Missing keys produce NaN (caught by validation later).
    """
    return normalize_series_tokens(series).map(lookup)


def load_raw_csv(path: Path) -> pd.DataFrame:
    """Load the raw Persian CSV and normalize its column headers.

    The raw CSV uses Persian column names with potential Unicode variants
    (ZWNJ, Arabic letter forms). All headers are normalized via
    normalize_column_name for reliable matching against COLUMN_RENAME.

    Args:
        path: Path to the raw UTF-8 CSV file.

    Returns:
        DataFrame with normalized column names.

    Raises:
        FileNotFoundError: If the CSV does not exist (deferred to caller).
        pd.errors.EmptyDataError: If the file is empty.
    """
    df = pd.read_csv(path, encoding="utf-8")
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Persian headers to canonical English snake_case.

    Uses COLUMN_RENAME with normalized keys for tolerant matching.

    Args:
        df: DataFrame with normalized Persian column headers.

    Returns:
        DataFrame with English column names. Unrecognized columns are
        silently dropped from the rename (they retain their original name).
    """
    ren = {normalize_column_name(k): v for k, v in COLUMN_RENAME.items()}
    return df.rename(columns=ren)


def map_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Map Persian categorical tokens to English canonical values.

    Applies the lookup maps defined in config.py. Tri-state columns
    (intl_roaming_package, operator_cloud_storage, etc.) preserve the
    'yes' / 'no' / 'no_data_service' semantics from the raw data.
    mobile_data_generation is uppercased for consistency (raw values
    may be mixed-case like "4g" vs "4G").

    Args:
        df: DataFrame with English column names (post-rename).

    Returns:
        DataFrame with all categorical columns in English canonical form.
    """
    out = df.copy()
    out["gender"] = _map_normalized_tokens(out["gender"], GENDER_MAP)
    out["sim_card_type"] = _map_normalized_tokens(out["sim_card_type"], SIM_TYPE_MAP)
    for col in TRI_STATE_COLUMNS:
        out[col] = _map_normalized_tokens(out[col], TRI_PERSIAN_TO_ENGLISH)
    out["operator_app_usage"] = _map_normalized_tokens(
        out["operator_app_usage"], APP_PERSIAN_TO_ENGLISH
    )
    out["mobile_data_generation"] = (
        normalize_series_tokens(out["mobile_data_generation"]).str.upper()
    )
    return out


def encode_target(df: pd.DataFrame) -> pd.DataFrame:
    """Encode the churn_label column to binary int8 (churn_binary).

    Drops the original Persian churn_label column after encoding.

    Args:
        df: DataFrame containing the raw 'churn_label' column.

    Returns:
        DataFrame with 'churn_binary' (int8: 0=stayed, 1=churned) and
        without the original 'churn_label' column.
    """
    out = df.copy()
    out["churn_binary"] = (
        normalize_series_tokens(out["churn_label"]).map(TARGET_MAP).astype("int8")
    )
    return out.drop(columns=["churn_label"])


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add minimal operational/QC flags — never alter observed spend.

    Three flags are computed:
      - tenure_zero_flag: 1 if sim_tenure_months == 0.
      - billing_definition_ambiguous_flag: 1 if tenure=0, cumulative=0,
        and monthly>0 (inconsistent billing definition).
      - is_data_capable: 1 if mobile_data_generation is not 2G.

    Args:
        df: DataFrame with at least sim_tenure_months, cumulative_spend_toman,
            monthly_spend_toman, and mobile_data_generation columns.

    Returns:
        DataFrame with three new int8 flag columns appended.
    """
    out = df.copy()
    out["tenure_zero_flag"] = (out["sim_tenure_months"] == 0).astype("int8")
    out["billing_definition_ambiguous_flag"] = (
        (out["sim_tenure_months"] == 0)
        & (out["cumulative_spend_toman"] == 0)
        & (out["monthly_spend_toman"] > 0)
    ).astype("int8")
    out["is_data_capable"] = (out["mobile_data_generation"] != "2G").astype("int8")
    return out


def enforce_cleaned_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Apply explicit canonical dtypes deterministically.

    Converts columns listed in CLEANED_DTYPE_CONTRACT to their declared
    dtypes using pd.to_numeric with errors="raise". This is intentionally
    strict — it will fail on unexpected data shapes rather than silently
    coerce.

    Called at the end of the pipeline. Validators later assert that the
    contract is met; this function is the enforcement layer.

    Args:
        df: DataFrame with columns that should match CLEANED_DTYPE_CONTRACT.

    Returns:
        DataFrame with numeric columns cast to int64/int8 as declared.

    Raises:
        ValueError: If a column contains non-numeric values (from
            pd.to_numeric errors="raise").
    """
    out = df.copy()
    for col, dtype in CLEANED_DTYPE_CONTRACT.items():
        if col not in out.columns:
            continue
        if dtype == "int64":
            out[col] = pd.to_numeric(out[col], errors="raise").astype("int64")
        elif dtype == "int8":
            out[col] = pd.to_numeric(out[col], errors="raise").astype("int8")
    return out


def _run_validation(
    reports: list[ValidationReport],
    step_name: str,
    *,
    policy: ValidationPolicy,
) -> ValidationReport:
    """Merge one or more ValidationReports and raise on failure.

    Each error/warning is prefixed with [step_name] for traceability
    through the pipeline log. The policy's raise_if_failed is called at
    the end.

    Args:
        reports: Validation reports to merge (usually one, but may be
            multiple for composite validations).
        step_name: Human-readable pipeline step label (e.g. "raw_schema").
        policy: ValidationPolicy for the merged report.

    Returns:
        The merged ValidationReport (also raises on failure).

    Raises:
        PreprocessingValidationError: If any report has passed=False and
            the policy does not suppress failures.
    """
    merged = ValidationReport(policy=policy, started_at_monotonic=time.monotonic())
    for r in reports:
        if not r.passed:
            merged.passed = False
        merged.errors.extend([f"[{step_name}] {e}" for e in r.errors])
        merged.warnings.extend([f"[{step_name}] {w}" for w in r.warnings])
        merged.unknown_tokens.extend(r.unknown_tokens)
        merged.metrics.update(r.metrics)
    merged.raise_if_failed()
    return merged


def build_cleaned_frame(
    df_raw: pd.DataFrame,
    *,
    validate: bool = True,
    policy: ValidationPolicy | None = None,
) -> pd.DataFrame:
    """Build the canonical cleaned table from a raw DataFrame.

    This is the core pipeline: rename -> map categoricals -> encode target
    -> add QC flags -> enforce dtypes -> validate. Validation gates are
    interleaved after critical transform stages for early failure.

    Args:
        df_raw: Raw DataFrame as loaded by load_raw_csv.
        validate: If True (default), run validation gates after each major
            transform step. Set to False only for testing or debugging.
        policy: ValidationPolicy controlling failure severity. Defaults
            to a strict fail-fast policy.

    Returns:
        Canonical cleaned DataFrame with columns in CLEANED_COLUMN_ORDER.
    """
    pol = policy or ValidationPolicy()

    if validate:
        _run_validation([validate_raw_schema(df_raw, pol)], "raw_schema", policy=pol)

    df = rename_columns(df_raw.copy())
    df = map_categoricals(df)
    if validate:
        _run_validation([validate_mapped_categoricals(df, pol)], "mapped_categoricals", policy=pol)

    df = encode_target(df)
    df = add_quality_flags(df)
    df = enforce_cleaned_dtypes(df)

    if validate:
        _run_validation(
            [validate_cleaned_frame(df, CLEANED_COLUMN_ORDER, pol)],
            "cleaned_final",
            policy=pol,
        )

    return df[CLEANED_COLUMN_ORDER].copy()


@dataclass
class PreprocessingConfig:
    """Configuration for a single preprocessing run.

    Attributes:
        raw_csv: Path to the raw Persian CSV file.
        verbose: If True, emit INFO-level logs.
        write_qc_artifacts: If True, produce QC outputs under outputs/preprocessing/.
        write_qc_plots: If True, render matplotlib sanity plots (requires
            matplotlib installed). Only relevant if write_qc_artifacts is True.
        validation_policy: Controls failure severity for validation gates.
    """

    raw_csv: Path = DEFAULT_RAW_CSV
    verbose: bool = True
    write_qc_artifacts: bool = True
    write_qc_plots: bool = True
    validation_policy: ValidationPolicy = field(default_factory=ValidationPolicy)


@dataclass
class PreprocessingArtifacts:
    """Return bundle from run_preprocessing.

    Attributes:
        manifest: Full preprocessing manifest dict (schema version, row
            counts, segment rates, paths, policies).
        cleaned: The canonical cleaned DataFrame (CLEANED_COLUMN_ORDER).
        qc_summary: QC summary dict (empty if QC was disabled).
    """

    manifest: dict[str, Any]
    cleaned: pd.DataFrame
    qc_summary: dict[str, Any] = field(default_factory=dict)


def _configure_logging(verbose: bool) -> None:
    """Set up logging level based on verbosity flag.

    Uses force=True to override any pre-existing logging configuration
    (e.g. from pytest or interactive sessions).

    Args:
        verbose: If True, set level to INFO; otherwise WARNING.
    """
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def run_preprocessing(cfg: PreprocessingConfig | None = None) -> PreprocessingArtifacts:
    """End-to-end preprocessing: snapshot raw, build cleaned parquet, manifest, QC outputs.

    This is the main entry point for the preprocessing pipeline. It:
      1. Validates the raw CSV schema.
      2. Resolves duplicate subscriber IDs per policy.
      3. Snapshots the raw CSV to data/raw/.
      4. Renames columns, maps categoricals, encodes target, adds QC flags.
      5. Runs validation gates after each transform stage.
      6. Writes the cleaned parquet, display labels, and QC artifacts.
      7. Writes a full preprocessing manifest for audit.

    Args:
        cfg: Configuration for the run. Uses defaults if None.

    Returns:
        PreprocessingArtifacts containing the manifest dict, cleaned
        DataFrame, and QC summary.

    Raises:
        FileNotFoundError: If raw_csv does not exist.
        PreprocessingValidationError: If any validation gate fails.
    """
    cfg = cfg or PreprocessingConfig()
    _configure_logging(cfg.verbose)
    pol = cfg.validation_policy

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = Path(cfg.raw_csv)
    if not raw_path.is_file():
        raise FileNotFoundError(raw_path)

    qc = QCReporter(write_plots=cfg.write_qc_plots) if cfg.write_qc_artifacts else None

    # --- Step 01: Load & validate raw ---
    df_raw = load_raw_csv(raw_path)
    if qc:
        qc.save_sample_rows(df_raw, "01_raw_head")
        qc.log_step("01_raw_loaded", df_raw)

    raw_report = validate_raw_schema(df_raw, pol)
    if qc:
        qc.save_validation_report(raw_report, "raw_schema")
    raw_report.raise_if_failed()

    # --- Step 01b: Duplicate resolution ---
    # Must happen before renaming because the ID column header is still Persian.
    id_col = normalize_column_name("شناسه_مشترک")
    dedup_metrics: dict[str, Any] = {}
    if id_col in df_raw.columns:
        df_raw, dedup_metrics = apply_duplicate_subscriber_policy(
            df_raw,
            id_col,
            pol.duplicate_subscriber_id,
        )
        if dedup_metrics.get("rows_dropped"):
            logger.warning(
                "Dropped %s duplicate subscriber rows (policy=%s)",
                dedup_metrics["rows_dropped"],
                pol.duplicate_subscriber_id,
            )

    if qc:
        qc.log_step("01b_raw_validated", df_raw, {**raw_report.metrics, **dedup_metrics})

    # Snapshot the raw CSV for reproducibility.
    raw_snapshot = RAW_DIR / raw_path.name
    shutil.copy2(raw_path, raw_snapshot)
    logger.info("Raw snapshot: %s", raw_snapshot)

    # --- Step 02: Rename headers ---
    df_renamed = rename_columns(df_raw.copy())
    if qc:
        qc.log_step("02_renamed", df_renamed)
        qc.save_sample_rows(df_renamed, "02_renamed_head")

    # --- Step 03: Map categoricals ---
    df_mapped = map_categoricals(df_renamed)
    mapped_report = validate_mapped_categoricals(df_mapped, pol)
    if qc:
        qc.save_validation_report(mapped_report, "mapped")
        mapped_report.raise_if_failed()
        qc.log_step("03_mapped", df_mapped)
        qc.save_value_counts(
            df_mapped,
            ["gender", "sim_card_type", "mobile_data_generation", "operator_app_usage"]
            + list(TRI_STATE_COLUMNS),
            "mapped",
        )
        qc.save_unknown_token_table(mapped_report.unknown_tokens)

    # --- Step 04: Encode target ---
    df_target = encode_target(df_mapped)
    if qc:
        qc.log_step("04_target_encoded", df_target)

    # --- Step 05: QC flags + dtypes + final validation ---
    cleaned = add_quality_flags(df_target)
    cleaned = enforce_cleaned_dtypes(cleaned)

    final_report = validate_cleaned_frame(cleaned, CLEANED_COLUMN_ORDER, pol)
    if qc:
        qc.save_validation_report(final_report, "cleaned_final")
        final_report.raise_if_failed()
        qc.log_step("05_cleaned_final", cleaned, final_report.metrics)
        qc.save_sample_rows(cleaned, "05_cleaned_head")
    else:
        final_report.raise_if_failed()

    # --- Persist cleaned output ---
    # Prefer parquet; fall back to CSV if pyarrow is not installed.
    cleaned_path = CLEANED_DIR / "subscribers_cleaned.parquet"
    try:
        cleaned.to_parquet(cleaned_path, index=False)
    except ImportError:
        cleaned_path = CLEANED_DIR / "subscribers_cleaned.csv"
        cleaned.to_csv(cleaned_path, index=False)
        logger.warning("pyarrow unavailable; wrote CSV instead of parquet")

    DISPLAY_LABELS_PATH.write_text(dumps_display_label_bundle(), encoding="utf-8")

    ambiguous = int(cleaned["billing_definition_ambiguous_flag"].sum())
    tenure_zero = int(cleaned["tenure_zero_flag"].sum())
    n_2g = int((cleaned["mobile_data_generation"] == "2G").sum())

    # --- QC artifacts ---
    qc_summary: dict[str, Any] = {}
    qc_paths: dict[str, str] = {}

    if cfg.write_qc_artifacts and qc:
        qc.save_null_counts(cleaned, "cleaned")
        churn_status = qc.save_churn_outputs(cleaned)
        flag_status = qc.save_flag_summary(cleaned)
        plot_paths = qc.maybe_write_plots(cleaned)
        qc_summary = qc.finalize(
            {
                "ambiguous_billing_rows": ambiguous,
                "tenure_zero_rows": tenure_zero,
                "n_2g": n_2g,
                "churn_qc": churn_status,
                "flag_qc": flag_status,
                "plot_paths": plot_paths,
                "unknown_token_summary": final_report.metrics.get("unknown_token_summary", {}),
            }
        )
        qc_paths = {
            "qc_dir": str(qc.output_dir),
            "qc_summary": str(qc.output_dir / "qc_summary.json"),
            "qc_index": str(qc.output_dir / "qc_index.json"),
        }

    # --- Build and persist manifest ---
    # The manifest documents every policy, count, and decision made during
    # this preprocessing run for full auditability.
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "canonical_cleaned_only",
        "validation_policy": pol.to_dict(),
        "duplicate_subscriber_id_policy": pol.duplicate_subscriber_id,
        "null_handling_policy": pol.null_handling,
        "explicitly_not_included": [
            "winsorization",
            "robust scaling",
            "sklearn ColumnTransformer fit",
            "modeling_ready matrix",
            "feature_engineering interaction flags",
            "cumulative_spend imputation for tenure_zero rows",
            "collapsing no_data_service into no",
        ],
        "tri_state_policy": {
            "english_tokens": ["yes", "no", "no_data_service"],
            "rule": "2G rows must be no_data_service on six VAS/data columns; non-2G must be yes or no only",
        },
        "dtype_contract": CLEANED_DTYPE_CONTRACT,
        "spend_policy": {
            "imputation": "none",
            "ambiguous_billing_rows": ambiguous,
            "tenure_zero_rows": tenure_zero,
        },
        "row_counts": {"raw": int(len(df_raw)), "cleaned": int(len(cleaned))},
        "duplicate_resolution": dedup_metrics,
        "segment_counts": {
            "n_2g": n_2g,
            "n_data_capable": int(cleaned["is_data_capable"].sum()),
            "churn_rate": round(float(cleaned["churn_binary"].mean()), 4),
        },
        "unknown_token_summary": final_report.metrics.get("unknown_token_summary", {}),
        "cleaned_column_schema": CLEANED_COLUMN_SCHEMA,
        "paths": {
            "raw_snapshot": str(raw_snapshot),
            "cleaned": str(cleaned_path),
            "display_labels": str(DISPLAY_LABELS_PATH),
            **qc_paths,
        },
        "bilingual_labels": {
            "canonical_language": "english",
            "display_bundle": str(DISPLAY_LABELS_PATH),
        },
    }

    CLEANED_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if cfg.verbose:
        logger.info(
            "Cleaned rows: %s | churn rate: %.2f%%",
            len(cleaned),
            100 * manifest["segment_counts"]["churn_rate"],
        )
        logger.info(
            "QC flags: tenure_zero=%s ambiguous_billing=%s 2G=%s",
            tenure_zero,
            ambiguous,
            n_2g,
        )
        logger.info("Wrote %s", cleaned_path)

    return PreprocessingArtifacts(manifest=manifest, cleaned=cleaned, qc_summary=qc_summary)
