"""Validation gates for raw and cleaned preprocessing layers.

Pipeline position:
  Consumed by pipeline.py (validate_raw_schema, validate_mapped_categoricals,
  validate_cleaned_frame) and by qc.py (UnknownTokenReport, unknown_tokens_to_dataframe).

Workflow stage:
  **Training + Inference** — validation is policy-driven but the policy
  is shared across both stages. During training the default strict policy
  is used; inference may use a relaxed policy.

Key invariants:
  - Validation reports are composable (merged via _merge_reports).
  - ValidationPolicy is a frozen dataclass for auditable serialization.
  - PreprocessingValidationError carries details dict with full context.
  - Unknown token collection reports both the normalized form (for matching)
    and the original surface form (for debugging).
  - All validation functions return a ValidationReport; they never raise
    directly. Callers must call report.raise_if_failed() to trigger
    PreprocessingValidationError.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from preprocessing.config import (
    AGE_MAX,
    AGE_MIN,
    ALLOWED_BIRTH_MONTHS_NORMALIZED,
    ALLOWED_CHURN_BINARY,
    ALLOWED_GENDER,
    ALLOWED_MOBILE_GENERATION,
    ALLOWED_OPERATOR_APP,
    ALLOWED_SIM_TYPE,
    ALLOWED_TRI_STATE,
    CLEANED_DTYPE_CONTRACT,
    COLUMN_RENAME,
    DEFAULT_DUPLICATE_SUBSCRIBER_ID_POLICY,
    DEFAULT_NULL_HANDLING_POLICY,
    DuplicateSubscriberIdPolicy,
    NullHandlingPolicy,
    SIM_TENURE_MAX_MONTHS,
    TRI_STATE_COLUMNS,
    VALIDATION_VERSION,
)
from preprocessing.text import (
    normalize_allowed_vocab,
    normalize_column_name,
    normalize_series_tokens,
    normalize_text_token,
)

FloatPolicy = Literal["fail", "warn"]
"""Policy for handling float dtypes where int is expected."""


class PreprocessingValidationError(ValueError):
    """Raised when preprocessing data fails a contract check.

    Carries a details dict with full error context including the error
    messages, warnings, unknown token reports, metrics snapshot, and
    the active validation policy.

    Attributes:
        details: Machine-readable dict with error context for logging
            and reporting.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class ValidationPolicy:
    """Auditable, deterministic runtime validation policy.

    This is a frozen dataclass so that it can be safely shared and
    serialized. All decisions (fail fast vs. warn, which nulls to allow,
    how to handle duplicate IDs) are captured here.

    Attributes:
        duplicate_subscriber_id: How to handle duplicate subscriber_id rows.
        null_handling: How to handle null values across the pipeline.
        null_allowed_columns: Set of columns where nulls are tolerated
            (only relevant when null_handling is "allow_selected_columns").
        float_as_int_policy: Whether to fail or warn when a column declared
            as int64/int8 has a float dtype.
        validation_version: Schema version string for audit trail.
    """

    duplicate_subscriber_id: DuplicateSubscriberIdPolicy = DEFAULT_DUPLICATE_SUBSCRIBER_ID_POLICY
    null_handling: NullHandlingPolicy = DEFAULT_NULL_HANDLING_POLICY
    null_allowed_columns: frozenset[str] = frozenset()
    float_as_int_policy: FloatPolicy = "fail"
    validation_version: str = VALIDATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy to a JSON-compatible dict."""
        return {
            "duplicate_subscriber_id": self.duplicate_subscriber_id,
            "null_handling": self.null_handling,
            "null_allowed_columns": sorted(self.null_allowed_columns),
            "float_as_int_policy": self.float_as_int_policy,
            "validation_version": self.validation_version,
        }


DEFAULT_VALIDATION_POLICY = ValidationPolicy()
"""Module-level default policy (strict fail-fast)."""


@dataclass
class UnknownTokenReport:
    """Records values in a column that fall outside the allowed vocabulary.

    Attributes:
        column: Column name where unknown tokens were found.
        unknown_values: Dict mapping unknown token string -> row count.
        allowed: Sorted list of allowed values for reference.
    """

    column: str
    unknown_values: dict[str, int]
    allowed: list[str]

    @property
    def total_unknown_rows(self) -> int:
        """Total number of rows with unknown tokens across all distinct values."""
        return int(sum(self.unknown_values.values()))


@dataclass
class ValidationReport:
    """Accumulates validation results from one or more check functions.

    A report can be:
      - Passed (passed=True) — all checks clear.
      - Failed (passed=False) — at least one check produced an error.
      - Warning-only — has warnings but no errors; passed remains True.

    Attributes:
        passed: True if no failures were recorded (warnings alone don't fail).
        errors: List of error messages.
        warnings: List of warning messages.
        unknown_tokens: List of UnknownTokenReport from categorical checks.
        metrics: Dict of numeric/structured metrics (row counts, null columns, etc.).
        policy: The active validation policy.
        started_at_monotonic: Timestamp from time.monotonic() when the report was created.
        elapsed_ms: Wall-clock time consumed by this validation (set by finish()).
    """

    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknown_tokens: list[UnknownTokenReport] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    policy: ValidationPolicy = field(default_factory=ValidationPolicy)
    started_at_monotonic: float = 0.0
    elapsed_ms: float = 0.0

    def fail(self, msg: str) -> None:
        """Record a validation failure.

        Args:
            msg: Human-readable error description.
        """
        self.passed = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        """Record a validation warning (does not set passed=False).

        Args:
            msg: Human-readable warning description.
        """
        self.warnings.append(msg)

    def finish(self) -> None:
        """Finalize the report: compute elapsed time and aggregate metrics.

        Called automatically by raise_if_failed(). Settles elapsed_ms
        and populates unknown_token_summary in metrics.
        """
        self.elapsed_ms = round((time.monotonic() - self.started_at_monotonic) * 1000, 2)
        self.metrics["validation_version"] = self.policy.validation_version
        self.metrics["validation_policy"] = self.policy.to_dict()
        self.metrics["elapsed_ms"] = self.elapsed_ms
        self.metrics["unknown_token_summary"] = summarize_unknown_tokens(self.unknown_tokens)

    def raise_if_failed(self) -> None:
        """Raise PreprocessingValidationError if the report has failures.

        Always calls finish() first to populate elapsed time and metrics.
        Raises with a details dict containing the full error context.
        """
        self.finish()
        if not self.passed:
            raise PreprocessingValidationError(
                "; ".join(self.errors),
                details={
                    "errors": self.errors,
                    "warnings": self.warnings,
                    "unknown_tokens": [
                        {
                            "column": u.column,
                            "unknown_values": u.unknown_values,
                            "allowed": u.allowed,
                            "total_unknown_rows": u.total_unknown_rows,
                        }
                        for u in self.unknown_tokens
                    ],
                    "metrics": self.metrics,
                    "policy": self.policy.to_dict(),
                },
            )


def summarize_unknown_tokens(reports: list[UnknownTokenReport]) -> dict[str, Any]:
    """Summarize unknown token reports into a single flat dict for metrics.

    Args:
        reports: List of per-column unknown token reports.

    Returns:
        Dict with total_unknown_rows and a nested columns dict mapping
        column name -> {unknown_value: count}.
    """
    if not reports:
        return {"total_unknown_rows": 0, "columns": {}}
    by_col = {r.column: r.unknown_values for r in reports}
    return {
        "total_unknown_rows": int(sum(r.total_unknown_rows for r in reports)),
        "columns": by_col,
    }


def new_report(policy: ValidationPolicy | None = None) -> ValidationReport:
    """Create a new ValidationReport with monotonic start time.

    Args:
        policy: Validation policy to use. Defaults to strict fail-fast.

    Returns:
        A fresh ValidationReport ready for check functions.
    """
    pol = policy or DEFAULT_VALIDATION_POLICY
    return ValidationReport(
        policy=pol,
        started_at_monotonic=time.monotonic(),
    )


def collect_unknown_tokens(
    series: pd.Series,
    allowed: frozenset[str] | set[str],
    column: str,
    *,
    normalize: bool = True,
) -> UnknownTokenReport | None:
    """Check a categorical series for values outside the allowed vocabulary.

    This is the core unknown-token detection function used by both raw
    and mapped-categorical validation. It optionally normalizes both the
    series values and the allowed set before comparison (for tolerant
    Persian token matching).

    When normalize=True, the report records the normalized form of the
    unknown values (for matching diagnostics). When normalize=False, the
    values as they appear in the series (post-stringification) are reported.

    Args:
        series: Categorical column to inspect.
        allowed: Set of allowed canonical values.
        column: Column name (for the report).
        normalize: If True, normalize both series values and allowed set
            before comparison. Default True.

    Returns:
        UnknownTokenReport if unknown values are found, or None if all
        values are within the allowed vocabulary.
    """
    s = series.dropna()
    if s.empty:
        return None

    if normalize:
        normalized = normalize_series_tokens(s)
        allowed_norm = normalize_allowed_vocab(frozenset(allowed))
        bad_mask = ~normalized.isin(allowed_norm)
        if not bad_mask.any():
            return None
        # Report original surface forms (before normalization) for debugging.
        counts = s.loc[bad_mask].map(normalize_text_token).value_counts().to_dict()
    else:
        s_str = s.astype(str).map(normalize_text_token)
        bad_mask = ~s_str.isin(allowed)
        if not bad_mask.any():
            return None
        counts = s_str[bad_mask].value_counts().to_dict()

    return UnknownTokenReport(
        column=column,
        unknown_values={str(k): int(v) for k, v in counts.items()},
        allowed=sorted(allowed),
    )


def check_nulls(
    df: pd.DataFrame,
    report: ValidationReport,
    *,
    context: str,
) -> None:
    """Apply the configured null-handling policy to a DataFrame.

    The policy field on the report determines the behavior:
      - "strict_fail": Any null causes a failure.
      - "warn_only": Nulls are logged as warnings only.
      - "allow_selected_columns": Nulls in columns listed in
        report.policy.null_allowed_columns are warned about; nulls in
        other columns cause a failure.

    Args:
        df: DataFrame to check for nulls.
        report: ValidationReport to append to (mutated in place).
        context: Label for metrics keys (e.g. "raw" or "cleaned").
    """
    if not df.isna().any().any():
        report.metrics[f"{context}_null_columns"] = []
        return

    null_cols = df.columns[df.isna().any()].tolist()
    report.metrics[f"{context}_null_columns"] = null_cols
    msg = f"Null values in {context}: {null_cols}"

    policy = report.policy.null_handling
    if policy == "strict_fail":
        report.fail(msg)
    elif policy == "warn_only":
        report.warn(msg)
    elif policy == "allow_selected_columns":
        disallowed = [c for c in null_cols if c not in report.policy.null_allowed_columns]
        if disallowed:
            report.fail(f"{msg} — disallowed nulls in: {disallowed}")
        else:
            report.warn(f"{msg} — allowed by policy")
    else:
        report.fail(f"Unknown null_handling policy: {policy}")


def apply_duplicate_subscriber_policy(
    df: pd.DataFrame,
    id_col: str,
    policy: DuplicateSubscriberIdPolicy,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Resolve duplicate subscriber IDs per the configured policy.

    Policies:
      - "fail_fast": Do not deduplicate; return the frame as-is. The
        caller is expected to check metrics and raise separately.
      - "keep_first": Keep the first occurrence of each subscriber_id.
      - "keep_last": Keep the last occurrence.

    Args:
        df: Raw DataFrame (still with Persian column headers).
        id_col: Name of the subscriber ID column (already normalized).
        policy: The duplicate resolution strategy.

    Returns:
        Tuple of (possibly deduped DataFrame, metrics dict). Metrics
        includes duplicate_subscriber_ids and, if any were found and
        resolved, rows_dropped and policy_applied.

    Raises:
        ValueError: If policy is not one of the known values.
    """
    metrics: dict[str, Any] = {"duplicate_subscriber_ids": int(df[id_col].duplicated().sum())}
    if metrics["duplicate_subscriber_ids"] == 0:
        return df, metrics

    if policy == "fail_fast":
        return df, metrics

    if policy == "keep_first":
        deduped = df.drop_duplicates(subset=[id_col], keep="first")
    elif policy == "keep_last":
        deduped = df.drop_duplicates(subset=[id_col], keep="last")
    else:
        raise ValueError(f"Unknown duplicate policy: {policy}")

    metrics["rows_dropped"] = int(len(df) - len(deduped))
    metrics["policy_applied"] = policy
    return deduped, metrics


def validate_raw_schema(
    df: pd.DataFrame,
    policy: ValidationPolicy | None = None,
) -> ValidationReport:
    """Validate the raw CSV before any transforms are applied.

    Checks performed:
      - Expected columns (from COLUMN_RENAME) are present.
      - No fully duplicate rows exist.
      - Null handling policy is applied.
      - Duplicate subscriber IDs are flagged if policy is fail_fast.

    Args:
        df: Raw DataFrame (Persian headers, not yet normalized).
        policy: Validation policy (default: strict fail-fast).

    Returns:
        ValidationReport with row/column metrics and any errors.
    """
    report = new_report(policy)
    report.metrics["n_rows"] = int(len(df))
    report.metrics["n_columns"] = int(len(df.columns))

    expected = {normalize_column_name(k) for k in COLUMN_RENAME}
    present = {normalize_column_name(c) for c in df.columns}
    missing = sorted(expected - present)
    extra = sorted(present - expected)
    if missing:
        report.fail(f"Raw CSV missing expected columns: {missing}")
    if extra:
        report.warn(f"Unexpected extra columns (ignored): {extra}")

    check_nulls(df, report, context="raw")

    dup_rows = int(df.duplicated().sum())
    report.metrics["duplicate_rows"] = dup_rows
    if dup_rows > 0:
        report.fail(f"Found {dup_rows} fully duplicate rows in raw CSV")

    id_col = normalize_column_name("شناسه_مشترک")
    if id_col in df.columns:
        dup_ids = int(df[id_col].duplicated().sum())
        report.metrics["duplicate_subscriber_ids"] = dup_ids
        if dup_ids > 0 and report.policy.duplicate_subscriber_id == "fail_fast":
            report.fail(
                f"Duplicate subscriber_id count={dup_ids} "
                f"(policy={report.policy.duplicate_subscriber_id})"
            )

    return report


def validate_mapped_categoricals(df: pd.DataFrame, policy: ValidationPolicy | None = None) -> ValidationReport:
    """After Persian-to-English mapping, ensure all categorical values are canonical.

    Verifies that every categorical column contains only expected English
    tokens. Unknown tokens are collected per-column for debugging.

    Args:
        df: DataFrame after map_categoricals() has been applied.
        policy: Validation policy (default: strict fail-fast).

    Returns:
        ValidationReport with unknown token reports and any failures.
    """
    report = new_report(policy)

    checks: list[tuple[str, frozenset[str]]] = [
        ("gender", ALLOWED_GENDER),
        ("sim_card_type", ALLOWED_SIM_TYPE),
        ("operator_app_usage", ALLOWED_OPERATOR_APP),
        ("mobile_data_generation", ALLOWED_MOBILE_GENERATION),
    ]
    for col, allowed in checks:
        if col not in df.columns:
            report.fail(f"Missing column after mapping: {col}")
            continue
        unk = collect_unknown_tokens(df[col], allowed, col, normalize=False)
        if unk:
            report.unknown_tokens.append(unk)
            report.fail(
                f"Unknown tokens in {col}: {unk.unknown_values} (allowed: {sorted(allowed)})"
            )

    if "birth_month_persian" in df.columns:
        normalized = normalize_series_tokens(df["birth_month_persian"])
        bad = ~normalized.isin(ALLOWED_BIRTH_MONTHS_NORMALIZED)
        if bad.any():
            counts = normalized[bad].value_counts().to_dict()
            report.unknown_tokens.append(
                UnknownTokenReport(
                    column="birth_month_persian",
                    unknown_values={str(k): int(v) for k, v in counts.items()},
                    allowed=sorted(ALLOWED_BIRTH_MONTHS_NORMALIZED),
                )
            )
            report.fail(f"Unknown birth_month_persian tokens: {counts}")

    for col in TRI_STATE_COLUMNS:
        if col not in df.columns:
            report.fail(f"Missing tri-state column: {col}")
            continue
        unk = collect_unknown_tokens(df[col], ALLOWED_TRI_STATE, col, normalize=False)
        if unk:
            report.unknown_tokens.append(unk)
            report.fail(f"Unknown tokens in {col}: {unk.unknown_values}")

    if "churn_binary" in df.columns:
        bad = ~df["churn_binary"].isin(ALLOWED_CHURN_BINARY)
        if bad.any():
            report.fail(
                f"Invalid churn_binary values: {df.loc[bad, 'churn_binary'].unique().tolist()}"
            )

    return report


def validate_structural_2g_consistency(
    df: pd.DataFrame,
    policy: ValidationPolicy | None = None,
) -> ValidationReport:
    """Enforce the structural relationship between 2G and VAS/data tri-state columns.

    Rule: 2G subscribers cannot have VAS/data add-ons, so their tri-state
    columns must be 'no_data_service'. Conversely, non-2G subscribers must
    never be 'no_data_service' (they are either 'yes' or 'no').

    Also verifies that is_data_capable agrees with mobile_data_generation.

    Args:
        df: Cleaned DataFrame (post-mapping).
        policy: Validation policy (default: strict fail-fast).

    Returns:
        ValidationReport with n_2g metric and any consistency failures.
    """
    report = new_report(policy)
    if "mobile_data_generation" not in df.columns:
        return report

    gen = df["mobile_data_generation"].map(normalize_text_token).str.upper()
    is_2g = gen == "2G"
    n_2g = int(is_2g.sum())
    report.metrics["n_2g"] = n_2g

    for col in TRI_STATE_COLUMNS:
        if col not in df.columns:
            continue
        bad_2g = is_2g & (df[col] != "no_data_service")
        if bad_2g.any():
            n_bad = int(bad_2g.sum())
            samples = df.loc[bad_2g, [col, "mobile_data_generation"]].head(5).to_dict("records")
            report.fail(
                f"{col}: {n_bad} rows on 2G have value != no_data_service. Samples: {samples}"
            )
        bad_non = (~is_2g) & (df[col] == "no_data_service")
        if bad_non.any():
            report.fail(f"{col}: {int(bad_non.sum())} non-2G rows incorrectly marked no_data_service")

    if "is_data_capable" in df.columns:
        expected = (gen != "2G").astype("int8")
        actual = df["is_data_capable"]
        if not pd.api.types.is_integer_dtype(actual):
            report.fail(f"is_data_capable must be integer, got {actual.dtype}")
        mismatch = (actual.astype("int8") != expected).sum()
        if mismatch:
            report.fail(
                f"is_data_capable mismatches mobile_data_generation on {int(mismatch)} rows"
            )

    return report


def _dtype_name(dtype: np.dtype | pd.api.extensions.ExtensionDtype) -> str:
    """Normalize pandas dtype names for comparison.

    Handles nullable integer dtypes (Int64 -> int64, Int8 -> int8)
    which otherwise have different string representations.

    Args:
        dtype: numpy or pandas extension dtype.

    Returns:
        Normalized dtype string name.
    """
    name = str(dtype)
    if name == "Int64":
        return "int64"
    if name == "Int8":
        return "int8"
    return name


def validate_canonical_dtypes(
    df: pd.DataFrame,
    policy: ValidationPolicy | None = None,
) -> ValidationReport:
    """Enforce the strict dtype contract for cleaned numeric/flag columns.

    Checks each column in CLEANED_DTYPE_CONTRACT:
      - Column must exist.
      - Must not be float (unless float_as_int_policy allows it).
      - Must match expected int64/int8 dtype.

    This is a strict check — no silent coercion is allowed.

    Args:
        df: Cleaned DataFrame.
        policy: Validation policy (default: strict fail-fast).

    Returns:
        ValidationReport with dtype_snapshot metric and any failures.
    """
    report = new_report(policy)

    for col, expected in CLEANED_DTYPE_CONTRACT.items():
        if col not in df.columns:
            report.fail(f"Missing column for dtype contract: {col}")
            continue

        actual = df[col].dtype
        actual_name = _dtype_name(actual)

        if pd.api.types.is_float_dtype(actual):
            msg = f"{col}: float dtype {actual} not allowed (expected {expected})"
            if report.policy.float_as_int_policy == "fail":
                if not np.allclose(df[col] % 1, 0, equal_nan=True):
                    report.fail(f"{col}: float column contains non-integer values")
                else:
                    report.fail(msg + " — possible silent coercion upstream")
            else:
                report.warn(msg)

        elif expected == "int64" and actual_name not in ("int64", "int32"):
            report.fail(f"{col}: expected int64, got {actual}")
        elif expected == "int8" and actual_name not in ("int8", "int64"):
            report.fail(f"{col}: expected int8, got {actual}")

        report.metrics.setdefault("dtype_snapshot", {})[col] = str(actual)

    return report


def validate_numeric_fields(
    df: pd.DataFrame,
    policy: ValidationPolicy | None = None,
) -> ValidationReport:
    """Range-check numeric business fields without applying any scaling.

    Checks:
      - All numeric columns must have non-negative values.
      - Age must be within [AGE_MIN, AGE_MAX].
      - sim_tenure_months exceeding SIM_TENURE_MAX_MONTHS triggers a warning.

    Args:
        df: Cleaned DataFrame.
        policy: Validation policy (default: strict fail-fast).

    Returns:
        ValidationReport merged with dtype validation results.
    """
    report = new_report(policy)
    report = _merge_reports(report, validate_canonical_dtypes(df, policy))

    int_cols = [
        "subscriber_id",
        "age",
        "sim_tenure_months",
        "monthly_spend_toman",
        "cumulative_spend_toman",
    ]
    for col in int_cols:
        if col not in df.columns:
            continue
        if (df[col] < 0).any():
            report.fail(f"{col}: {int((df[col] < 0).sum())} negative values")

    if "age" in df.columns:
        if (df["age"] < AGE_MIN).any() or (df["age"] > AGE_MAX).any():
            report.fail(f"age outside [{AGE_MIN}, {AGE_MAX}]")

    if "sim_tenure_months" in df.columns:
        if (df["sim_tenure_months"] > SIM_TENURE_MAX_MONTHS).any():
            report.warn(f"sim_tenure_months exceeds {SIM_TENURE_MAX_MONTHS} on some rows")

    return report


def validate_cleaned_frame(
    df: pd.DataFrame,
    expected_columns: list[str],
    policy: ValidationPolicy | None = None,
) -> ValidationReport:
    """Final validation gate on the canonical cleaned output.

    This is the composite validator called at the end of the pipeline.
    It checks:
      - Expected column presence (and absence of unexpected columns).
      - Nulls per policy.
      - No duplicate subscriber_id in the cleaned output.
      - Delegates to validate_mapped_categoricals,
        validate_structural_2g_consistency, and validate_numeric_fields.

    Args:
        df: The final cleaned DataFrame.
        expected_columns: The canonical column order/schema list.
        policy: Validation policy (default: strict fail-fast).

    Returns:
        Composite ValidationReport.
    """
    report = new_report(policy)
    report.metrics["n_rows"] = int(len(df))

    missing_cols = [c for c in expected_columns if c not in df.columns]
    extra_cols = [c for c in df.columns if c not in expected_columns]
    if missing_cols:
        report.fail(f"Cleaned frame missing columns: {missing_cols}")
    if extra_cols:
        report.fail(f"Cleaned frame has unexpected columns: {extra_cols}")

    check_nulls(df, report, context="cleaned")

    if "subscriber_id" in df.columns:
        dup_ids = int(df["subscriber_id"].duplicated().sum())
        report.metrics["duplicate_subscriber_ids"] = dup_ids
        if dup_ids > 0:
            report.fail(f"Duplicate subscriber_id in cleaned output: {dup_ids}")

    return _merge_reports(
        report,
        validate_mapped_categoricals(df, policy),
        validate_structural_2g_consistency(df, policy),
        validate_numeric_fields(df, policy),
    )


def _merge_reports(base: ValidationReport, *others: ValidationReport) -> ValidationReport:
    """Merge multiple ValidationReports into a single base report.

    Errors, warnings, unknown tokens, and metrics from all others are
    appended/merged into the base. If any other report has passed=False,
    the base is also marked as failed.

    Args:
        base: The primary report to merge into.
        *others: Additional reports to merge.

    Returns:
        The base report (mutated in place).
    """
    for o in others:
        if not o.passed:
            base.passed = False
        base.errors.extend(o.errors)
        base.warnings.extend(o.warnings)
        base.unknown_tokens.extend(o.unknown_tokens)
        base.metrics.update(o.metrics)
    return base


def unknown_tokens_to_dataframe(reports: list[UnknownTokenReport]) -> pd.DataFrame:
    """Flatten a list of UnknownTokenReport into a DataFrame for QC CSV export.

    Each row represents one unknown token in one column, with its count
    and a sample of allowed values.

    Args:
        reports: List of per-column unknown token reports.

    Returns:
        DataFrame with columns: column, unknown_token, row_count, allowed_sample.
        Empty DataFrame if reports is empty.
    """
    rows: list[dict[str, Any]] = []
    for r in reports:
        for token, count in r.unknown_values.items():
            rows.append(
                {
                    "column": r.column,
                    "unknown_token": token,
                    "row_count": count,
                    "allowed_sample": "|".join(r.allowed[:5]),
                }
            )
    return pd.DataFrame(rows)
