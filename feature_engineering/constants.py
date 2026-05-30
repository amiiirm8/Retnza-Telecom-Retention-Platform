"""\nConstants for deterministic telecom feature engineering (Feature engineering layer).

This module centralises all configuration values, paths, thresholds,
mappings, and column schemas used by the feature engineering pipeline.
It is the single source of truth for business rules (age bands, tenure
bins, revenue risk segments) and determines the contract between the
cleaned input table and the engineered output.

Key design invariants:
  - All thresholds are fixed (not train-fitted) unless documented
    otherwise (e.g. monthly_spend_q75 is passed at runtime).
  - STRUCTURAL_NA = -1 is the reserved sentinel for tri-state fields
    on 2G / non-data-capable rows, distinguishing "not eligible" from
    "eligible but not adopted".
  - The projective root, data paths, and QC output paths are derived
    once here rather than scattered across callers.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "subscribers_cleaned.parquet"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
FEATURE_QC_DIR = PROJECT_ROOT / "outputs" / "features"

SCHEMA_VERSION = "task4-v2"
FE_VALIDATION_VERSION = "fe-validators-v1"

# Structural sentinel for tri-state fields on 2G / non-data-capable rows.
# We use -1 (not NaN) because:
#   - int8 columns cannot hold NaN without upcasting to float.
#   - -1 is ordinal-safe (it sorts below 0 and 1).
#   - Tree-based models treat -1 as a distinct category, preserving
#     the "not eligible" signal that would be lost with imputation.
STRUCTURAL_NA = -1

# Ordinal mapping for mobile network generations.
# Used both for ordinal features (mobile_gen_ordinal) and as an eligibility
# gate for advanced-service adopters (ADVANCED_GEN_MIN_ORDINAL >= 2 = 4G+).
GEN_MAP: dict[str, int] = {"2G": 0, "3G": 1, "4G": 2, "5G": 3}

# Tenure bins for lifecycle stage bucketing.
# Edges:   -1–6  (new), 6–12 (early), 12–24 (mid), 24–60 (mature), 60–72 (loyal).
# The lower bound -1 ensures rows with tenure=0 / data-entry errors are binned
# into labelled group 0 rather than discarded as NaN.
TENURE_BIN_EDGES = [-1, 6, 12, 24, 60, 72]
TENURE_BIN_LABELS = (0, 1, 2, 3, 4)

AGE_YOUTH_MAX = 25
AGE_YOUNG_ADULT_MAX = 35
AGE_ADULT_MAX = 55
# age > ADULT_MAX -> senior bucket (4)

# Human-readable labels for age_bucket ordinal values (used in reporting only).
AGE_BUCKET_MAP = {
    0: "youth",
    1: "young_adult",
    2: "adult",
    3: "senior",
}

# All VAS / package columns (tri-state).
VAS_SERVICE_COLUMNS: tuple[str, ...] = (
    "intl_roaming_package",
    "operator_cloud_storage",
    "night_data_package",
    "volte_service",
    "superapp_social",
    "superapp_financial",
)

# Digital ecosystem (Rubika, EWANO, Hamrah Man) + VoLTE for engagement score.
ECOSYSTEM_COLUMNS: tuple[str, ...] = (
    "operator_app_usage",
    "superapp_social",
    "superapp_financial",
    "volte_service",
)

ECOSYSTEM_SUPERAPP_COLUMNS: tuple[str, ...] = (
    "superapp_social",
    "superapp_financial",
)

COMMUNICATION_COLUMNS: tuple[str, ...] = (
    "volte_service",
    "intl_roaming_package",
    "night_data_package",
    "operator_cloud_storage",
)

# Canonical cleaned columns required as inputs (not mutated).
CLEANED_INPUT_COLUMNS: tuple[str, ...] = (
    "subscriber_id",
    "gender",
    "age",
    "birth_month_persian",
    "sim_tenure_months",
    "mobile_data_generation",
    *VAS_SERVICE_COLUMNS,
    "sim_card_type",
    "operator_app_usage",
    "monthly_spend_toman",
    "cumulative_spend_toman",
    "tenure_zero_flag",
    "billing_definition_ambiguous_flag",
    # is_data_capable is kept as a first-class feature (not used solely for
    # row filtering) because the model must distinguish "2G subscriber who
    # could not adopt VAS" from "3G+ subscriber who chose not to".  Dropping
    # it would collapse two structurally different populations into one.
    "is_data_capable",
    "churn_binary",
)

# Business thresholds (fixed; train-fitted thresholds passed at runtime).
# These encode domain rules of thumb and are *not* data-driven.  The two Q75
# thresholds (monthly_spend, lifetime_arpu) are deliberately left as runtime
# parameters rather than constants to force explicit train-split fitting,
# preventing leakage from the inference pipeline.
DEFAULT_BILL_SHOCK_RATIO = 2.0          # monthly/lifetime ARPU > 2x → bill shock
LOW_ENGAGEMENT_DIGITAL_MAX = 1          # digital_engagement_score ≤ 1 → low engagement
ADVANCED_GEN_MIN_ORDINAL = 2            # 4G+ required for "advanced adopter"
ADVANCED_ECOSYSTEM_MIN_COUNT = 2        # min ecosystem services for "advanced adopter"
PREPAID_LOW_TENURE_MONTHS = 6           # new prepaid churn risk window
YOUNG_AGE_MAX = 30                      # upper bound for "young user" flag
SENIOR_AGE_MIN = 56                     # lower bound for "senior user" flag

# Revenue risk segment ordinals (explainability-oriented).
# Ordinal encoding rather than one-hot keeps the segmentation monotonic,
# which is friendlier for tree-based models and SHAP summary plots.
REVENUE_RISK_LOW = 0
REVENUE_RISK_MEDIUM = 1
REVENUE_RISK_HIGH = 2
REVENUE_RISK_PREMIUM = 3
