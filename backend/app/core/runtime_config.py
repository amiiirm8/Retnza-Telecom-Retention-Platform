"""
Artifact-driven runtime configuration — the single source of truth for backend ML state.

Pipeline position:
  Loaded at startup (and lazily cached) by MLService. Reads champion model
  artifacts (joblib bundle), JSON manifests, Parquet schemas, and runs validation
  to guarantee the backend can safely serve predictions.

Workflow stage:
  Consumed by every endpoint that needs model metadata, feature contracts,
  thresholds, or compatibility checks. Acts as the read-only view into which
  model version is champion, which features it expects, and what policies apply.

Key invariants:
  - All artifact loads go through _read_json / _parquet_columns with graceful
    degradation for optional files and hard failures for required ones.
  - Champion bundle must pass validate_backend_model_compatibility before any
    scoring can proceed. Legacy bundles (<= LEGACY_FEATURE_COUNT_MAX features)
    are explicitly blocked.
  - SHAP and recommendation Parquet files are validated against the champion
    feature contract to ensure cross-artifact consistency.
  - The RuntimeConfig dataclass is frozen — once constructed, it is immutable.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modeling.config import CHAMPION_BUNDLE_SCHEMA, LEGACY_FEATURE_COUNT_MAX, MODELING_SCHEMA_VERSION

EXPECTED_RECOMMENDATION_SCHEMA = "task8-recommendations-v4"
EXPECTED_SHAP_SCHEMA = "task7-shap-v4"

REQUIRED_RECOMMENDATION_COLUMNS = {
    "subscriber_id",
    "churn_probability_raw",
    "churn_probability",
    "risk_tier",
    "rule_id",
    "recommended_action",
    "campaign_priority",
    "campaign_cost_tier",
    "crm_queue",
    "digital_only_flag",
    "escalation_required",
    "ecosystem_segment",
    "ecosystem_retention_strategy",
    "rule_top_driver",
    "shap_top_driver",
    "final_top_driver",
    "final_top_driver_source",
}

class RuntimeConfigError(RuntimeError):
    """
    Raised when production artifacts cannot be used safely.

    Carries an optional validation dict so callers can inspect exactly which
    check(s) failed (model, recommendation, SHAP, etc.).
    """

    def __init__(self, message: str, validation: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.validation = validation or {}


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Immutable, version-safe view of all backend runtime artifacts.

    Constructed once by load_runtime_config() and cached. Every field is derived
    from on-disk artifacts (joblib bundle, JSON manifests, Parquet schemas) that
    have been through validation.

    Fields:
        champion_bundle: The loaded model joblib dict (model, calibrator, thresholds).
        champion_manifest: JSON metadata describing the champion model version.
        model_stability_summary: Cross-validation stability metrics across candidate families.
        calibration_summary: Calibration fit diagnostics.
        drift_reference_snapshot: Training-time feature distributions for PSI monitoring.
        model_compatibility: Governance compatibility report from a prior validation run.
        drift_reference_summary: Aggregated drift + holdout performance summary.
        explainability_manifest: SHAP artifact metadata and feature schema.
        recommendation_manifest: Recommendation schema version and ecosystem analytics.
        feature_columns: Ordered list of feature names the champion model expects.
        risk_tier_thresholds: Probability boundaries for Very High / High / Medium / Low.
        operating_threshold: Decision threshold used at the operating policy point.
        operating_policy: Business policy name (e.g., 'recall@0.8').
        champion_family: ML model family name (e.g., 'lgbm_v4').
        calibration_method: Calibrator type (e.g., 'isotonic', 'platt').
        schema_version: Modeling schema version from manifest.
        bundle_schema_version: Champion bundle schema version.
        feature_schema_version: Active feature contract version.
        recommendation_schema_version: Recommendation Parquet schema version.
        shap_schema_version: SHAP Parquet schema version.
        recommendation_columns: Column list from the recommendation Parquet.
        ecosystem_segments: Segment label -> subscriber count mapping.
        ecosystem_taxonomy: Sorted list of ecosystem segment labels.
        ecosystem_analytics: Segment-level analytics from the recommendation manifest.
        artifact_freshness: Timestamps (UTC ISO) for every artifact file on disk.
        validation: Dict of validation reports for model, recommendations, SHAP.
        warnings: Non-fatal warnings collected during artifact loading.
    """

    champion_bundle: dict[str, Any]
    champion_manifest: dict[str, Any]
    model_stability_summary: dict[str, Any]
    calibration_summary: dict[str, Any]
    drift_reference_snapshot: dict[str, Any]
    model_compatibility: dict[str, Any]
    drift_reference_summary: dict[str, Any]
    explainability_manifest: dict[str, Any]
    recommendation_manifest: dict[str, Any]
    feature_columns: list[str]
    risk_tier_thresholds: dict[str, float]
    operating_threshold: float | None
    operating_policy: str | None
    champion_family: str | None
    calibration_method: str | None
    schema_version: str | None
    bundle_schema_version: str | None
    feature_schema_version: str | None
    recommendation_schema_version: str | None
    shap_schema_version: str | None
    recommendation_columns: list[str]
    ecosystem_segments: dict[str, int]
    ecosystem_taxonomy: list[str]
    ecosystem_analytics: dict[str, Any]
    artifact_freshness: dict[str, str | None]
    validation: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        """Number of features in the active champion feature contract."""
        return len(self.feature_columns)

    @property
    def compatibility_status(self) -> str:
        """
        Aggregate compatibility across model, recommendations, and SHAP validations.

        Returns 'compatible' only if all validation sub-reports pass.
        """
        checks = self.validation.values()
        return "compatible" if all(c.get("compatible", False) for c in checks) else "incompatible"

    @property
    def is_compatible(self) -> bool:
        """True if the entire artifact stack is compatible."""
        return self.compatibility_status == "compatible"


def _read_json(path: Path, *, required: bool = False) -> tuple[dict[str, Any], str | None]:
    """
    Read a JSON artifact file, returning parsed dict and an optional warning.

    Args:
        path: Filesystem path to the JSON file.
        required: If True, a missing or corrupt file raises RuntimeConfigError.
            If False, returns ({}, warning_string) on failure.

    Returns:
        Tuple of (data_dict, warning_or_None). On success, warning is None.
    """
    if not path.is_file():
        if required:
            raise RuntimeConfigError(f"Required artifact missing: {path}")
        return {}, f"Optional artifact missing: {path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        if required:
            raise RuntimeConfigError(f"Invalid JSON artifact {path}: {exc}") from exc
        return {}, f"Invalid optional JSON artifact {path.name}: {exc}"


def _utc_mtime(path: Path) -> str | None:
    """
    Return the UTC ISO-8601 modification timestamp of a file, or None.

    Used to populate artifact_freshness metadata so dashboards can report
    staleness of each artifact.
    """
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _parquet_columns(path: Path) -> list[str]:
    """
    Read column names from a Parquet file without loading full data.

    Prefers pyarrow (fast metadata-only read) and falls back to pandas if
    pyarrow is not available.

    Args:
        path: Path to the Parquet file.

    Returns:
        List of column names, or [] if the file does not exist.
    """
    if not path.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(path)
        return [meta.schema.column(i).name for i in range(meta.num_columns)]
    except Exception:
        import pandas as pd

        return list(pd.read_parquet(path).columns)


def _artifact_paths() -> dict[str, Path]:
    """
    Build a dict of logical keys -> filesystem paths from application settings.

    Keys match the field names used in artifact_freshness and load_runtime_config.
    """
    settings = get_settings()
    return {
        "champion_model": settings.CHAMPION_MODEL_PATH,
        "champion_manifest": settings.CHAMPION_MANIFEST_PATH,
        "model_stability_summary": settings.MODEL_STABILITY_SUMMARY_PATH,
        "calibration_summary": settings.CALIBRATION_SUMMARY_PATH,
        "drift_reference_snapshot": settings.DRIFT_REFERENCE_SNAPSHOT_PATH,
        "model_compatibility": settings.MODEL_COMPATIBILITY_PATH,
        "drift_reference_summary": settings.DRIFT_REFERENCE_SUMMARY_PATH,
        "explainability_manifest": settings.EXPLAINABILITY_MANIFEST_PATH,
        "subscriber_shap": settings.SHAP_PATH,
        "recommendation_manifest": settings.RECOMMENDATION_MANIFEST_PATH,
        "subscriber_recommendations": settings.RECOMMENDATIONS_PATH,
    }


def validate_backend_model_compatibility(
    bundle: dict[str, Any],
    manifest: dict[str, Any],
    compatibility_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Validate champion bundle shape, schema version, and critical component presence.

    Checks performed:
      - feature_columns list is present and consistent with n_features.
      - Legacy bundles (n_features <= LEGACY_FEATURE_COUNT_MAX) are blocked.
      - Schema versions match expected constants (CHAMPION_BUNDLE_SCHEMA, MODELING_SCHEMA_VERSION).
      - Manifest bundle_schema_version agrees with the bundle's own schema_version.
      - base_model has predict_proba; calibrator has calibrate_probabilities.
      - risk_band_thresholds exist (either in bundle or manifest).
      - Governance compatibility report's expected_n_features matches, if provided.

    Args:
        bundle: The loaded champion joblib dict.
        manifest: Champion manifest JSON as a dict.
        compatibility_report: Optional governance report from the training pipeline
            that may specify expected_n_features as a cross-check.

    Returns:
        Dict with 'compatible' (bool), 'errors' (list), 'warnings' (list), and
        metadata fields (n_features, schema versions, checked_at_utc).
    """
    report: dict[str, Any] = {
        "compatible": True,
        "warnings": [],
        "errors": [],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    feature_columns = list(bundle.get("feature_columns") or [])
    n_features = int(bundle.get("n_features") or len(feature_columns))
    report["n_features"] = n_features
    report["bundle_schema_version"] = bundle.get("schema_version")
    report["modeling_schema_version"] = manifest.get("schema_version")

    if not feature_columns:
        report["errors"].append("Champion bundle is missing feature_columns")
    if n_features != len(feature_columns):
        report["errors"].append(
            f"Champion n_features={n_features} does not match feature_columns={len(feature_columns)}"
        )
    if n_features <= LEGACY_FEATURE_COUNT_MAX:
        report["errors"].append(
            f"Champion bundle exposes {n_features} features; legacy bundles are blocked"
        )

    if bundle.get("schema_version") != CHAMPION_BUNDLE_SCHEMA:
        report["errors"].append(
            f"Champion bundle schema {bundle.get('schema_version')!r} != {CHAMPION_BUNDLE_SCHEMA!r}"
        )
    if manifest.get("schema_version") != MODELING_SCHEMA_VERSION:
        report["errors"].append(
            f"Champion manifest schema {manifest.get('schema_version')!r} != {MODELING_SCHEMA_VERSION!r}"
        )
    if manifest.get("bundle_schema_version") and manifest["bundle_schema_version"] != bundle.get("schema_version"):
        report["errors"].append("Champion manifest and joblib bundle schema versions disagree")

    base_model = bundle.get("base_model")
    calibrator = bundle.get("calibrator")
    if base_model is None or not hasattr(base_model, "predict_proba"):
        report["errors"].append("Champion bundle missing base_model.predict_proba")
    if calibrator is None or not hasattr(calibrator, "calibrate_probabilities"):
        report["errors"].append("Champion bundle missing calibrated score support")
    if not bundle.get("risk_band_thresholds") and not manifest.get("risk_band_thresholds"):
        report["errors"].append("No runtime risk band thresholds found in champion artifacts")

    expected_features = (compatibility_report or {}).get("expected_n_features")
    if expected_features is not None and int(expected_features) != n_features:
        report["errors"].append(
            f"Governance expected_n_features={expected_features} does not match bundle n_features={n_features}"
        )

    report["compatible"] = not report["errors"]
    return report


def validate_recommendation_schema(
    recommendation_manifest: dict[str, Any],
    recommendation_columns: list[str],
    *,
    champion_bundle_schema: str | None,
    modeling_schema: str | None,
) -> dict[str, Any]:
    """
    Validate recommendation artifact metadata and delivery Parquet schema.

    Checks performed:
      - All REQUIRED_RECOMMENDATION_COLUMNS are present in the Parquet.
      - Schema version matches EXPECTED_RECOMMENDATION_SCHEMA.
      - Manifest declares compatibility with the champion bundle and modeling schemas.
      - Manifest asserts non-uplift/causal/treatment-effect modeling (governance).
      - Manifest declares SHAP-does-not-select-actions (narrative-only policy).
      - Ecosystem segment counts are present (warning, not error).

    Args:
        recommendation_manifest: JSON dict from the recommendation manifest file.
        recommendation_columns: Column names read from the recommendation Parquet.
        champion_bundle_schema: The schema version of the champion model bundle.
        modeling_schema: The schema version from the champion manifest.

    Returns:
        Dict with 'compatible' (bool), 'errors' (list), 'warnings' (list).
    """
    report: dict[str, Any] = {
        "compatible": True,
        "warnings": [],
        "errors": [],
        "schema_version": recommendation_manifest.get("schema_version"),
        "columns_present": len(recommendation_columns),
    }
    missing = sorted(REQUIRED_RECOMMENDATION_COLUMNS - set(recommendation_columns))
    if missing:
        report["errors"].append(f"Recommendation parquet missing required columns: {missing}")
    if recommendation_manifest.get("schema_version") != EXPECTED_RECOMMENDATION_SCHEMA:
        report["errors"].append(
            f"Recommendation schema {recommendation_manifest.get('schema_version')!r} "
            f"!= {EXPECTED_RECOMMENDATION_SCHEMA!r}"
        )
    if recommendation_manifest.get("compatible_champion_schema") != champion_bundle_schema:
        report["errors"].append("Recommendation manifest is not compatible with champion bundle schema")
    if recommendation_manifest.get("compatible_modeling_schema") != modeling_schema:
        report["errors"].append("Recommendation manifest is not compatible with modeling schema")
    for key in ("not_uplift_modeling", "not_causal_inference", "not_treatment_effect_estimation"):
        if recommendation_manifest.get(key) is not True:
            report["errors"].append(f"Recommendation manifest must declare {key}=true")
    traceability = recommendation_manifest.get("explanation_traceability", {})
    if traceability.get("shap_does_not_select_actions") is not True:
        report["errors"].append("Recommendation manifest must preserve SHAP-as-narrative policy")

    if not recommendation_manifest.get("ecosystem_segment_counts"):
        report["warnings"].append("Recommendation manifest does not expose ecosystem segment counts")

    report["compatible"] = not report["errors"]
    return report


def validate_shap_schema(
    shap_manifest: dict[str, Any],
    shap_columns: list[str],
    feature_columns: list[str],
) -> dict[str, Any]:
    """
    Validate SHAP Parquet against the active champion feature schema.

    Checks performed:
      - SHAP manifest schema version matches EXPECTED_SHAP_SCHEMA.
      - Manifest-reported n_features matches the champion feature count.
      - Every champion feature has a corresponding shap_<feature> column.
      - subscriber_id is present.
      - Non-contract SHAP columns are flagged as warnings.
      - Legacy feature contracts (<= LEGACY_FEATURE_COUNT_MAX) are blocked.

    Args:
        shap_manifest: JSON dict from the explainability manifest.
        shap_columns: Column names read from the SHAP Parquet file.
        feature_columns: Active champion feature column names.

    Returns:
        Dict with 'compatible' (bool), 'errors' (list), 'warnings' (list),
        and 'n_shap_columns' (int).
    """
    report: dict[str, Any] = {
        "compatible": True,
        "warnings": [],
        "errors": [],
        "schema_version": shap_manifest.get("schema_version"),
        "n_expected_features": len(feature_columns),
    }
    if shap_manifest.get("schema_version") != EXPECTED_SHAP_SCHEMA:
        report["errors"].append(
            f"SHAP manifest schema {shap_manifest.get('schema_version')!r} != {EXPECTED_SHAP_SCHEMA!r}"
        )
    manifest_n_features = shap_manifest.get("n_features")
    if manifest_n_features is not None and int(manifest_n_features) != len(feature_columns):
        report["errors"].append("SHAP manifest feature count does not match champion feature count")

    expected_shap = {f"shap_{name}" for name in feature_columns}
    actual_shap = {name for name in shap_columns if name.startswith("shap_")}
    missing = sorted(expected_shap - actual_shap)
    extra = sorted(actual_shap - expected_shap)
    if "subscriber_id" not in shap_columns:
        report["errors"].append("SHAP parquet missing subscriber_id")
    if missing:
        report["errors"].append(f"SHAP parquet missing {len(missing)} feature columns")
    if extra:
        report["warnings"].append(f"SHAP parquet has {len(extra)} non-contract SHAP columns")
    if len(actual_shap) <= LEGACY_FEATURE_COUNT_MAX:
        report["errors"].append("SHAP parquet appears to use a legacy feature contract")

    report["n_shap_columns"] = len(actual_shap)
    report["compatible"] = not report["errors"]
    return report


@lru_cache(maxsize=1)
def load_runtime_config() -> RuntimeConfig:
    """
    Load, validate, and cache all runtime artifacts into a single RuntimeConfig.

    Called once per process (lru_cache with maxsize=1). Cleared explicitly by
    clear_runtime_config_cache() when artifacts are updated at runtime.

    Steps:
      1. Resolve artifact paths from settings.
      2. Load champion model joblib bundle (required).
      3. Load champion manifest JSON (required).
      4. Load optional JSON artifacts (stability, calibration, drift, etc.).
      5. Read Parquet schemas for recommendations and SHAP.
      6. Run model validation — fatal errors raise RuntimeConfigError.
      7. Run recommendation schema validation (non-fatal).
      8. Run SHAP schema validation (non-fatal).
      9. Extract thresholds, ecosystem metadata, and freshness timestamps.
      10. Construct and return the frozen RuntimeConfig.

    Raises:
        RuntimeConfigError: If the champion model file is missing, the bundle
            is not a dict, validation finds fatal errors, or risk tier thresholds
            cannot be found.
    """
    paths = _artifact_paths()
    if not paths["champion_model"].is_file():
        raise RuntimeConfigError(f"Champion model not found: {paths['champion_model']}")

    bundle = joblib.load(paths["champion_model"])
    if not isinstance(bundle, dict):
        raise RuntimeConfigError("Champion model artifact must be a dictionary bundle")

    warnings: list[str] = []
    champion_manifest, warning = _read_json(paths["champion_manifest"], required=True)
    if warning:
        warnings.append(warning)

    optional_json: dict[str, dict[str, Any]] = {}
    for key in (
        "model_stability_summary",
        "calibration_summary",
        "drift_reference_snapshot",
        "model_compatibility",
        "drift_reference_summary",
        "explainability_manifest",
        "recommendation_manifest",
    ):
        optional_json[key], warning = _read_json(paths[key])
        if warning:
            warnings.append(warning)

    feature_columns = list(bundle.get("feature_columns") or [])
    recommendation_columns = _parquet_columns(paths["subscriber_recommendations"])
    shap_columns = _parquet_columns(paths["subscriber_shap"])

    validation = {
        "model": validate_backend_model_compatibility(
            bundle,
            champion_manifest,
            optional_json["model_compatibility"],
        ),
        "recommendations": validate_recommendation_schema(
            optional_json["recommendation_manifest"],
            recommendation_columns,
            champion_bundle_schema=bundle.get("schema_version"),
            modeling_schema=champion_manifest.get("schema_version"),
        ),
        "shap": validate_shap_schema(
            optional_json["explainability_manifest"],
            shap_columns,
            feature_columns,
        ),
    }

    fatal_errors = validation["model"].get("errors", [])
    if fatal_errors:
        raise RuntimeConfigError("; ".join(fatal_errors), validation)

    thresholds = bundle.get("risk_band_thresholds") or champion_manifest.get("risk_band_thresholds") or {}
    if not thresholds:
        raise RuntimeConfigError("Risk tier thresholds were not found in champion artifacts", validation)

    recommendation_manifest = optional_json["recommendation_manifest"]
    ecosystem_segments = {
        str(k): int(v)
        for k, v in (recommendation_manifest.get("ecosystem_segment_counts") or {}).items()
    }
    ecosystem_taxonomy = sorted(ecosystem_segments)

    artifact_freshness = {key: _utc_mtime(path) for key, path in paths.items()}

    return RuntimeConfig(
        champion_bundle=bundle,
        champion_manifest=champion_manifest,
        model_stability_summary=optional_json["model_stability_summary"],
        calibration_summary=optional_json["calibration_summary"],
        drift_reference_snapshot=optional_json["drift_reference_snapshot"],
        model_compatibility=optional_json["model_compatibility"],
        drift_reference_summary=optional_json["drift_reference_summary"],
        explainability_manifest=optional_json["explainability_manifest"],
        recommendation_manifest=recommendation_manifest,
        feature_columns=feature_columns,
        risk_tier_thresholds={str(k): float(v) for k, v in thresholds.items()},
        operating_threshold=(
            float(bundle.get("operating_threshold"))
            if bundle.get("operating_threshold") is not None
            else (
                float(champion_manifest["operating_threshold"])
                if champion_manifest.get("operating_threshold") is not None
                else None
            )
        ),
        operating_policy=bundle.get("operating_policy") or champion_manifest.get("recommended_operating_policy"),
        champion_family=bundle.get("model_family") or champion_manifest.get("champion_family"),
        calibration_method=bundle.get("calibration_method") or champion_manifest.get("selected_calibration"),
        schema_version=champion_manifest.get("schema_version"),
        bundle_schema_version=bundle.get("schema_version"),
        feature_schema_version=(
            optional_json["explainability_manifest"].get("feature_schema")
            or recommendation_manifest.get("compatible_feature_schema")
        ),
        recommendation_schema_version=recommendation_manifest.get("schema_version"),
        shap_schema_version=optional_json["explainability_manifest"].get("schema_version"),
        recommendation_columns=recommendation_columns,
        ecosystem_segments=ecosystem_segments,
        ecosystem_taxonomy=ecosystem_taxonomy,
        ecosystem_analytics=recommendation_manifest.get("ecosystem_analytics") or {},
        artifact_freshness=artifact_freshness,
        validation=validation,
        warnings=warnings,
    )


def clear_runtime_config_cache() -> None:
    """
    Clear the cached RuntimeConfig so the next call to load_runtime_config
    re-reads all artifacts from disk.

    Called by artifact watchdogs or admin endpoints when model artifacts are
    refreshed without restarting the process.
    """
    load_runtime_config.cache_clear()
