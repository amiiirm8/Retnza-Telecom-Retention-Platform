"""
Retnza — Telecom feature engineering pipeline (Feature engineering layer).

This package transforms canonical cleaned subscriber data into a curated
set of ML-ready features used for churn prediction. It operates in both
training and inference modes: thresholds (Q75) are fit on the training
split and passed at build time to prevent leakage.

Pipeline position : Feature engineering layer (after cleaning, before model training).
Workflow stages   : training (fit + build) and inference (build only).
Key invariants    :
  - Cleaned business columns are never mutated (read-only inputs).
  - Tri-state encoding (1=yes, 0=no, -1=structural N/A) preserves
    the distinction between "not adopted" and "not eligible".
  - All engineered dtypes are deterministic (int8 / float64).
  - The feature registry is the single source of truth for the model
    contract and is versioned via SCHEMA_VERSION.
"""

from feature_engineering.builders import (
    build_features,
    fit_lifetime_arpu_q75,
    fit_monthly_spend_q75,
    get_feature_metadata,
    get_model_feature_columns,
)
from feature_engineering.registry import (
    MODEL_FEATURE_COLUMNS,
    MODEL_FEATURE_GROUPS,
    get_business_labels,
)
from feature_engineering.validators import (
    FeatureEngineeringValidationError,
    validate_featured_frame,
)

__all__ = [
    "MODEL_FEATURE_COLUMNS",
    "MODEL_FEATURE_GROUPS",
    "FeatureEngineeringValidationError",
    "build_features",
    "fit_lifetime_arpu_q75",
    "fit_monthly_spend_q75",
    "get_business_labels",
    "get_feature_metadata",
    "get_model_feature_columns",
    "validate_featured_frame",
]
