"""Paths, vocabularies, policies, and canonical dtype contract for Task 2 preprocessing.

Pipeline position:
  Configuration constants consumed by all other preprocessing modules.
  This module is a leaf dependency (no intra-package imports beyond text.py).

Workflow stage:
  **Training + Inference** — both stages share the same config values.

Key invariants:
  - All persisted paths are derived from PROJECT_ROOT; consumers should not
    hardcode relative paths.
  - Type aliases (DuplicateSubscriberIdPolicy, NullHandlingPolicy) are
    Literal strings for auditable serialization.
  - CLEANED_DTYPE_CONTRACT is the single source of truth for parquet dtypes.
  - BACKWARD-COMPATIBLE ALIASES are preserved at the module bottom.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from preprocessing.text import build_normalized_lookup, normalize_text_token

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RAW_CSV = PROJECT_ROOT / "data" / "raw" / "MCI_Challenge_FinalDataset.csv"
"""Path to the raw input CSV.

Place the CSV at this location before running the pipeline::

    mkdir -p data/raw
    cp /path/to/MCI_Challenge_FinalDataset.csv data/raw/
"""
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
INFERENCE_DIR = DATA_DIR / "inference"
QC_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "preprocessing"

SCHEMA_VERSION = "task2-v4"
VALIDATION_VERSION = "validators-v2"

# --- Configurable policies (defaults preserve strict source contract) ---

DuplicateSubscriberIdPolicy = Literal["fail_fast", "keep_first", "keep_last"]
"""Policy for resolving duplicate subscriber_id rows in the raw CSV."""

NullHandlingPolicy = Literal["strict_fail", "allow_selected_columns", "warn_only"]
"""Policy for handling null values during preprocessing."""

DEFAULT_DUPLICATE_SUBSCRIBER_ID_POLICY: DuplicateSubscriberIdPolicy = "fail_fast"
"""Default: raise on any duplicate subscriber_id (strict source contract)."""

DEFAULT_NULL_HANDLING_POLICY: NullHandlingPolicy = "strict_fail"
"""Default: raise on any null anywhere in the dataset."""

# Persian solar month names — retained in cleaned output for BI/reporting;
# ordinal encoding is deferred to the modeling pipeline.
PERSIAN_MONTH_ORDER: dict[str, int] = {
    "فروردین": 1,
    "اردیبهشت": 2,
    "خرداد": 3,
    "تیر": 4,
    "مرداد": 5,
    "شهریور": 6,
    "مهر": 7,
    "آبان": 8,
    "آذر": 9,
    "دی": 10,
    "بهمن": 11,
    "اسفند": 12,
}

# Raw Persian maps (source CSV tokens — raw unnormalized keys).
GENDER_MAP_RAW: dict[str, str] = {"مرد": "male", "زن": "female"}
SIM_TYPE_MAP_RAW: dict[str, str] = {"اعتباری": "prepaid", "دائمی": "postpaid"}
TARGET_MAP_RAW: dict[str, int] = {"خیر": 0, "بله": 1}
TRI_PERSIAN_TO_ENGLISH_RAW: dict[str, str] = {
    "خیر": "no",
    "بله": "yes",
    "فاقد سرویس دیتا": "no_data_service",
}
APP_PERSIAN_TO_ENGLISH_RAW: dict[str, str] = {"خیر": "no", "بله": "yes"}

# Normalized-key lookups for tolerant matching after ``normalize_text_token``.
# These tolerate ZWNJ, Arabic letter variants, and other Unicode quirks
# common in the raw CSV export.
GENDER_MAP: dict[str, str] = build_normalized_lookup(GENDER_MAP_RAW)
SIM_TYPE_MAP: dict[str, str] = build_normalized_lookup(SIM_TYPE_MAP_RAW)
TARGET_MAP: dict[str, int] = {
    normalize_text_token(k): v for k, v in TARGET_MAP_RAW.items()
}
TRI_PERSIAN_TO_ENGLISH: dict[str, str] = build_normalized_lookup(TRI_PERSIAN_TO_ENGLISH_RAW)
APP_PERSIAN_TO_ENGLISH: dict[str, str] = build_normalized_lookup(APP_PERSIAN_TO_ENGLISH_RAW)

# Column rename: Persian header (normalized) -> English snake_case.
# Keys must already be normalized via normalize_column_name before lookup.
# This dict doubles as an audit crosswalk (see labels.COLUMN_RAW_HEADER_FA).
COLUMN_RENAME: dict[str, str] = {
    "شناسه_مشترک": "subscriber_id",
    "جنسیت": "gender",
    "سن": "age",
    "ماه_تولد": "birth_month_persian",
    "سابقه_سیم‌کارت_ماه": "sim_tenure_months",
    "نسل_اینترنت_همراه": "mobile_data_generation",
    "بسته_رومینگ_بین‌الملل": "intl_roaming_package",
    "فضای_ابری_اپراتور": "operator_cloud_storage",
    "بسته_اینترنت_شبانه": "night_data_package",
    "سرویس_تماس_VoLTE": "volte_service",
    "سوپراپ_شبکه اجتماعی": "superapp_social",
    "سوپراپ_خدمات_مالی": "superapp_financial",
    "نوع_سیم‌کارت": "sim_card_type",
    "استفاده_اپلیکیشن_اپراتور": "operator_app_usage",
    "هزینه_ماهیانه_تومان": "monthly_spend_toman",
    "هزینه_کل_تومان": "cumulative_spend_toman",
    "ریزش": "churn_label",
}

TRI_STATE_COLUMNS: tuple[str, ...] = (
    "intl_roaming_package",
    "operator_cloud_storage",
    "night_data_package",
    "volte_service",
    "superapp_social",
    "superapp_financial",
)
"""Columns using tri-state semantics: yes / no / no_data_service.
2G subscribers are structurally N/A for these VAS/data fields."""

ALLOWED_GENDER: frozenset[str] = frozenset({"male", "female"})
ALLOWED_SIM_TYPE: frozenset[str] = frozenset({"prepaid", "postpaid"})
ALLOWED_TRI_STATE: frozenset[str] = frozenset({"yes", "no", "no_data_service"})
ALLOWED_OPERATOR_APP: frozenset[str] = frozenset({"yes", "no"})
ALLOWED_MOBILE_GENERATION: frozenset[str] = frozenset({"2G", "3G", "4G", "5G"})
ALLOWED_BIRTH_MONTHS: frozenset[str] = frozenset(PERSIAN_MONTH_ORDER.keys())
ALLOWED_BIRTH_MONTHS_NORMALIZED: frozenset[str] = frozenset(
    normalize_text_token(m) for m in PERSIAN_MONTH_ORDER
)
"""Normalized aliases of PERSIAN_MONTH_ORDER keys for tolerant matching."""
ALLOWED_CHURN_BINARY: frozenset[int] = frozenset({0, 1})

# Strict canonical dtype contract (cleaned parquet).
# Only numeric/flag columns are listed; string columns keep object dtype.
# This contract is asserted by validators and enforced by enforce_cleaned_dtypes.
CLEANED_DTYPE_CONTRACT: dict[str, str] = {
    "subscriber_id": "int64",
    "age": "int64",
    "sim_tenure_months": "int64",
    "monthly_spend_toman": "int64",
    "cumulative_spend_toman": "int64",
    "churn_binary": "int8",
    "tenure_zero_flag": "int8",
    "billing_definition_ambiguous_flag": "int8",
    "is_data_capable": "int8",
}

AGE_MIN: int = 18
"""Minimum plausible subscriber age (domain constraint)."""
AGE_MAX: int = 120
"""Maximum plausible subscriber age (domain constraint)."""
SIM_TENURE_MAX_MONTHS: int = 120
"""Caps tenure at 10 years; values above trigger a warning but not a failure."""

# Backward-compatible alias for modules that imported the old name.
DUPLICATE_SUBSCRIBER_ID_POLICY = DEFAULT_DUPLICATE_SUBSCRIBER_ID_POLICY
