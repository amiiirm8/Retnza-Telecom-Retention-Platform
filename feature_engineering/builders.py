"""
Telecom feature engineering pipeline.

This module orchestrates the transformation of canonical cleaned subscriber
data into a flat DataFrame of ML-ready features.  Feature construction is
organised in five conceptual layers (predictive, business semantic,
demographic, spend/revenue, interactions), each implemented as a private
``_build_*`` function.  The public entry point is :func:`build_features`.

Pipeline position : Feature engineering layer, after cleaning (Task 2), before training (Task 5).
Workflow stages   : training (``fit_*`` + ``build_features``) and inference
                    (``build_features`` only with pre-fitted thresholds).
Key invariants    :
  - Cleaned business columns are never mutated (read-only inputs).
  - Tri-state encoding (1/0/-1) preserves the not-eligible vs not-adopted
    distinction.
  - All engineered dtypes are deterministic (int8 / float64).
  - Train-fitted thresholds (monthly_spend_q75, lifetime_arpu_q75) must
    be fitted on the training split only and passed at build time to
    prevent leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_engineering.constants import (
    ADVANCED_ECOSYSTEM_MIN_COUNT,
    ADVANCED_GEN_MIN_ORDINAL,
    COMMUNICATION_COLUMNS,
    DEFAULT_BILL_SHOCK_RATIO,
    ECOSYSTEM_COLUMNS,
    ECOSYSTEM_SUPERAPP_COLUMNS,
    GEN_MAP,
    LOW_ENGAGEMENT_DIGITAL_MAX,
    PREPAID_LOW_TENURE_MONTHS,
    REVENUE_RISK_HIGH,
    REVENUE_RISK_LOW,
    REVENUE_RISK_MEDIUM,
    REVENUE_RISK_PREMIUM,
    SENIOR_AGE_MIN,
    TENURE_BIN_EDGES,
    VAS_SERVICE_COLUMNS,
    YOUNG_AGE_MAX,
)
from feature_engineering.helpers import (
    age_to_bucket,
    birth_month_to_ordinal,
    count_yes_among_capable,
    ensure_int8,
    lifetime_arpu,
    tri_state_adoption_flag,
    yes_no_flag,
    yes_only_binary_score,
)
from feature_engineering.registry import (
    ENGINEERED_FEATURE_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    get_feature_metadata,
    get_model_feature_columns,
)

# Re-export contract for downstream imports.
__all__ = [
    "MODEL_FEATURE_COLUMNS",
    "ENGINEERED_FEATURE_COLUMNS",
    "build_features",
    "fit_monthly_spend_q75",
    "fit_lifetime_arpu_q75",
    "get_model_feature_columns",
    "get_feature_metadata",
]


def fit_monthly_spend_q75(train_df: pd.DataFrame) -> float:
    """Fit the 75th-percentile monthly spend threshold on the training split.

    This threshold is used downstream by :func:`_build_spend_layer` to
    create ``high_monthly_spend_flag``.  Fitting on the training split
    only (never on the full dataset) is the mechanism that prevents
    label leakage from the inference or test splits.  If this function
    were called on the full dataset, high-spend flags on test rows
    would implicitly know the training distribution.

    Args:
        train_df: Training partition of the cleaned subscriber table.
            Must contain the column ``monthly_spend_toman``.

    Returns:
        The 75th percentile of monthly spend (toman).
    """
    return float(train_df["monthly_spend_toman"].quantile(0.75))


def fit_lifetime_arpu_q75(train_df: pd.DataFrame) -> float:
    """Fit the 75th-percentile lifetime ARPU threshold on the training split.

    Analogous to :func:`fit_monthly_spend_q75`: the computed threshold is
    used by ``_build_spend_layer`` to create ``high_value_customer_flag``
    and the ``revenue_risk_segment``.  Must be fitted on train only.

    Args:
        train_df: Training partition of the cleaned subscriber table.
            Must contain ``cumulative_spend_toman`` and ``sim_tenure_months``.

    Returns:
        The 75th percentile of lifetime ARPU (toman per month).
    """
    arpu = lifetime_arpu(train_df["cumulative_spend_toman"], train_df["sim_tenure_months"])
    return float(arpu.quantile(0.75))


def _capable_mask(df: pd.DataFrame) -> pd.Series:
    """Derive boolean mask for data-capable subscribers (3G+).

    If the cleaned data already contains an ``is_data_capable`` column
    (the canonical path), it is used directly.  Otherwise falls back to
    a heuristic: ``mobile_data_generation != "2G"``.  This fallback
    exists to support unit tests and ad-hoc runs against data that has
    not been through the full cleaning pipeline.

    Returns:
        Boolean Series: True for subscribers on 3G/4G/5G networks.
    """
    if "is_data_capable" in df.columns:
        return df["is_data_capable"].astype(bool)
    return df["mobile_data_generation"].ne("2G")


def _build_predictive_layer(
    df: pd.DataFrame,
    *,
    capable: pd.Series,
) -> pd.DataFrame:
    """Layer 1 — statistical / predictive features.

    This layer computes features that are simple arithmetic or ordinal
    transformations of the raw numeric/ordinal columns: ARPU, spend
    ratios, tenure bucketing, network generation ordinal, and basic
    VAS adoption counts.  No interaction terms or business-rules are
    applied here — those belong in Layers 2–4.

    Args:
        df: Cleaned subscriber DataFrame.
        capable: Boolean mask for data-capable subscribers (3G+).

    Returns:
        DataFrame with Layer 1 features.
    """
    out = pd.DataFrame(index=df.index)
    tenure = df["sim_tenure_months"].clip(lower=0)

    # Lifetime ARPU: cumulative spend per tenure month.
    # Using log1p on both spend and ARPU before summing creates a
    # spend_intensity_score that is approximately log-spend + log-ARPU,
    # which compresses the heavy right tail of telecom spend data.
    out["lifetime_arpu_toman"] = lifetime_arpu(
        df["cumulative_spend_toman"], tenure
    )
    out["log_monthly_spend_toman"] = np.log1p(df["monthly_spend_toman"].astype("float64"))
    out["monthly_to_lifetime_arpu_ratio"] = (
        df["monthly_spend_toman"].astype("float64")
        / np.maximum(out["lifetime_arpu_toman"], 1.0)
    )
    out["spend_intensity_score"] = (
        out["log_monthly_spend_toman"] + np.log1p(out["lifetime_arpu_toman"])
    ).astype("float64")

    # Tenure binned into lifecycle stages (edges inclusive on left).
    # Using ordinal labels (not one-hot) so tree splits can find
    # contiguous stage thresholds (e.g. "tenure < 12 months").
    out["tenure_bucket"] = (
        pd.cut(tenure, bins=TENURE_BIN_EDGES, labels=[0, 1, 2, 3, 4]).astype("int8")
    )
    out["early_lifecycle_flag"] = (tenure <= 12).astype("int8")
    # is_data_capable is repeated here as a feature so that tree models
    # can split on it directly (see constants.CLEANED_INPUT_COLUMNS for
    # the design rationale).
    out["is_data_capable"] = capable.astype("int8")
    out["is_prepaid"] = df["sim_card_type"].eq("prepaid").astype("int8")
    out["mobile_gen_ordinal"] = df["mobile_data_generation"].map(GEN_MAP).astype("int8")

    # VAS adoption: count of "yes" among capable subscribers.
    # Non-capable rows receive -1 (STRUCTURAL_NA) because a zero count
    # would conflate "not eligible" with "eligible but zero".
    vas_yes = df[list(VAS_SERVICE_COLUMNS)].eq("yes")
    out["vas_adoption_count"] = np.where(
        capable, vas_yes.sum(axis=1), -1
    ).astype("int8")
    out["zero_vas_capable_flag"] = (
        capable & (out["vas_adoption_count"] == 0)
    ).astype("int8")
    out["volte_non_adopter_capable"] = (
        capable & df["volte_service"].eq("no")
    ).astype("int8")

    return out


def _build_business_semantic_layer(
    df: pd.DataFrame,
    *,
    capable: pd.Series,
) -> pd.DataFrame:
    """Layer 2 — explicit telecom service semantics.

    This layer translates raw service columns (superapps, VoLTE, roaming,
    cloud, etc.) into business-meaningful flags using tri-state encodings.
    It also computes composite scores (``digital_engagement_score``,
    ``ecosystem_service_count``) that summarise the breadth of a
    subscriber's digital relationship with the operator.

    Design note: individual service flags are kept alongside aggregate
    scores so that tree models can choose between fine-grained splits
    (e.g. "Rubika flag = 1") and coarse-grained splits (e.g. "ecosystem
    count >= 2").

    Args:
        df: Cleaned subscriber DataFrame.
        capable: Boolean mask for data-capable subscribers (3G+).

    Returns:
        DataFrame with Layer 2 features.
    """
    out = pd.DataFrame(index=df.index)

    # Tri-state flags for VAS services (yes / no / structural N/A).
    # hamrahman_user_flag is the exception: operator_app_usage has no
    # "no_data_service" state, so it uses binary yes_no_flag.
    out["rubika_user_flag"] = tri_state_adoption_flag(df["superapp_social"], capable)
    out["ewano_user_flag"] = tri_state_adoption_flag(df["superapp_financial"], capable)
    out["hamrahman_user_flag"] = yes_no_flag(df["operator_app_usage"])
    out["operator_app_user"] = out["hamrahman_user_flag"]  # legacy alias
    out["volte_user_flag"] = tri_state_adoption_flag(df["volte_service"], capable)
    out["roaming_user_flag"] = tri_state_adoption_flag(df["intl_roaming_package"], capable)
    out["cloud_storage_user_flag"] = tri_state_adoption_flag(
        df["operator_cloud_storage"], capable
    )
    out["night_package_user_flag"] = tri_state_adoption_flag(
        df["night_data_package"], capable
    )

    # Digital engagement score is a sum of adoption indicators.
    # We intentionally use yes_only_binary_score (not tri_state_adoption_flag)
    # because -1 would reduce the sum aggregation, misleadingly signalling
    # "negative" engagement on non-capable rows.  For operator_app_usage the
    # capable mask is None since it's a simple binary column.
    # Note: ecosystem_yes_cols variable is unused but kept for documentation.
    ecosystem_yes_cols = [c for c in ECOSYSTEM_COLUMNS if c != "operator_app_usage"]
    out["digital_engagement_score"] = (
        yes_only_binary_score(df["operator_app_usage"])
        + yes_only_binary_score(df["superapp_social"], capable)
        + yes_only_binary_score(df["superapp_financial"], capable)
        + yes_only_binary_score(df["volte_service"], capable)
    ).astype("int8")

    # Count-based breadth metrics for ecosystem and VAS adoption.
    out["ecosystem_service_count"] = count_yes_among_capable(
        df, list(ECOSYSTEM_SUPERAPP_COLUMNS) + ["operator_app_usage"], capable
    )
    out["communication_service_count"] = count_yes_among_capable(
        df, list(COMMUNICATION_COLUMNS), capable
    )

    # Individual engagement flags for the two superapps.
    out["financial_engagement_flag"] = (
        capable & df["superapp_financial"].eq("yes")
    ).astype("int8")
    out["entertainment_social_engagement_flag"] = (
        capable & df["superapp_social"].eq("yes")
    ).astype("int8")

    # Advanced adopter: capable, with sufficient ecosystem breadth AND
    # modern network generation.  Both conditions must hold because
    # adopting many services on a 3G connection is a different behaviour
    # from doing so on a 5G connection (the latter signals higher
    # investment willingness).
    out["advanced_service_adopter_flag"] = (
        capable
        & (out["ecosystem_service_count"] >= ADVANCED_ECOSYSTEM_MIN_COUNT)
        & (df["mobile_data_generation"].map(GEN_MAP) >= ADVANCED_GEN_MIN_ORDINAL)
    ).astype("int8")

    return out


def _build_demographic_layer(df: pd.DataFrame) -> pd.DataFrame:
    """Layer 3 — demographic features for explainability.

    Demographic features (age buckets, birth month ordinal, gender) are
    kept as a separate layer because they:
      1. Do not depend on the ``capable`` mask (no tri-state concerns).
      2. Serve primarily model-explainability and fairness-monitoring
         purposes rather than predictive lift.
      3. Use binary gender flags (one per category) rather than a single
         categorical column so that tree-based models can split on each
         direction independently.

    Args:
        df: Cleaned subscriber DataFrame (must contain ``age``, ``gender``,
            and ``birth_month_persian``).

    Returns:
        DataFrame with Layer 3 features.
    """
    out = pd.DataFrame(index=df.index)
    # Persian month → ordinal 1..12 for SHAP explainability.
    out["birth_month_ordinal"] = birth_month_to_ordinal(df["birth_month_persian"])
    out["age_bucket"] = age_to_bucket(df["age"])
    out["young_user_flag"] = (df["age"] <= YOUNG_AGE_MAX).astype("int8")
    out["senior_user_flag"] = (df["age"] >= SENIOR_AGE_MIN).astype("int8")
    # One-hot-like binary columns (not a single categorical) so that
    # tree splits can act on individual gender directions.
    out["gender_female"] = df["gender"].eq("female").astype("int8")
    out["gender_male"] = df["gender"].eq("male").astype("int8")
    return out


def _build_spend_layer(
    df: pd.DataFrame,
    pred: pd.DataFrame,
    sem: pd.DataFrame,
    *,
    monthly_spend_q75: float | None,
    lifetime_arpu_q75: float | None,
    bill_shock_ratio: float,
) -> pd.DataFrame:
    """Layer 4 — business-semantic spend / revenue abstractions.

    This layer produces high-level spend flags and a composite revenue-risk
    segmentation.  All flags are derived from Layer 1 (pred) outputs plus
    the raw spend columns — they do not access the raw data independently
    except for monthly spend (which is needed directly for threshold comparison).

    When thresholds are ``None`` (e.g. at inference time before train-fit
    values are known), the corresponding flags default to 0 / the medium
    risk segment.  This allows the pipeline to produce a valid (if less
    informative) feature set without fitted values.

    Args:
        df: Cleaned subscriber DataFrame.
        pred: Output of :func:`_build_predictive_layer` (contains ARPU, ratio).
        sem: Output of :func:`_build_business_semantic_layer` (engagement score).
        monthly_spend_q75: 75th percentile of monthly spend (train-fitted).
            ``None`` disables the high-spend tier flag.
        lifetime_arpu_q75: 75th percentile of lifetime ARPU (train-fitted).
            ``None`` disables the high-value flag and the revenue-risk
            segmentation.
        bill_shock_ratio: Ratio threshold for ``possible_bill_shock_flag``.

    Returns:
        DataFrame with Layer 4 features.
    """
    out = pd.DataFrame(index=df.index)
    arpu = pred["lifetime_arpu_toman"]

    # High monthly spend: flagged when monthly spend >= train Q75.
    # When threshold is None (e.g. production without fitted value),
    # default to 0 to avoid NaN or mid-air failures.
    if monthly_spend_q75 is not None:
        out["high_monthly_spend_flag"] = (
            df["monthly_spend_toman"] >= monthly_spend_q75
        ).astype("int8")
    else:
        out["high_monthly_spend_flag"] = pd.Series(0, index=df.index, dtype="int8")

    # Bill shock: a short-term monthly cost that is disproportionately
    # high relative to the subscriber's lifetime average.  This is a
    # well-known churn indicator in telecom.
    out["possible_bill_shock_flag"] = (
        pred["monthly_to_lifetime_arpu_ratio"] >= bill_shock_ratio
    ).astype("int8")

    # High lifetime value customer flag (ARPU >= train Q75).
    if lifetime_arpu_q75 is not None:
        out["high_value_customer_flag"] = (arpu >= lifetime_arpu_q75).astype("int8")
    else:
        out["high_value_customer_flag"] = pd.Series(0, index=df.index, dtype="int8")

    # Double-low flag: low monthly spend (< 50% of Q75) AND low
    # digital engagement.  Captures subscribers who are both low-value
    # and disengaged — highest churn risk.
    if monthly_spend_q75 is not None:
        low_monthly = df["monthly_spend_toman"] < monthly_spend_q75 * 0.5
    else:
        low_monthly = pd.Series(False, index=df.index)

    out["low_spend_low_engagement_flag"] = (
        low_monthly & (sem["digital_engagement_score"] <= LOW_ENGAGEMENT_DIGITAL_MAX)
    ).astype("int8")

    # Revenue risk segment (ordinal, explainability-oriented).
    # Ordinal (0/1/2/3) rather than one-hot so that SHAP summary plots
    # can show a monotonic "higher segment = higher risk" direction.
    segment = pd.Series(REVENUE_RISK_MEDIUM, index=df.index, dtype="int8")
    if lifetime_arpu_q75 is not None and monthly_spend_q75 is not None:
        segment[arpu < lifetime_arpu_q75 * 0.5] = REVENUE_RISK_LOW
        segment[
            (arpu >= lifetime_arpu_q75 * 0.5)
            & (arpu < lifetime_arpu_q75)
            & ~out["high_monthly_spend_flag"].astype(bool)
        ] = REVENUE_RISK_MEDIUM
        segment[
            (arpu >= lifetime_arpu_q75) | out["high_monthly_spend_flag"].astype(bool)
        ] = REVENUE_RISK_HIGH
        segment[
            (arpu >= lifetime_arpu_q75)
            & out["high_monthly_spend_flag"].astype(bool)
            & (sem["digital_engagement_score"] >= 2)
        ] = REVENUE_RISK_PREMIUM
    out["revenue_risk_segment"] = segment

    return out


def _build_interaction_layer(
    df: pd.DataFrame,
    pred: pd.DataFrame,
    sem: pd.DataFrame,
    spend: pd.DataFrame,
) -> pd.DataFrame:
    """Layer 5 — telecom retention interaction patterns.

    This layer computes feature crosses (interactions) between attributes
    from different layers.  The crossed features capture segment-specific
    behaviours that are more predictive than any single attribute:

      - SIM type (prepaid/postpaid) × network generation
      - SIM type × tenure
      - App adoption × service adoption
      - High value × low engagement (a classic "at risk" signal)

    Interaction features are kept in their own layer so they can be
    reviewed, added, or removed independently without touching the
    base-layer logic.

    Args:
        df: Cleaned subscriber DataFrame.
        pred: Output of :func:`_build_predictive_layer`.
        sem: Output of :func:`_build_business_semantic_layer`.
        spend: Output of :func:`_build_spend_layer`.

    Returns:
        DataFrame with Layer 5 features.
    """
    out = pd.DataFrame(index=df.index)
    prepaid = pred["is_prepaid"] == 1
    postpaid = ~prepaid

    # Prepaid on 5G: these subscribers have access to the fastest network
    # but may churn if they cannot afford the associated data plans.
    out["prepaid_5g_risk_flag"] = (
        prepaid & df["mobile_data_generation"].eq("5G")
    ).astype("int8")
    # Prepaid with very short tenure (≤ 6 months): high churn risk window.
    out["prepaid_low_tenure_flag"] = (
        prepaid & (df["sim_tenure_months"] <= PREPAID_LOW_TENURE_MONTHS)
    ).astype("int8")
    # Prepaid with high monthly spend: counterintuitive (prepaid is
    # usually low-spend) and may signal pain-point behaviour.
    out["prepaid_high_spend_flag"] = (
        prepaid & spend.get("high_monthly_spend_flag", pd.Series(0, index=df.index)).eq(1)
    ).astype("int8")

    # Cross: Hamrah Man app user AND VoLTE user.  Both are sticky
    # services; having both signals deeper operator lock-in.
    out["app_and_volte_user"] = (
        (sem["hamrahman_user_flag"] == 1) & (sem["volte_user_flag"] == 1)
    ).astype("int8")

    # High lifetime value but very low digital engagement: revenue at risk.
    out["high_value_low_engagement_flag"] = (
        spend.get("high_value_customer_flag", pd.Series(0, index=df.index)).eq(1)
        & (sem["digital_engagement_score"] <= LOW_ENGAGEMENT_DIGITAL_MAX)
    ).astype("int8")

    # Advanced network (4G/5G) but very narrow ecosystem adoption (≤ 1).
    # These subscribers have the infrastructure for digital services but
    # have not adopted them — a retention opportunity.
    # Replace -1 with 0 for the comparison so that non-capable rows do
    # not incorrectly trigger this flag.
    out["advanced_network_low_engagement_flag"] = (
        (pred["mobile_gen_ordinal"] >= ADVANCED_GEN_MIN_ORDINAL)
        & (sem["ecosystem_service_count"].replace(-1, 0) <= 1)
    ).astype("int8")

    out["young_prepaid_user_flag"] = (
        prepaid & (df["age"] <= YOUNG_AGE_MAX)
    ).astype("int8")

    out["high_spend_postpaid_flag"] = (
        postpaid
        & spend.get("high_monthly_spend_flag", pd.Series(0, index=df.index)).eq(1)
    ).astype("int8")

    return out


def build_features(
    df: pd.DataFrame,
    monthly_spend_q75: float | None = None,
    lifetime_arpu_q75: float | None = None,
    bill_shock_ratio: float = DEFAULT_BILL_SHOCK_RATIO,
) -> pd.DataFrame:
    """Engineer the full feature set from a canonical cleaned subscriber table.

    This is the primary public entry point for the feature-engineering
    pipeline.  It composes five specialised builder layers and attaches
    their outputs as new columns on a **copy** of the input DataFrame.
    The original cleaned columns are never mutated.

    Workflow:
      1. Validate that required base columns exist.
      2. Derive the ``capable`` mask (data-capable subscribers).
      3. Build each feature layer sequentially (some layers consume
         outputs from earlier layers).
      4. Concatenate all engineered features.
      5. Attach them to a copy of the cleaned data.
      6. Enforce deterministic dtypes (int8 / float64).

    Leakage prevention:
      ``monthly_spend_q75`` and ``lifetime_arpu_q75`` must be fitted
      on the training split exclusively (see :func:`fit_monthly_spend_q75`
      and :func:`fit_lifetime_arpu_q75`).  When passed as ``None``, the
      corresponding flags default to 0 / medium risk — this is safe for
      inference but loses information.

    Args:
        df: Cleaned subscriber DataFrame from Task 2.  Must contain at
            minimum ``sim_tenure_months``, ``monthly_spend_toman``, and
            ``cumulative_spend_toman``.
        monthly_spend_q75: 75th percentile of monthly spend, fitted on
            the training split.  ``None`` disables high-spend tier flags.
        lifetime_arpu_q75: 75th percentile of lifetime ARPU, fitted on
            the training split.  ``None`` disables high-value flags.
        bill_shock_ratio: Threshold for ``possible_bill_shock_flag``
            (monthly / lifetime ARPU ratio).  Default is 2.0.

    Returns:
        A **copy** of the input DataFrame with all engineered feature
        columns attached.  The returned DataFrame includes all original
        cleaned columns plus new columns from each builder layer.

    Raises:
        ValueError: If any of the three required base columns are missing.
    """
    missing = [c for c in ("sim_tenure_months", "monthly_spend_toman", "cumulative_spend_toman") if c not in df.columns]
    if missing:
        raise ValueError(f"build_features missing required columns: {missing}")

    capable = _capable_mask(df)

    pred = _build_predictive_layer(df, capable=capable)
    sem = _build_business_semantic_layer(df, capable=capable)
    demo = _build_demographic_layer(df)
    spend = _build_spend_layer(
        df, pred, sem,
        monthly_spend_q75=monthly_spend_q75,
        lifetime_arpu_q75=lifetime_arpu_q75,
        bill_shock_ratio=bill_shock_ratio,
    )
    inter = _build_interaction_layer(df, pred, sem, spend)

    engineered = pd.concat([pred, sem, demo, spend, inter], axis=1)

    # Attach without mutating cleaned business fields.
    out = df.copy()
    for col in engineered.columns:
        out[col] = engineered[col]

    # Passthrough raw numerics used directly in model.
    if "age" not in engineered.columns:
        out["age"] = df["age"]
    if "sim_tenure_months" not in engineered.columns:
        out["sim_tenure_months"] = df["sim_tenure_months"]

    _enforce_feature_dtypes(out)
    return out


def _enforce_feature_dtypes(df: pd.DataFrame) -> None:
    """Enforce deterministic dtypes on all engineered feature columns (in-place).

    The model contract requires exact dtypes (int8 for categorical/binary/
    ordinal features, float64 for continuous features).  This function
    guarantees that every column in ``MODEL_FEATURE_COLUMNS`` has the
    expected dtype, regardless of upstream dtype promotion that may occur
    during pandas operations (e.g. ``pd.cut`` sometimes returns int64,
    nullable Int8, or object).

    Non-engineered raw pass-through columns (age, sim_tenure_months) are
    excluded from this enforcement; they retain their original int64 dtype
    from the cleaning stage.

    Args:
        df: DataFrame to modify in-place.  Only columns listed in the
            model feature contract are cast.

    Returns:
        None (modifies ``df`` in place).
    """
    int8_cols = [c for c in MODEL_FEATURE_COLUMNS if c not in (
        "age", "sim_tenure_months",
        "lifetime_arpu_toman", "monthly_to_lifetime_arpu_ratio",
        "log_monthly_spend_toman", "spend_intensity_score",
    )]
    for col in int8_cols:
        if col in df.columns:
            df[col] = ensure_int8(df[col])
    for col in ("lifetime_arpu_toman", "monthly_to_lifetime_arpu_ratio", "log_monthly_spend_toman", "spend_intensity_score"):
        if col in df.columns:
            df[col] = df[col].astype("float64")
