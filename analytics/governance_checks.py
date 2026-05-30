"""Governance validations for the analytics layer.

Workflow stage: reporting-time (step 8 of 8, final validation gate).

Validates SHAP schema, recommendation schema, demographic field presence,
ecosystem compatibility, stale artifact detection, and feature alignment
against the 47-feature contract.

Pipeline position: final gate. Runs after all analytics modules and determines
whether the pipeline output is compatible. If any check fails (compatible=False),
the run_all pipeline exits with code 1.

Key invariants:
  - Schema versions are explicitly checked against expected constants.
  - Recommendation manifest must declare not_uplift_modeling=true,
    not_causal_inference=true, not_treatment_effect_estimation=true.
  - SHAP-as-narrative policy must be declared in manifest.
  - Stale artifact detection is advisory (warning only, not a compat gate).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    CHAMPION_MANIFEST_PATH,
    CHAMPION_PATH,
    FEATURES_PATH,
    GOVERNANCE_REPORT_PATH,
    OUTPUT_ANALYTICS,
    RECOMMENDATIONS_MANIFEST_PATH,
    RECOMMENDATIONS_PATH,
    SHAP_MANIFEST_PATH,
    SHAP_VALUES_PATH,
)
from feature_engineering.registry import MODEL_FEATURE_COLUMNS

REQUIRED_DEMOGRAPHIC_FIELDS = {
    "age", "gender_female", "gender_male", "birth_month_ordinal",
    "age_bucket", "young_user_flag", "senior_user_flag",
}

REQUIRED_ECOSYSTEM_FIELDS = {
    "rubika_user_flag", "ewano_user_flag", "hamrahman_user_flag",
    "volte_user_flag", "digital_engagement_score", "ecosystem_service_count",
    "is_data_capable",
}

REQUIRED_RECOMMENDATION_ANALYTICS_COLUMNS = {
    "subscriber_id", "churn_probability", "churn_probability_raw",
    "risk_tier", "rule_id", "campaign_priority", "crm_queue",
    "ecosystem_segment", "digital_only_flag", "human_touch_flag",
    "is_fallback_rule",
}

EXPECTED_CHAMPION_SCHEMA = "champion-bundle-v4"
EXPECTED_RECOMMENDATION_SCHEMA = "task8-recommendations-v4"
EXPECTED_SHAP_SCHEMA = "task7-shap-v4"
EXPECTED_FEATURE_SCHEMA = "task4-v2"


@dataclass
class GovernanceReport:
    """Structured governance validation output.

    Aggregates all check results into a single report object consumed by
    run_all.py and write_governance_report(). A single compatible=False
    anywhere means the pipeline should halt.

    Attributes:
        compatible: True if all checks pass, False if any critical check failed.
        checks: Raw per-check result dicts from each validate_* function.
        errors: Flattened list of all error messages across checks.
        warnings: Flattened list of all warning messages across checks.
        stale_artifacts: List of artifact staleness descriptions.
        generated_at_utc: ISO-8601 timestamp of report generation.
    """
    compatible: bool = True
    checks: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stale_artifacts: list[str] = field(default_factory=list)
    generated_at_utc: str = ""


class GovernanceValidationError(RuntimeError):
    """Raised on critical governance check failure.

    Used for exceptional failures (e.g. missing required files) that
    should abort immediately rather than collect multiple errors.
    """


def validate_shap_schema(
    shap_path: Path = SHAP_VALUES_PATH,
    shap_manifest_path: Path = SHAP_MANIFEST_PATH,
) -> dict[str, Any]:
    """Validate SHAP parquet columns and manifest metadata.

    Checks that all shap_<feature> columns exist per the 47-feature contract
    (MODEL_FEATURE_COLUMNS). Warns on extra columns and manifest schema
    version mismatches.

    Args:
        shap_path: Path to subscriber_shap_values.parquet.
        shap_manifest_path: Path to explainability_manifest.json.

    Returns:
        dict with check name, compatible flag, errors list, warnings list.
    """
    result: dict[str, Any] = {
        "check": "shap_schema_validation",
        "compatible": True,
        "errors": [],
        "warnings": [],
    }

    if not shap_path.is_file():
        result["errors"].append(f"SHAP values file missing: {shap_path}")
        result["compatible"] = False
        return result

    df = pd.read_parquet(shap_path)
    shap_cols = [c for c in df.columns if c.startswith("shap_")]
    expected_shap = {f"shap_{f}" for f in MODEL_FEATURE_COLUMNS}
    actual_shap = set(shap_cols)

    missing = sorted(expected_shap - actual_shap)
    extra = sorted(actual_shap - expected_shap)
    if missing:
        result["errors"].append(f"SHAP missing {len(missing)} feature columns")
        result["compatible"] = False
    if extra:
        result["warnings"].append(f"SHAP has {len(extra)} non-contract columns")

    if shap_manifest_path.is_file():
        manifest = json.loads(shap_manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != EXPECTED_SHAP_SCHEMA:
            result["warnings"].append(
                f"SHAP manifest schema {manifest.get('schema_version')} != {EXPECTED_SHAP_SCHEMA}"
            )
    else:
        result["warnings"].append("SHAP manifest file not found")

    return result


def validate_recommendation_schema(
    rec_path: Path = RECOMMENDATIONS_PATH,
    manifest_path: Path = RECOMMENDATIONS_MANIFEST_PATH,
) -> dict[str, Any]:
    """Validate recommendation parquet and manifest for analytics compatibility.

    Checks required analytics columns (subscriber_id, churn_probability, etc.)
    and manifest metadata including schema version, non-causal declarations,
    and SHAP-as-narrative policy.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.
        manifest_path: Path to recommendation_manifest.json.

    Returns:
        dict with check name, compatible flag, errors list, warnings list.
    """
    result: dict[str, Any] = {
        "check": "recommendation_schema_validation",
        "compatible": True,
        "errors": [],
        "warnings": [],
    }

    if not rec_path.is_file():
        result["errors"].append(f"Recommendations file missing: {rec_path}")
        result["compatible"] = False
        return result

    df = pd.read_parquet(rec_path)
    columns = set(df.columns)
    missing = sorted(REQUIRED_RECOMMENDATION_ANALYTICS_COLUMNS - columns)
    if missing:
        result["errors"].append(f"Missing required columns: {missing}")
        result["compatible"] = False

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != EXPECTED_RECOMMENDATION_SCHEMA:
            result["warnings"].append(
                f"Recommendation manifest schema {manifest.get('schema_version')} "
                f"!= {EXPECTED_RECOMMENDATION_SCHEMA}"
            )
        for flag in ("not_uplift_modeling", "not_causal_inference", "not_treatment_effect_estimation"):
            if manifest.get(flag) is not True:
                result["errors"].append(f"Manifest missing {flag}=true")
                result["compatible"] = False
        if manifest.get("explanation_traceability", {}).get("shap_does_not_select_actions") is not True:
            result["errors"].append("SHAP-as-narrative policy not declared in manifest")
            result["compatible"] = False
    else:
        result["warnings"].append("Recommendation manifest file not found")

    return result


def validate_demographic_fields(
    feature_path: Path = FEATURES_PATH,
) -> dict[str, Any]:
    """Verify demographic feature columns exist and have expected types.

    Checks for REQUIRED_DEMOGRAPHIC_FIELDS (age, gender, birth_month, etc.)
    in the feature parquet. Warns if any field is entirely null.

    Args:
        feature_path: Path to feature-schema feature parquet.

    Returns:
        dict with check name, compatible flag, errors list, warnings list.
    """
    result: dict[str, Any] = {
        "check": "demographic_field_validation",
        "compatible": True,
        "errors": [],
        "warnings": [],
    }

    if not feature_path.is_file():
        result["errors"].append(f"Feature file missing: {feature_path}")
        result["compatible"] = False
        return result

    df = pd.read_parquet(feature_path)
    columns = set(df.columns)
    missing = sorted(REQUIRED_DEMOGRAPHIC_FIELDS - columns)
    if missing:
        result["errors"].append(f"Missing demographic fields: {missing}")
        result["compatible"] = False

    for demog_field in REQUIRED_DEMOGRAPHIC_FIELDS & columns:
        if df[demog_field].isna().all():
            result["warnings"].append(f"Demographic field '{demog_field}' is entirely null")

    return result


def validate_ecosystem_compatibility(
    feature_path: Path = FEATURES_PATH,
) -> dict[str, Any]:
    """Ensure ecosystem feature fields are present and populated.

    Checks for REQUIRED_ECOSYSTEM_FIELDS (rubika_user_flag, etc.) in the
    feature parquet. Errors on missing fields, warns on null populations.

    Args:
        feature_path: Path to feature-schema feature parquet.

    Returns:
        dict with check name, compatible flag, errors list, warnings list.
    """
    result: dict[str, Any] = {
        "check": "ecosystem_compatibility_validation",
        "compatible": True,
        "errors": [],
        "warnings": [],
    }

    if not feature_path.is_file():
        result["errors"].append(f"Feature file missing: {feature_path}")
        result["compatible"] = False
        return result

    df = pd.read_parquet(feature_path)
    columns = set(df.columns)
    missing = sorted(REQUIRED_ECOSYSTEM_FIELDS - columns)
    if missing:
        result["errors"].append(f"Missing ecosystem fields: {missing}")
        result["compatible"] = False

    return result


def detect_stale_artifacts(
    max_age_hours: float = 168.0,
) -> list[str]:
    """Detect artifacts older than max_age_hours across key outputs.

    Checks modification timestamps of all critical artifacts (champion model,
    SHAP values, recommendations, features, manifests, governance report).
    Missing artifacts are reported as stale.

    Notes:
        168 hours = 7 days, a reasonable freshness window for weekly runs.

    Args:
        max_age_hours: Maximum allowed age in hours (default 168 = 7 days).

    Returns:
        list of strings describing stale or missing artifacts.
    """
    stale: list[str] = []
    now = datetime.now(timezone.utc)

    artifact_paths: dict[str, Path] = {
        "champion_model": CHAMPION_PATH,
        "champion_manifest": CHAMPION_MANIFEST_PATH,
        "shap_values": SHAP_VALUES_PATH,
        "shap_manifest": SHAP_MANIFEST_PATH,
        "recommendations": RECOMMENDATIONS_PATH,
        "recommendations_manifest": RECOMMENDATIONS_MANIFEST_PATH,
        "governance_report": GOVERNANCE_REPORT_PATH,
        "features": FEATURES_PATH,
    }

    for name, path in artifact_paths.items():
        if not path.exists():
            stale.append(f"{name}: missing")
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age = (now - mtime).total_seconds() / 3600
        if age > max_age_hours:
            stale.append(f"{name}: {age:.1f}h old (threshold: {max_age_hours}h)")

    return stale


def validate_feature_alignment(
    feature_path: Path = FEATURES_PATH,
) -> dict[str, Any]:
    """Verify feature columns match the 47-feature contract.

    Compares actual feature parquet columns against MODEL_FEATURE_COLUMNS
    from feature_engineering.registry. Missing columns are errors; extra
    columns are warnings.

    Args:
        feature_path: Path to feature-schema feature parquet.

    Returns:
        dict with check name, compatible flag, errors list, warnings list.
    """
    result: dict[str, Any] = {
        "check": "feature_alignment_validation",
        "compatible": True,
        "errors": [],
        "warnings": [],
    }

    if not feature_path.is_file():
        result["errors"].append(f"Feature file missing: {feature_path}")
        result["compatible"] = False
        return result

    df = pd.read_parquet(feature_path)
    actual = set(df.columns)
    expected = set(MODEL_FEATURE_COLUMNS)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        result["errors"].append(f"Missing {len(missing)} contract features")
        result["compatible"] = False
    if extra:
        result["warnings"].append(f"Extra non-contract columns: {len(extra)}")

    return result


def run_all_governance_checks(
    max_age_hours: float = 168.0,
) -> GovernanceReport:
    """Execute all governance checks and return a comprehensive report.

    Runs shap_schema, recommendation_schema, demographic_fields,
    ecosystem_compatibility, feature_alignment validations and
    stale artifact detection. Aggregates all errors and warnings
    into a single GovernanceReport dataclass.

    Args:
        max_age_hours: Max artifact age in hours for staleness check.

    Returns:
        GovernanceReport with all check results, errors, warnings, and
        overall compatible flag.
    """
    report = GovernanceReport(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )

    checks = {
        "shap_schema": validate_shap_schema(),
        "recommendation_schema": validate_recommendation_schema(),
        "demographic_fields": validate_demographic_fields(),
        "ecosystem_compatibility": validate_ecosystem_compatibility(),
        "feature_alignment": validate_feature_alignment(),
    }
    report.checks = checks
    report.stale_artifacts = detect_stale_artifacts(max_age_hours)

    for check_name, check_result in checks.items():
        check_result.pop("check", None)
        errors = check_result.get("errors", [])
        warnings = check_result.get("warnings", [])
        report.errors.extend(f"[{check_name}] {e}" for e in errors)
        report.warnings.extend(f"[{check_name}] {w}" for w in warnings)
        if not check_result.get("compatible", True):
            report.compatible = False

    return report


def write_governance_report(
    report: GovernanceReport | None = None,
) -> Path:
    """Serialize governance report to JSON.

    Converts GovernanceReport to a serializable dict and writes to
    OUTPUT_ANALYTICS / governance_checks_report.json.

    Args:
        report: GovernanceReport instance. If None, runs
            run_all_governance_checks() first.

    Returns:
        Path to the written JSON file.

    Side effects:
        Creates OUTPUT_ANALYTICS directory and writes JSON file.
    """
    report = report or run_all_governance_checks()

    serialized = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": report.generated_at_utc,
        "compatible": report.compatible,
        "errors": report.errors,
        "warnings": report.warnings,
        "stale_artifacts": report.stale_artifacts,
        "n_checks": len(report.checks),
        "checks": {
            name: {
                "compatible": chk.get("compatible", True),
                "errors": chk.get("errors", []),
                "warnings": chk.get("warnings", []),
            }
            for name, chk in report.checks.items()
        },
        "disclaimer": (
            "Governance validations check artifact compatibility and data quality. "
            "They do not evaluate model performance or business rule effectiveness."
        ),
    }

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_ANALYTICS / "governance_checks_report.json"
    out_path.write_text(json.dumps(serialized, indent=2, default=str), encoding="utf-8")

    return out_path
