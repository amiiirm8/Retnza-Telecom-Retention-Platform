"""Shared analytics configuration — all paths from existing pipeline artifacts.

Workflow stage: reporting-time. All paths reference artifacts produced by the
modeling pipeline (recommendations, SHAP values, champion model, features) and
define the output locations for analytics and dashboard artifacts.

Pipeline position: configuration root, imported by every analytics module.
Produces no artifacts on its own.

Key invariants:
  - Paths are derived from modeling.config, guaranteeing schema alignment.
  - RECOMMENDATIONS_PATH, SHAP_VALUES_PATH, and FEATURES_PATH must exist
    before analytics can run (validated by governance_checks).
  - OUTPUT_ANALYTICS and OUTPUT_DASHBOARD are created by each module at write
    time; no top-level mkdir needed.
"""

from __future__ import annotations

from modeling.config import (
    OUTPUT_CHAMPION,
    OUTPUT_EXPLAINABILITY,
    OUTPUT_GOVERNANCE,
    PROJECT_ROOT,
    FEATURES_PATH,
)

_RECOMMENDATIONS_DIR = PROJECT_ROOT / "outputs" / "recommendations"

OUTPUT_ANALYTICS = PROJECT_ROOT / "outputs" / "analytics"
OUTPUT_DASHBOARD = PROJECT_ROOT / "outputs" / "dashboard"

RECOMMENDATIONS_PATH = _RECOMMENDATIONS_DIR / "subscriber_recommendations.parquet"
RECOMMENDATIONS_MANIFEST_PATH = _RECOMMENDATIONS_DIR / "recommendation_manifest.json"
CHAMPION_PATH = OUTPUT_CHAMPION / "champion_model.joblib"
CHAMPION_MANIFEST_PATH = OUTPUT_CHAMPION / "champion_manifest.json"
SHAP_VALUES_PATH = OUTPUT_EXPLAINABILITY / "subscriber_shap_values.parquet"
SHAP_MANIFEST_PATH = OUTPUT_EXPLAINABILITY / "explainability_manifest.json"
GOVERNANCE_REPORT_PATH = OUTPUT_GOVERNANCE / "model_compatibility.json"

ANALYTICS_SCHEMA_VERSION = "analytics-v1"
