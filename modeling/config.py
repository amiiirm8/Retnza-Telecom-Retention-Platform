"""Modeling layer configuration (Retnza modeling pipeline).

Central constants: paths, schema versions, random seeds, business policy defaults,
champion selection tolerances, risk-band thresholds, and legacy detection parameters.

All modeling submodules import their config from here rather than duplicating values.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
"""Project root (2 levels up from modeling/config.py)."""

# ── Data paths ──────────────────────────────────────────────
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "subscribers_cleaned.parquet"
"""Cleaned subscriber parquet consumed by all modeling tasks."""
FEATURES_PATH = PROJECT_ROOT / "data" / "features" / "subscribers_featured.parquet"
"""Pre-built feature-engineered parquet (alternative input for inference-only pipelines)."""

# ── Output directories ──────────────────────────────────────
OUTPUT_BASELINES = PROJECT_ROOT / "outputs" / "baselines"
"""Baseline benchmarking reports (baseline_results.json)."""
OUTPUT_CHAMPION = PROJECT_ROOT / "outputs" / "champion"
"""Champion model bundle, manifest, stability/calibration/drift summaries."""
OUTPUT_EXPLAINABILITY = PROJECT_ROOT / "outputs" / "explainability"
"""SHAP importance CSVs, parquet, beeswarm plots."""
OUTPUT_GOVERNANCE = PROJECT_ROOT / "outputs" / "governance"
"""Governance / compatibility / lifecycle reports."""
OUTPUT_ARCHIVE = PROJECT_ROOT / "outputs" / "archive"
"""Legacy artifact archive (stale bundles moved here, not deleted)."""

# ── Schema versions (bump on breaking changes) ───────────────
MODELING_SCHEMA_VERSION = "modeling-v4"
"""Modeling pipeline schema version (increment on manifest structure change)."""
FEATURE_SCHEMA_EXPECTED = "task4-v2"
"""Expected feature engineering schema version for validation."""
CHAMPION_BUNDLE_SCHEMA = "champion-bundle-v4"
"""Champion joblib bundle schema version (increment on bundle key change)."""

# ── Determinism ──────────────────────────────────────────────
RANDOM_STATE = 42
"""Global random seed for reproducibility across all modeling tasks."""

# ── Split proportions (TRAIN + VAL + TEST = 1.0) ────────────
TEST_SIZE = 0.15
VAL_SIZE = 0.15
TRAIN_SIZE = 1.0 - TEST_SIZE - VAL_SIZE

# ── Telecom retention threshold policy defaults ─────────────
# These are business-driven: FN cost (missed churner) >> FP cost (false alarm)
# because a missed churner churns permanently while a false alarm costs only a
# retention offer.
MIN_RECALL_CONTACT = 0.75
"""Minimum recall target for the contact policy (catch at least 75% of churners)."""
MIN_PRECISION_CONTACT = 0.50
"""Precision target floor for the contact policy. Not always achievable."""
RECALL_TOLERANCE = 0.02
"""Relaxation band for the recall target (effective floor = MIN_RECALL - RECALL_TOLERANCE)."""
PRECISION_TOLERANCE = 0.05
"""Relaxation band for the precision target."""
DEFAULT_THRESHOLD = 0.5
"""Default binary classification threshold (used for 'default_0.5' policy)."""

# ── Calibrated risk bands (aligned with recommendation.engine) ──
# These thresholds define the tier labels used in CRM / save-offer campaigns.
# They are applied to the CALIBRATED churn probability (not raw).
RISK_TIER_THRESHOLDS: dict[str, float] = {
    "Very High": 0.65,
    "High": 0.30,
    "Medium": 0.15,
    "Low": 0.0,
}

# ── Champion selection tolerances ────────────────────────────
# Champion selection uses a tolerance-band approach: any model within
# CHAMPION_PR_AUC_TOLERANCE_ABS (absolute) or CHAMPION_PR_AUC_TOLERANCE_REL (relative)
# of the best PR-AUC is eligible. Among eligible candidates, we prefer:
#   lower fold std → simpler model (lower rank) → lower Brier
CHAMPION_PRIMARY_METRIC = "pr_auc"
"""Primary metric for champion ranking."""
CHAMPION_CALIBRATION_METRIC = "brier_score"
"""Secondary metric for calibration method selection."""
CHAMPION_PR_AUC_TOLERANCE_ABS = 0.01
"""Absolute PR-AUC tolerance band (±0.01 from best)."""
CHAMPION_PR_AUC_TOLERANCE_REL = 0.02
"""Relative PR-AUC tolerance band (±2% from best)."""
CHAMPION_CALIBRATION_PR_TOLERANCE = 0.01
"""PR-AUC tolerance for calibration method selection (default 0.01)."""

# Simplicity ranking: lower = simpler / more interpretable.
# Used as a tie-breaker in champion selection — simpler models are preferred
# when performance is statistically indistinguishable.
MODEL_SIMPLICITY_RANK: dict[str, int] = {
    "logistic_regression": 1,
    "random_forest": 2,
    "hist_gradient_boosting": 3,
    "lightgbm": 4,
    "xgboost": 5,
    "catboost": 6,
}

# ── Cross-validated stability ───────────────────────────────
# Stability CV runs repeated stratified K-fold on the train+val pool
# (test set is never used for any decision). Multiple seeds detect
# seed-sensitivity of the champion winner.
STABILITY_CV_FOLDS = 5
"""Number of folds per seed."""
STABILITY_CV_SEEDS: tuple[int, ...] = (42, 123, 456)
"""Random seeds for repeated CV (detects seed-sensitivity)."""

# ── Tuning ───────────────────────────────────────────────────
N_RF_TUNING_ITER = 24
"""Number of RandomizedSearchCV iterations for RF tuning."""
N_CV_FOLDS = 3
"""Number of CV folds for RandomizedSearchCV (not the same as STABILITY_CV_FOLDS)."""

# ── Legacy artifact detection ───────────────────────────────
# Bundles with n_features <= LEGACY_FEATURE_COUNT_MAX are from the old
# ~18-feature contract and must be rejected/archived.
LEGACY_FEATURE_COUNT_MAX = 25
"""Max feature count for legacy bundle detection. Current contract is 47 features."""
