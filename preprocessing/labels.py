"""Bilingual display labels for reporting and dashboards.

Pipeline position:
  Consumed by pipeline.run_preprocessing to write display_labels.json
  alongside the cleaned parquet. Also consumed by QCReporter.finalize.

Workflow stage:
  **Reporting + Governance** — the label bundle is never used during
  modeling; it exists solely for downstream BI tools and stakeholder exports.

Key invariants:
  - Canonical cleaned data stays in English. Persian strings are presentation-only.
  - All value map keys are strings (JSON-safe serialization; int keys are
    stringified via _stringify_value_keys before export).
  - VALUE_DISPLAY_FA_TO_EN is computed programmatically from
    VALUE_DISPLAY_EN_TO_FA — the two maps are kept in sync.
  - COLUMN_BUSINESS_DESCRIPTION_EN is the single source of truth for
    stakeholder-facing definitions (docs, tooltips, data dictionaries).
"""

from __future__ import annotations

import json
from typing import Any

from preprocessing.config import COLUMN_RENAME

# Human-friendly Persian column titles (UI/BI) — not raw CSV header reverse-map.
COLUMN_DISPLAY_FA: dict[str, str] = {
    "subscriber_id": "شناسه مشترک",
    "gender": "جنسیت",
    "age": "سن",
    "birth_month_persian": "ماه تولد (شمسی)",
    "sim_tenure_months": "سابقه سیم‌کارت (ماه)",
    "mobile_data_generation": "نسل اینترنت همراه",
    "intl_roaming_package": "بسته رومینگ بین‌الملل",
    "operator_cloud_storage": "فضای ابری اپراتور",
    "night_data_package": "بسته اینترنت شبانه",
    "volte_service": "سرویس تماس VoLTE",
    "superapp_social": "روبیکا",
    "superapp_financial": "اَوانو",
    "sim_card_type": "نوع سیم‌کارت",
    "operator_app_usage": "استفاده از همراه من",
    "monthly_spend_toman": "هزینه ماهیانه (تومان)",
    "cumulative_spend_toman": "هزینه تجمعی (تومان)",
    "tenure_zero_flag": "پرچم سابقه صفر",
    "billing_definition_ambiguous_flag": "پرچم ابهام تعریف هزینه",
    "is_data_capable": "مشترک دارای سرویس دیتا",
    "churn_binary": "ریزش (بله/خیر)",
}

# English canonical token -> Persian display (string keys throughout).
VALUE_DISPLAY_EN_TO_FA: dict[str, dict[str, str]] = {
    "gender": {"male": "مرد", "female": "زن"},
    "sim_card_type": {"prepaid": "اعتباری", "postpaid": "دائمی"},
    "churn_binary": {"0": "خیر", "1": "بله"},
    "operator_app_usage": {"yes": "بله", "no": "خیر"},
    "mobile_data_generation": {"2G": "2G", "3G": "3G", "4G": "4G", "5G": "5G"},
    "intl_roaming_package": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "operator_cloud_storage": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "night_data_package": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "volte_service": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "superapp_social": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "superapp_financial": {
        "yes": "بله",
        "no": "خیر",
        "no_data_service": "فاقد سرویس دیتا",
    },
    "tenure_zero_flag": {"0": "خیر", "1": "بله"},
    "billing_definition_ambiguous_flag": {"0": "خیر", "1": "بله"},
    "is_data_capable": {"0": "خیر (2G)", "1": "بله"},
}

# Persian display -> English canonical (for inbound UI filters if needed).
VALUE_DISPLAY_FA_TO_EN: dict[str, dict[str, str]] = {
    col: {fa: en for en, fa in mapping.items()}
    for col, mapping in VALUE_DISPLAY_EN_TO_FA.items()
}

# Stakeholder-facing English descriptions (docs, tooltips, exports).
COLUMN_BUSINESS_DESCRIPTION_EN: dict[str, str] = {
    "subscriber_id": "Unique subscriber identifier in the dataset.",
    "gender": "Subscriber gender (male/female).",
    "age": "Subscriber age in years at observation time.",
    "birth_month_persian": "Birth month on the Persian (Shamsi) calendar — retained for reporting.",
    "sim_tenure_months": "Months since SIM activation (customer tenure on network).",
    "mobile_data_generation": "Highest mobile data network generation: 2G, 3G, 4G, or 5G.",
    "sim_card_type": "SIM billing type: prepaid (اعتباری) or postpaid (دائمی).",
    "monthly_spend_toman": "Monthly billed amount in Iranian Toman for the observation window.",
    "cumulative_spend_toman": "Lifetime cumulative billed amount in Toman (business definition varies).",
    "operator_app_usage": "Usage of the operator mobile app (همراه من): yes/no.",
    "superapp_social": "Engagement with Rubika social superapp (روبیکا): yes/no/no_data_service.",
    "superapp_financial": "Engagement with Ewano financial superapp (اَوانو): yes/no/no_data_service.",
    "volte_service": "VoLTE voice-over-LTE service subscription state.",
    "intl_roaming_package": "International roaming package subscription.",
    "operator_cloud_storage": "Operator cloud storage product subscription.",
    "night_data_package": "Night-time mobile data package subscription.",
    "churn_binary": "Historical churn label: 1=left, 0=stayed (training target).",
    "tenure_zero_flag": "QC flag: tenure is zero months (infant account edge case).",
    "billing_definition_ambiguous_flag": "QC flag: tenure=0, cumulative=0, monthly>0 (ambiguous billing).",
    "is_data_capable": "Operational flag: 1 if non-2G (data/VAS fields apply); 0 for 2G structural N/A.",
}

# Raw CSV Persian headers for audit crosswalk.
# Inverted from COLUMN_RENAME so that given an English column name you can
# look up the original Persian header that appeared in the source CSV.
COLUMN_RAW_HEADER_FA: dict[str, str] = {v: k for k, v in COLUMN_RENAME.items()}


def _stringify_value_keys(mapping: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Ensure all value-map keys are strings (JSON-safe).

    Int keys like 0/1 that appear in churn_binary, tenure_zero_flag, etc.
    are converted to "0"/"1" so that json.dump does not write numeric keys.

    Args:
        mapping: Nested dict of column -> {value -> display}.

    Returns:
        Deep copy with all leaf keys stringified.
    """
    return {
        col: {str(k): v for k, v in vals.items()}
        for col, vals in mapping.items()
    }


def build_display_label_bundle() -> dict[str, Any]:
    """Build a JSON-serializable bundle of all display labels for downstream tools.

    The bundle includes:
      - column_display_fa: Persian display names for each column.
      - column_raw_header_fa: Original Persian CSV header per column.
      - value_display_en_to_fa: English canonical -> Persian display.
      - value_display_fa_to_en: Persian display -> English canonical (for UI filters).
      - column_business_description_en: Stakeholder-facing English definitions.

    Returns:
        dict ready for json.dumps (keys are all strings, values are
        JSON-serializable).

    Raises:
        No explicit exceptions, but relies on the module-level
        dictionaries being well-formed.
    """
    return {
        "schema_version": "display-labels-v2",
        "column_display_fa": COLUMN_DISPLAY_FA,
        "column_raw_header_fa": COLUMN_RAW_HEADER_FA,
        "value_display_en_to_fa": _stringify_value_keys(VALUE_DISPLAY_EN_TO_FA),
        "value_display_fa_to_en": _stringify_value_keys(VALUE_DISPLAY_FA_TO_EN),
        "column_business_description_en": COLUMN_BUSINESS_DESCRIPTION_EN,
        "note": "Canonical parquet uses English tokens; apply these maps only at presentation time.",
    }


def dumps_display_label_bundle(indent: int = 2) -> str:
    """Serialize the display label bundle to pretty-printed JSON.

    Uses ensure_ascii=False so that Persian/Farsi characters in the
    output are human-readable rather than \\uXXXX escapes.

    Args:
        indent: Indentation level for the JSON output (default 2).

    Returns:
        Formatted JSON string with Persian text preserved.
    """
    return json.dumps(build_display_label_bundle(), indent=indent, ensure_ascii=False)
