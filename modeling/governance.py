"""Model artifact governance, compatibility checks, and lifecycle management.

Provides the validation layer that ensures champion bundles, SHAP parquet files,
and other artifacts are compatible with the current feature contract. Also
handles legacy artifact detection, archiving, and ecosystem auditing.

Pipeline position: consumed by champion.py (during bundle creation), explainability.py
  (SHAP export), and scoring.py (production inference validation).
Workflow stage: governance / lifecycle (cross-cutting).
Key invariants:
  - Bundles with n_features <= LEGACY_FEATURE_COUNT_MAX (25) are BLOCKED — they
    use the old ~18-feature contract and must be retrained.
  - Feature column comparison is strict: stored features must exactly match the
    current registry (extra or missing columns both fail).
  - Archiving is copy-only (soft deprecation) — artifacts are never deleted.
  - Schema version bumps require explicit increment in config.py constants.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from feature_engineering.builders import get_model_feature_columns
from feature_engineering.constants import SCHEMA_VERSION as FE_SCHEMA_VERSION

from modeling.config import (
    CHAMPION_BUNDLE_SCHEMA,
    FEATURE_SCHEMA_EXPECTED,
    LEGACY_FEATURE_COUNT_MAX,
    MODELING_SCHEMA_VERSION,
    OUTPUT_ARCHIVE,
    OUTPUT_CHAMPION,
    OUTPUT_EXPLAINABILITY,
    OUTPUT_GOVERNANCE,
)


class ModelArtifactError(RuntimeError):
    """Raised when a saved model bundle is incompatible with the current feature contract.

    Attributes:
        report: Detailed compatibility report with errors and warnings.
    """

    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


def expected_feature_columns() -> list[str]:
    """Return the current expected feature column list from the feature registry.

    Returns:
        List of feature column names as defined by get_model_feature_columns().
    """
    return get_model_feature_columns()


def validate_champion_bundle(bundle: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    """Verify that a champion joblib bundle matches the current 47-feature registry.

    Checks:
      - Presence of base_model, calibrator/calibration_method keys.
      - Feature column count and exact match against the current registry.
      - Bundle schema version compatibility.
      - Legacy feature count rejection (n_features <= LEGACY_FEATURE_COUNT_MAX).

    Args:
        bundle: The loaded champion bundle dict.
        strict: If True (default), raises ModelArtifactError on any error.
            If False, returns the report with errors listed but no exception raised.

    Returns:
        A dict with 'compatible' (bool), 'warnings' (list), 'errors' (list).

    Raises:
        ModelArtifactError: If strict=True and any compatibility errors are found.

    Side effects: None.
    """
    report: dict[str, Any] = {
        "compatible": True,
        "warnings": [],
        "errors": [],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    expected = expected_feature_columns()
    n_expected = len(expected)

    if "base_model" not in bundle:
        report["errors"].append("Missing base_model in bundle")
    if "calibrator" not in bundle and "calibration_method" not in bundle:
        report["warnings"].append("No calibrator wrapper — legacy bundle shape")

    stored = bundle.get("feature_columns") or bundle.get("model_feature_columns")
    if not stored:
        report["errors"].append("Missing feature_columns in bundle")
    else:
        stored_list = list(stored)
        report["n_stored_features"] = len(stored_list)
        report["n_expected_features"] = n_expected
        if stored_list != expected:
            missing = sorted(set(expected) - set(stored_list))
            extra = sorted(set(stored_list) - set(expected))
            report["compatible"] = False
            report["errors"].append(
                f"Feature schema mismatch: missing={missing[:8]}, extra={extra[:8]}. "
                "Retrain champion on task4-v2 features."
            )

    schema = bundle.get("schema_version") or bundle.get("bundle_schema")
    if schema and schema != CHAMPION_BUNDLE_SCHEMA:
        report["warnings"].append(
            f"Bundle schema {schema!r} != current {CHAMPION_BUNDLE_SCHEMA!r}; retrain required"
        )

    n_feat = bundle.get("n_features") or (len(stored) if stored else 0)
    if n_feat and n_feat <= LEGACY_FEATURE_COUNT_MAX:
        report["compatible"] = False
        report["errors"].append(
            f"Artifact has {n_feat} features (legacy ~18 contract). BLOCKED — retrain required."
        )

    report["feature_engineering_schema"] = FE_SCHEMA_VERSION
    report["expected_fe_schema"] = FEATURE_SCHEMA_EXPECTED
    report["expected_modeling_schema"] = MODELING_SCHEMA_VERSION

    if strict and report["errors"]:
        report["compatible"] = False
        raise ModelArtifactError("; ".join(report["errors"]), report)

    return report


def validate_shap_parquet(path: Path, expected_features: list[str] | None = None) -> dict[str, Any]:
    """Ensure a SHAP parquet file has the expected shap_<feature> columns.

    Reads the parquet, checks that every expected feature has a corresponding
    shap_<feature> column, and flags extra legacy columns.

    Args:
        path: Path to the SHAP parquet file.
        expected_features: List of expected feature names. If None, uses
            expected_feature_columns().

    Returns:
        A dict with 'compatible' (bool), 'warnings' (list), 'errors' (list).
    """
    import pandas as pd

    report: dict[str, Any] = {"path": str(path), "compatible": True, "warnings": [], "errors": []}
    if not path.is_file():
        report["compatible"] = False
        report["errors"].append("SHAP file missing")
        return report

    full = pd.read_parquet(path)
    shap_cols = [c for c in full.columns if c.startswith("shap_")]
    expected = expected_features or expected_feature_columns()
    expected_shap = {f"shap_{f}" for f in expected}
    missing = expected_shap - set(shap_cols)
    extra = set(shap_cols) - expected_shap
    if missing:
        report["compatible"] = False
        report["errors"].append(f"SHAP missing columns for {len(missing)} features")
    if extra and len(extra) > 5:
        report["warnings"].append(f"SHAP has {len(extra)} extra legacy columns")
    return report


def audit_artifact_ecosystem() -> dict[str, Any]:
    """Scan output directories for stale, incompatible, or legacy artifacts.

    Checks:
      - champion_model.joblib: loads and validates against current registry.
      - champion_manifest.json: checks schema version.
      - subscriber_shap_values.parquet / subscriber_shap_test.parquet: checks SHAP columns.

    Returns:
        A dict with 'artifacts' list, 'stale_warnings', and 'action_required' list.
    """
    expected = expected_feature_columns()
    audit: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_n_features": len(expected),
        "expected_bundle_schema": CHAMPION_BUNDLE_SCHEMA,
        "artifacts": [],
        "stale_warnings": [],
        "action_required": [],
    }

    champion_path = OUTPUT_CHAMPION / "champion_model.joblib"
    if champion_path.is_file():
        try:
            bundle = joblib.load(champion_path)
            rep = validate_champion_bundle(bundle, strict=False)
            audit["artifacts"].append({"type": "champion", "path": str(champion_path), **rep})
            if not rep.get("compatible", True):
                audit["action_required"].append("Retrain champion — bundle incompatible")
        except ModelArtifactError as e:
            audit["artifacts"].append({"type": "champion", "compatible": False, "errors": [str(e)]})
            audit["action_required"].append("Retrain champion")

    manifest_path = OUTPUT_CHAMPION / "champion_manifest.json"
    if manifest_path.is_file():
        m = json.loads(manifest_path.read_text())
        if m.get("schema_version") != MODELING_SCHEMA_VERSION:
            audit["stale_warnings"].append(
                f"champion_manifest schema {m.get('schema_version')} != {MODELING_SCHEMA_VERSION}"
            )

    for shap_name in ("subscriber_shap_values.parquet", "subscriber_shap_test.parquet"):
        sp = OUTPUT_EXPLAINABILITY / shap_name
        if sp.is_file():
            audit["artifacts"].append(
                {"type": "shap", "name": shap_name, **validate_shap_parquet(sp, expected)}
            )

    return audit


def archive_legacy_artifacts(dry_run: bool = False) -> list[str]:
    """Archive known-invalid legacy bundles to outputs/archive/ with timestamp.

    Artifacts with n_features <= LEGACY_FEATURE_COUNT_MAX are detected,
    copied to OUTPUT_ARCHIVE with a timestamp prefix, and accompanied by a
    .deprecated.json marker file. The originals are NOT deleted — this is a
    soft deprecation for audit trail purposes.

    Args:
        dry_run: If True, only return the paths that would be archived without
            performing any file operations.

    Returns:
        List of destination paths (actual or would-be).

    Side effects: Copies files and writes .deprecated.json markers (unless dry_run).
    """
    OUTPUT_ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived: list[str] = []
    candidates = [
        OUTPUT_CHAMPION / "champion_model.joblib",
        OUTPUT_EXPLAINABILITY / "subscriber_shap_values.parquet",
    ]
    for src in candidates:
        if not src.is_file():
            continue
        if src.suffix == ".joblib":
            try:
                b = joblib.load(src)
                n = b.get("n_features") or len(b.get("feature_columns", []))
                if n > LEGACY_FEATURE_COUNT_MAX:
                    continue
            except Exception:
                pass
        dest = OUTPUT_ARCHIVE / f"{stamp}_{src.name}"
        if not dry_run:
            shutil.copy2(src, dest)
            (OUTPUT_ARCHIVE / f"{stamp}_{src.name}.deprecated.json").write_text(
                json.dumps(
                    {
                        "original": str(src),
                        "archived_to": str(dest),
                        "reason": "legacy_feature_schema",
                        "utc": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        archived.append(str(dest))
    return archived


def bundle_metadata(
    model_family: str,
    feature_columns: list[str],
    calibration_method: str,
    split_meta: dict[str, Any],
    selection: dict[str, Any],
    *,
    stability_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard governance metadata block for manifests and joblib sidecars.

    This block is embedded in the champion bundle and manifest to provide a
    self-describing record of how the model was trained, selected, and calibrated.

    Args:
        model_family: Name of the selected champion model family.
        feature_columns: List of feature column names used by the model.
        calibration_method: Calibration method selected ('none', 'sigmoid', 'isotonic').
        split_meta: Metadata dict from the SplitBundle (churn rates, n per split, etc.).
        selection: The selection rationale dict from select_champion_with_tolerance().
        stability_summary: Optional stability summary dict for CV PR-AUC per family.

    Returns:
        dict with schema versions, feature info, split metadata, selection rationale,
        and retrain_required_if triggers.
    """
    meta: dict[str, Any] = {
        "schema_version": CHAMPION_BUNDLE_SCHEMA,
        "modeling_schema_version": MODELING_SCHEMA_VERSION,
        "model_family": model_family,
        "n_features": len(feature_columns),
        "feature_columns": feature_columns,
        "feature_engineering_schema": FE_SCHEMA_VERSION,
        "calibration_method": calibration_method,
        "split": split_meta,
        "selection_rationale": selection,
        "retrain_required_if": [
            "feature_engineering schema changes",
            "MODEL_FEATURE_COLUMNS count changes",
            "preprocessing tri-state semantics change",
            "modeling schema_version bump",
        ],
    }
    if stability_summary:
        meta["cv_stability_pr_auc"] = {
            f: stability_summary["by_family"][f]["pr_auc"]
            for f in stability_summary.get("by_family", {})
            if "pr_auc" in stability_summary["by_family"][f]
        }
    return meta


def write_compatibility_report(audit: dict[str, Any] | None = None) -> Path:
    """Write the artifact ecosystem audit to outputs/governance/model_compatibility.json.

    Args:
        audit: The result of audit_artifact_ecosystem(). If None, runs the audit fresh.

    Returns:
        Path to the written JSON file.

    Side effects: Creates OUTPUT_GOVERNANCE directory and writes JSON.
    """
    OUTPUT_GOVERNANCE.mkdir(parents=True, exist_ok=True)
    audit = audit or audit_artifact_ecosystem()
    path = OUTPUT_GOVERNANCE / "model_compatibility.json"
    path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    return path
