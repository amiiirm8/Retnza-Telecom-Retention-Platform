"""\nFeature registry: lineage, families, and model contract (feature engineering).

This module is the **single source of truth** for the feature schema used
by the churn prediction model.  It defines:

  - ``FeatureSpec`` — a frozen dataclass describing one feature (layer,
    family, dtype, description, business question, leakage safety, and
    whether it is included in the model).
  - ``FEATURE_REGISTRY`` — the ordered tuple of all ``FeatureSpec`` entries
    that determines the contract between the engineering pipeline and the
    model training / inference code.
  - ``MODEL_FEATURE_COLUMNS`` — the deterministic ordered list of column
    names that the model expects (derived from the registry).
  - ``MODEL_FEATURE_GROUPS`` — logical groupings of features for reporting
    and governance.

Workflow stage : governance / contract definition (used during both
                 training and inference).

Key invariants:
  - Every feature in ``MODEL_FEATURE_COLUMNS`` must be produced by
    ``build_features`` and accepted by ``validate_featured_frame``.
  - The registry is versioned via ``SCHEMA_VERSION`` (in constants).
  - Adding or removing a feature requires updating the registry, the
    builder layer, and the validator — the registry is the first place
    to check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FeatureLayer = Literal["predictive", "business_semantic", "interaction", "demographic", "spend"]
FeatureFamily = Literal[
    "spend",
    "lifecycle",
    "network",
    "vas",
    "ecosystem",
    "demographic",
    "segment",
    "interaction",
]


@dataclass(frozen=True)
class FeatureSpec:
    """Immutable specification of a single feature in the registry.

    Each ``FeatureSpec`` documents one column produced by the engineering
    pipeline.  Frozenness guarantees that the registry cannot be mutated
    after creation — the model contract is immutable by design.

    Attributes:
        name: Feature column name (must match the DataFrame column exactly).
        layer: Conceptual pipeline layer (predictive, business_semantic,
            interaction, demographic, spend).
        family: Business-domain category (spend, lifecycle, network, vas,
            ecosystem, demographic, segment, interaction).
        dtype: Expected pandas/numpy dtype (``"int8"``, ``"float64"``).
        description: Human-readable one-liner for dashboards and BI.
        business_question: The business question this feature helps answer
            (used for model documentation and SHAP explainability).
        leakage_safe: ``True`` if this feature can be computed without
            looking at the future or the label.  All current features
            are leakage-safe by construction.
        in_model: ``True`` if this feature is included in the model
            feature set.  ``False`` for backward-compatible aliases
            that exist in the DataFrame but are not used as model inputs.
    """
    name: str
    layer: FeatureLayer
    family: FeatureFamily
    dtype: str
    description: str
    business_question: str
    leakage_safe: bool = True
    in_model: bool = True


def _spec(
    name: str,
    layer: FeatureLayer,
    family: FeatureFamily,
    dtype: str,
    description: str,
    business_question: str,
    *,
    in_model: bool = True,
) -> FeatureSpec:
    """Construct a ``FeatureSpec`` with default leakage-safe=True.

    This factory reduces boilerplate in the registry definition below.
    All features created through this function are leakage-safe by
    default (the only kind this pipeline produces).

    Args:
        name: Feature column name.
        layer: Pipeline layer identifier.
        family: Business-domain family.
        dtype: Expected pandas dtype string.
        description: Short description for BI / dashboards.
        business_question: Interpretable business question.
        in_model: Whether to include in the model feature set.

    Returns:
        A frozen ``FeatureSpec`` instance.
    """
    return FeatureSpec(
        name=name,
        layer=layer,
        family=family,
        dtype=dtype,
        description=description,
        business_question=business_question,
        in_model=in_model,
    )


# --- Registry (ordered by layer / family) ---
FEATURE_REGISTRY: tuple[FeatureSpec, ...] = (
    # LAYER 1 — Predictive
    _spec("lifetime_arpu_toman", "predictive", "spend", "float64", "Cumulative spend per month of tenure", "Do spend patterns affect churn?",),
    _spec("monthly_to_lifetime_arpu_ratio", "predictive", "spend", "float64", "Monthly bill vs lifetime ARPU", "Does bill shock vs history raise risk?",),
    _spec("log_monthly_spend_toman", "predictive", "spend", "float64", "log1p(monthly spend)", "Monthly spend level vs churn",),
    _spec("spend_intensity_score", "predictive", "spend", "float64", "Normalized monthly + lifetime ARPU blend", "Spend intensity vs peers",),
    _spec("tenure_bucket", "predictive", "lifecycle", "int8", "Tenure stage 0=new … 4=loyal", "How does tenure affect churn?",),
    _spec("early_lifecycle_flag", "predictive", "lifecycle", "int8", "Tenure ≤ 12 months", "Early lifecycle churn risk",),
    _spec("is_data_capable", "predictive", "network", "int8", "Non-2G (data/VAS eligible)", "Churn among users without data services?",),
    _spec("mobile_gen_ordinal", "predictive", "network", "int8", "2G=0 … 5G=3", "How does network generation affect churn?",),
    _spec("vas_adoption_count", "predictive", "vas", "int8", "# VAS yes among capable; -1 if 2G", "VAS adoption vs churn",),
    _spec("zero_vas_capable_flag", "predictive", "vas", "int8", "Capable but zero VAS", "Low engagement on capable network",),
    _spec("volte_non_adopter_capable", "predictive", "vas", "int8", "Capable, VoLTE=no", "VoLTE non-adoption risk",),
    _spec("is_prepaid", "predictive", "segment", "int8", "Prepaid SIM", "Does SIM type affect churn?",),
    # LAYER 2 — Business semantic (individual services)
    _spec("rubika_user_flag", "business_semantic", "ecosystem", "int8", "Rubika (superapp_social) 1/0/-1", "Does Rubika reduce churn?",),
    _spec("ewano_user_flag", "business_semantic", "ecosystem", "int8", "EWANO (superapp_financial) 1/0/-1", "Does EWANO reduce churn?",),
    _spec("hamrahman_user_flag", "business_semantic", "ecosystem", "int8", "Hamrah Man app 1/0", "Does Hamrah Man improve retention?",),
    _spec("volte_user_flag", "business_semantic", "vas", "int8", "VoLTE adoption 1/0/-1", "Does VoLTE improve retention?",),
    _spec("roaming_user_flag", "business_semantic", "vas", "int8", "Intl roaming 1/0/-1", "Roaming pack adoption",),
    _spec("cloud_storage_user_flag", "business_semantic", "vas", "int8", "Cloud storage 1/0/-1", "Cloud product adoption",),
    _spec("night_package_user_flag", "business_semantic", "vas", "int8", "Night data pack 1/0/-1", "Night pack adoption",),
    _spec("digital_engagement_score", "business_semantic", "ecosystem", "int8", "Sum Hamrah Man+Rubika+EWANO+VoLTE yes", "Digital ecosystem engagement",),
    _spec("ecosystem_service_count", "business_semantic", "ecosystem", "int8", "Count ecosystem yes (capable)", "Ecosystem breadth",),
    _spec("communication_service_count", "business_semantic", "vas", "int8", "Count comms/network VAS yes", "Comms service breadth",),
    _spec("financial_engagement_flag", "business_semantic", "ecosystem", "int8", "EWANO yes on capable", "Financial superapp engagement",),
    _spec("entertainment_social_engagement_flag", "business_semantic", "ecosystem", "int8", "Rubika yes on capable", "Social superapp engagement",),
    _spec("advanced_service_adopter_flag", "business_semantic", "ecosystem", "int8", "≥2 ecosystem + modern network", "Advanced digital adopter",),
    # LAYER 3 — Interactions
    _spec("prepaid_5g_risk_flag", "interaction", "segment", "int8", "Prepaid on 5G", "High-risk prepaid 5G segment",),
    _spec("prepaid_low_tenure_flag", "interaction", "segment", "int8", "Prepaid & tenure ≤6m", "New prepaid churn risk",),
    _spec("prepaid_high_spend_flag", "interaction", "segment", "int8", "Prepaid & high monthly spend", "High-spend prepaid",),
    _spec("app_and_volte_user", "interaction", "ecosystem", "int8", "Hamrah Man + VoLTE yes", "App × VoLTE interaction",),
    _spec("high_value_low_engagement_flag", "interaction", "segment", "int8", "High value, low digital score", "Revenue at risk — low engagement",),
    _spec("advanced_network_low_engagement_flag", "interaction", "network", "int8", "4G/5G but low ecosystem count", "Modern network, low digital uptake",),
    _spec("young_prepaid_user_flag", "interaction", "demographic", "int8", "Prepaid & age ≤30", "Young prepaid segment",),
    _spec("high_spend_postpaid_flag", "interaction", "segment", "int8", "Postpaid & high monthly tier", "High-value postpaid",),
    # Demographic
    _spec("birth_month_ordinal", "demographic", "demographic", "int8", "Persian birth month 1–12", "Birth month / seasonality segments",),
    _spec("age_bucket", "demographic", "demographic", "int8", "Age band ordinal", "Demographic churn patterns",),
    _spec("young_user_flag", "demographic", "demographic", "int8", "Age ≤30", "Young user churn",),
    _spec("senior_user_flag", "demographic", "demographic", "int8", "Age ≥56", "Senior user churn",),
    _spec("gender_female", "demographic", "demographic", "int8", "Gender female", "Gender churn patterns",),
    _spec("gender_male", "demographic", "demographic", "int8", "Gender male", "Gender churn patterns",),
    # Spend / revenue semantics
    _spec("high_monthly_spend_flag", "spend", "spend", "int8", "Monthly ≥ train Q75", "High monthly spend tier",),
    _spec("possible_bill_shock_flag", "spend", "spend", "int8", "Monthly >> lifetime ARPU", "Bill shock approximation",),
    _spec("high_value_customer_flag", "spend", "spend", "int8", "High lifetime ARPU tier", "High-value customer",),
    _spec("low_spend_low_engagement_flag", "spend", "ecosystem", "int8", "Low spend & low digital score", "Low value + low engagement",),
    _spec("revenue_risk_segment", "spend", "segment", "int8", "0=low … 3=premium revenue band", "Revenue risk segmentation",),
    # Backward-compatible alias (same as hamrahman on yes/no column)
    _spec("operator_app_user", "business_semantic", "ecosystem", "int8", "Hamrah Man yes (legacy name)", "Hamrah Man engagement",),
    # Raw passthrough for model (optional — keep age/tenure in model)
    _spec("age", "predictive", "demographic", "int64", "Customer age", "Age vs churn",),
    _spec("sim_tenure_months", "predictive", "lifecycle", "int64", "SIM tenure months", "Tenure vs churn",),
)

FEATURE_BY_NAME: dict[str, FeatureSpec] = {s.name: s for s in FEATURE_REGISTRY}

MODEL_FEATURE_GROUPS: dict[str, list[str]] = {
    "predictive_core": [
        "age",
        "sim_tenure_months",
        "lifetime_arpu_toman",
        "monthly_to_lifetime_arpu_ratio",
        "log_monthly_spend_toman",
        "spend_intensity_score",
        "tenure_bucket",
        "early_lifecycle_flag",
        "is_data_capable",
        "mobile_gen_ordinal",
        "vas_adoption_count",
        "zero_vas_capable_flag",
        "volte_non_adopter_capable",
        "is_prepaid",
    ],
    "ecosystem_semantic": [
        "rubika_user_flag",
        "ewano_user_flag",
        "hamrahman_user_flag",
        "volte_user_flag",
        "roaming_user_flag",
        "cloud_storage_user_flag",
        "night_package_user_flag",
        "digital_engagement_score",
        "ecosystem_service_count",
        "communication_service_count",
        "financial_engagement_flag",
        "entertainment_social_engagement_flag",
        "advanced_service_adopter_flag",
        "operator_app_user",
    ],
    "interactions": [
        "prepaid_5g_risk_flag",
        "prepaid_low_tenure_flag",
        "prepaid_high_spend_flag",
        "app_and_volte_user",
        "high_value_low_engagement_flag",
        "advanced_network_low_engagement_flag",
        "young_prepaid_user_flag",
        "high_spend_postpaid_flag",
    ],
    "demographic": [
        "birth_month_ordinal",
        "age_bucket",
        "young_user_flag",
        "senior_user_flag",
        "gender_female",
        "gender_male",
    ],
    "spend_revenue": [
        "high_monthly_spend_flag",
        "possible_bill_shock_flag",
        "high_value_customer_flag",
        "low_spend_low_engagement_flag",
        "revenue_risk_segment",
    ],
}

# Deterministic ordered model contract (union of groups).
# Order is determined by the registry layout, which groups features by
# layer and family for readability.  This list drives dtype enforcement
# in _enforce_feature_dtypes and column validation in validate_featured_frame.
MODEL_FEATURE_COLUMNS: list[str] = [
    spec.name for spec in FEATURE_REGISTRY if spec.in_model
]

# Engineered-only columns (excludes raw age/tenure duplicated from cleaned).
# These are a subset of MODEL_FEATURE_COLUMNS — the raw passthrough columns
# (age, sim_tenure_months) are still in the model feature set but are not
# considered "engineered" for reporting purposes.
ENGINEERED_FEATURE_COLUMNS: list[str] = [
    c for c in MODEL_FEATURE_COLUMNS if c not in ("age", "sim_tenure_months")
]


def get_model_feature_columns() -> list[str]:
    """Return an independent copy of the model feature column names.

    Returns a new list to prevent callers from accidentally mutating
    the module-level ``MODEL_FEATURE_COLUMNS`` constant.

    Returns:
        Ordered list of column names that constitute the model contract.
    """
    return list(MODEL_FEATURE_COLUMNS)


def get_feature_metadata() -> dict[str, Any]:
    """Export the full feature registry as a dictionary for manifest / BI tooling.

    The returned dict is not serialisable itself but is intended to be
    written as JSON by the caller (e.g. ``FeatureQCReporter.save_group_registry``).

    Returns:
        Dictionary with schema version, feature counts, groups, and
        the full ordered list of feature specs.
    """
    return {
        "schema_version": "task4-v2-registry",
        "n_features": len(FEATURE_REGISTRY),
        "n_model_features": len(MODEL_FEATURE_COLUMNS),
        "groups": MODEL_FEATURE_GROUPS,
        "features": [
            {
                "name": s.name,
                "layer": s.layer,
                "family": s.family,
                "dtype": s.dtype,
                "description": s.description,
                "business_question": s.business_question,
                "in_model": s.in_model,
                "leakage_safe": s.leakage_safe,
            }
            for s in FEATURE_REGISTRY
        ],
    }


def get_business_labels() -> dict[str, str]:
    """Return a mapping of feature names to human-readable descriptions.

    Designed for use in SHAP summary plots, feature-importance dashboards,
    and BI reporting — anywhere a technical column name needs a plain-
    language label.

    Returns:
        Dict keyed by ``feature_name`` with description values.
    """
    return {s.name: s.description for s in FEATURE_REGISTRY}
