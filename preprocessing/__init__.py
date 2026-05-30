"""Preprocessing package for raw telecom CSV data cleaning and validation.

Pipeline position:
  Consumes raw Persian CSV exports -> produces a canonical cleaned parquet.

Workflow stage:
  **Training** — this is the sole preprocessing entry point; downstream
  modeling reads the canonical parquet and applies its own transforms.

Key invariants:
  - No winsorization, imputation, scaling, or feature engineering.
  - All Persian categorical tokens are mapped to English canonical tokens.
  - The cleaned dataset preserves raw observed spend untouched.
  - QC/operational flags are appended but never alter observed values.
  - Bilingual display labels are exported alongside the cleaned data.
"""

from preprocessing.labels import (
    COLUMN_BUSINESS_DESCRIPTION_EN,
    COLUMN_DISPLAY_FA,
    VALUE_DISPLAY_EN_TO_FA,
    VALUE_DISPLAY_FA_TO_EN,
    build_display_label_bundle,
    dumps_display_label_bundle,
)
from preprocessing.pipeline import (
    CLEANED_COLUMN_ORDER,
    CLEANED_COLUMN_SCHEMA,
    PreprocessingArtifacts,
    PreprocessingConfig,
    build_cleaned_frame,
    enforce_cleaned_dtypes,
    load_raw_csv,
    run_preprocessing,
)
from preprocessing.text import normalize_column_name, normalize_text_token
from preprocessing.validators import (
    PreprocessingValidationError,
    ValidationPolicy,
    ValidationReport,
    apply_duplicate_subscriber_policy,
)
from preprocessing.qc import QCReporter, QCArtifact

__all__ = [
    "CLEANED_COLUMN_ORDER",
    "CLEANED_COLUMN_SCHEMA",
    "COLUMN_BUSINESS_DESCRIPTION_EN",
    "COLUMN_DISPLAY_FA",
    "PreprocessingArtifacts",
    "PreprocessingConfig",
    "PreprocessingValidationError",
    "QCArtifact",
    "QCReporter",
    "ValidationPolicy",
    "ValidationReport",
    "VALUE_DISPLAY_EN_TO_FA",
    "VALUE_DISPLAY_FA_TO_EN",
    "apply_duplicate_subscriber_policy",
    "build_cleaned_frame",
    "build_display_label_bundle",
    "dumps_display_label_bundle",
    "enforce_cleaned_dtypes",
    "load_raw_csv",
    "normalize_column_name",
    "normalize_text_token",
    "run_preprocessing",
]
