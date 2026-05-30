"""
Model monitoring endpoints — health, drift, stability, governance.

Pipeline position:
  Read-only views over the current RuntimeConfig and ModelVersion registry.
  These endpoints provide observability into the champion model's health, drift
  status, cross-validation stability, and governance validation status.

Workflow stage:
  GET /api/v1/monitoring/health — current champion version, metrics, thresholds.
  GET /api/v1/monitoring/drift — PSI / feature distribution drift summary.
  GET /api/v1/monitoring/stability — cross-validation CV metrics by family.
  GET /api/v1/monitoring/governance — schema compatibility and artifact validation.
  GET /api/v1/monitoring/monitoring — backward-compatible alias for /health.

Security:
  All endpoints require authentication via CurrentUser dependency.
"""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.runtime_config import load_runtime_config
from app.models.model_version import ModelVersion

router = APIRouter()


def _test_metrics(runtime: Any) -> dict[str, Any]:
    """
    Extract holdout test metrics from champion artifacts with fallback chain.

    Priority order (most preferred -> fallback):
      1. uncalibrated_vs_selected_test (training pipeline output)
      2. test_at_operating_policy (operating-policy-specific metrics)
      3. baseline_metrics_holdout -> test_ranking_raw (drift reference)

    The fallback chain ensures that metrics are always available even if the
    training pipeline used a different key structure.
    """
    manifest = runtime.champion_manifest
    selected = manifest.get("uncalibrated_vs_selected_test") or {}
    operating = manifest.get("test_at_operating_policy") or {}
    drift = runtime.drift_reference_summary.get("baseline_metrics_holdout") or {}
    ranking = drift.get("test_ranking_raw") or {}
    return {
        "pr_auc": selected.get("pr_auc_calibrated")
        or selected.get("pr_auc_selected")
        or operating.get("pr_auc")
        or ranking.get("pr_auc"),
        "roc_auc": selected.get("roc_auc_calibrated")
        or selected.get("roc_auc_selected")
        or operating.get("roc_auc")
        or ranking.get("roc_auc"),
        "brier": selected.get("brier_calibrated")
        or selected.get("brier_selected")
        or operating.get("brier_score")
        or ranking.get("brier_score"),
        "ece": selected.get("ece_calibrated")
        or selected.get("ece_selected")
        or operating.get("ece")
        or ranking.get("ece"),
    }


@router.get("/health")
async def model_health(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    """
    Return the current champion model's health status and key metadata.

    Includes holdout test metrics (PR-AUC, ROC-AUC, Brier, ECE), champion version
    tag, schema versions, threshold policy, artifact freshness timestamps, and
    any warnings generated during artifact loading.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        Dict with metrics, champion metadata, threshold policy, and freshness.
    """
    runtime = load_runtime_config()
    active = await db.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    version = active.scalar_one_or_none()
    metrics = _test_metrics(runtime)
    return {
        **metrics,
        "version_tag": version.version_tag if version else runtime.bundle_schema_version,
        "champion_family": runtime.champion_family,
        "calibration_method": runtime.calibration_method,
        "schema_version": runtime.schema_version,
        "bundle_schema_version": runtime.bundle_schema_version,
        "feature_contract_version": runtime.feature_schema_version,
        "recommendation_schema_version": runtime.recommendation_schema_version,
        "compatibility_status": runtime.compatibility_status,
        "threshold_policy": {
            "operating_threshold": runtime.operating_threshold,
            "operating_policy": runtime.operating_policy,
            "risk_tier_thresholds": runtime.risk_tier_thresholds,
        },
        "artifact_freshness": runtime.artifact_freshness,
        "warnings": runtime.warnings,
    }


@router.get("/drift")
async def model_drift(_user: CurrentUser) -> dict[str, Any]:
    """
    Return model drift monitoring data including PSI references and score shifts.

    Combines the drift_reference_snapshot (training-time feature distributions)
    with the drift_reference_summary (holdout performance and monitoring notes).

    Args:
        _user: Authenticated user.

    Returns:
        Dict with drift summary, PSI references, score histograms, and notes.
    """
    runtime = load_runtime_config()
    snapshot = runtime.drift_reference_snapshot
    summary = runtime.drift_reference_summary
    return {
        "schema_version": summary.get("schema_version") or snapshot.get("schema_version"),
        "model_family": summary.get("model_family") or snapshot.get("model_family"),
        "calibration_method": summary.get("calibration_method") or snapshot.get("calibration_method"),
        "n_features": summary.get("n_features") or snapshot.get("n_features"),
        "drift_summary": summary,
        "psi_references": {
            "feature_columns_hash": snapshot.get("feature_columns_hash"),
            "feature_column_version": snapshot.get("feature_column_version"),
            "psi_ready_score_raw": snapshot.get("psi_ready_score_raw"),
            "feature_distribution_train": snapshot.get("feature_distribution_train"),
        },
        "score_histograms": snapshot.get("score_distribution") or {},
        "baseline_metrics_holdout": summary.get("baseline_metrics_holdout")
        or snapshot.get("baseline_metrics_holdout")
        or {},
        "monitoring_notes": summary.get("monitoring_notes") or snapshot.get("monitoring_notes") or [],
        "artifact_freshness": runtime.artifact_freshness,
    }


@router.get("/stability")
async def model_stability(_user: CurrentUser) -> dict[str, Any]:
    """
    Return cross-validation stability metrics for all candidate model families.

    Includes CV mean/std for PR-AUC, ROC-AUC, and Brier score per family, along
    with the candidate benchmark comparison and selection rationale from the
    training pipeline.

    Args:
        _user: Authenticated user.

    Returns:
        Dict with CV metrics, family comparison, selection rationale.
    """
    runtime = load_runtime_config()
    stability = runtime.model_stability_summary
    by_family = stability.get("by_family") or {}
    cv = {
        family: {
            "pr_auc_mean": metrics.get("pr_auc", {}).get("mean"),
            "pr_auc_std": metrics.get("pr_auc", {}).get("std"),
            "roc_auc_mean": metrics.get("roc_auc", {}).get("mean"),
            "roc_auc_std": metrics.get("roc_auc", {}).get("std"),
            "brier_mean": metrics.get("brier_score", {}).get("mean"),
            "brier_std": metrics.get("brier_score", {}).get("std"),
        }
        for family, metrics in by_family.items()
    }
    selection = runtime.champion_manifest.get("selection") or {}
    return {
        "generated_at_utc": stability.get("generated_at_utc"),
        "method": stability.get("method"),
        "cv_mean_std": cv,
        "family_comparison": runtime.champion_manifest.get("candidate_benchmark") or [],
        "selection_rationale": selection.get("selection_rationale") or selection,
        "champion_family": runtime.champion_family,
        "schema_version": runtime.schema_version,
    }


@router.get("/governance")
async def model_governance(_user: CurrentUser) -> dict[str, Any]:
    """
    Return governance validation status for all runtime artifacts.

    Reports schema compatibility checks for the model bundle, SHAP Parquet,
    and recommendation Parquet, plus artifact freshness and calibration health.

    Args:
        _user: Authenticated user.

    Returns:
        Dict with compatibility status, validation reports, and governance metadata.
    """
    runtime = load_runtime_config()
    return {
        "schema_compatibility": runtime.validation,
        "feature_contract_version": runtime.feature_schema_version,
        "artifact_validation": runtime.model_compatibility,
        "shap_compatibility": runtime.validation.get("shap"),
        "recommendation_compatibility": runtime.validation.get("recommendations"),
        "compatibility_status": runtime.compatibility_status,
        "artifact_freshness": runtime.artifact_freshness,
        "threshold_policies": runtime.champion_manifest.get("threshold_policies") or {},
        "calibration_health": {
            "method": runtime.calibration_method,
            "summary": runtime.calibration_summary.get("selection")
            or runtime.champion_manifest.get("selected_calibration"),
        },
        "production_notes": runtime.recommendation_manifest.get("production_cautions") or [],
    }


@router.get("/monitoring")
async def model_monitoring(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    """Backward-compatible alias for older dashboards — delegates to /health."""
    return await model_health(db, _user)
