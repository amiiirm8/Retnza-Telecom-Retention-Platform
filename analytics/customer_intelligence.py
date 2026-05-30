"""Customer / demographic intelligence from feature and recommendation artifacts.

Workflow stage: reporting-time (first analytics module, step 1 of 8).

Computes age-cohort, gender, seasonality, and ecosystem-by-demographic
analytics using calibrated and raw risk scores. All wording is associative only
— no causal claims are made about demographics and churn.

Pipeline position: reads feature-schema features and recommendation-engine.
Produces age_cohort_summary.json, gender_analytics.json,
seasonality_analytics.json, ecosystem_demographic_analytics.json, and
age_risk_distribution.parquet.

Key invariants:
  - All metrics describe observed associations in the current snapshot.
  - Calibrated and raw scores are kept separate throughout.
  - Ecosystem adoption is measured as product flags, not inferred engagement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    FEATURES_PATH,
    OUTPUT_ANALYTICS,
    RECOMMENDATIONS_PATH,
)

AGE_COHORT_BINS = [0, 18, 25, 35, 45, 55, 200]
AGE_COHORT_LABELS = ["<18", "18-24", "25-34", "35-44", "45-54", "55+"]
MONTH_LABELS = [
    "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
    "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand",
]


def _safe_mean(s: pd.Series) -> float:
    """Compute mean of a series, returning 0.0 for empty series."""
    return float(s.mean()) if len(s) else 0.0


def _cohort_label(val: int) -> str | None:
    """Map an age integer to its cohort label using AGE_COHORT_BINS."""
    if pd.isna(val):
        return None
    for i, (lo, hi) in enumerate(zip(AGE_COHORT_BINS[:-1], AGE_COHORT_BINS[1:])):
        if lo <= int(val) < hi:
            return AGE_COHORT_LABELS[i]
    return AGE_COHORT_LABELS[-1]


def compute_age_cohort_summary(
    df: pd.DataFrame,
    rec: pd.DataFrame,
) -> dict[str, Any]:
    """Churn risk and ecosystem metrics by age cohort.

    Merges feature and recommendation data, assigns cohort labels, and
    computes per-cohort: n, share_of_base, churn_rate, mean calibrated/raw
    risk, prepaid_ratio, ecosystem_penetration, per-product adoption,
    mean_arpu, mean_tenure, bill_shock_frequency, mean_digital_engagement.

    Args:
        df: Feature DataFrame (feature-schema) containing demographic columns.
        rec: Recommendation DataFrame (recommendation-engine) containing
            churn_probability, churn_probability_raw, etc.

    Returns:
        dict mapping cohort label -> per-cohort metrics dict.
    """
    merged = rec.merge(
        df[["subscriber_id", "age", "is_prepaid", "sim_tenure_months",
            "lifetime_arpu_toman", "possible_bill_shock_flag",
            "digital_engagement_score", "rubika_user_flag",
            "ewano_user_flag", "hamrahman_user_flag",
            "volte_user_flag", "gender_female", "gender_male",
            "birth_month_ordinal"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    merged["_age_cohort"] = merged["age"].apply(_cohort_label)

    cohorts: dict[str, Any] = {}
    for label, grp in merged.groupby("_age_cohort", observed=True):
        n = len(grp)
        p_cal = grp["churn_probability"]
        p_raw = grp.get("churn_probability_raw", pd.Series([0.0] * n))
        cohorts[str(label)] = {
            "n": n,
            "share_of_base": n / len(merged),
            "churn_rate": _safe_mean(p_cal),
            "mean_calibrated_risk": _safe_mean(p_cal),
            "mean_raw_risk": _safe_mean(p_raw),
            "prepaid_ratio": float(grp["is_prepaid"].mean()) if "is_prepaid" in grp else None,
            "ecosystem_penetration": float(
                ((grp.get("rubika_user_flag", 0) == 1) |
                 (grp.get("ewano_user_flag", 0) == 1) |
                 (grp.get("hamrahman_user_flag", 0) == 1)).mean()
            ),
            "rubika_adoption": float((grp.get("rubika_user_flag", -1) == 1).mean()),
            "ewano_adoption": float((grp.get("ewano_user_flag", -1) == 1).mean()),
            "hamrah_man_adoption": float((grp.get("hamrahman_user_flag", 0) == 1).mean()),
            "volte_adoption": float((grp.get("volte_user_flag", -1) == 1).mean()),
            "mean_arpu": _safe_mean(grp["lifetime_arpu_toman"]) if "lifetime_arpu_toman" in grp else None,
            "mean_tenure_months": _safe_mean(grp["sim_tenure_months"]),
            "bill_shock_frequency": float(grp["possible_bill_shock_flag"].mean()) if "possible_bill_shock_flag" in grp else None,
            "mean_digital_engagement": _safe_mean(grp["digital_engagement_score"]),
        }
    return cohorts


def compute_gender_analytics(
    df: pd.DataFrame,
    rec: pd.DataFrame,
) -> dict[str, Any]:
    """Churn risk and ecosystem metrics by gender.

    Merges feature and recommendation data, maps gender_female flag to
    'female'/'male'/'unknown', and computes per-gender: n, share_of_base,
    churn_rate, mean_calibrated_risk, prepaid_ratio, ecosystem_penetration,
    per-product adoption, mean_arpu, mean_tenure, bill_shock_frequency,
    mean_digital_engagement.

    Args:
        df: Feature DataFrame (feature-schema) containing gender flags.
        rec: Recommendation DataFrame (recommendation-engine).

    Returns:
        dict mapping gender label -> per-gender metrics dict.
    """
    merged = rec.merge(
        df[["subscriber_id", "gender_female", "gender_male",
            "is_prepaid", "lifetime_arpu_toman",
            "sim_tenure_months", "digital_engagement_score",
            "possible_bill_shock_flag", "rubika_user_flag",
            "ewano_user_flag", "hamrahman_user_flag",
            "volte_user_flag"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )

    merged["_gender"] = merged["gender_female"].map({1: "female", 0: "male"}).fillna("unknown")

    genders: dict[str, Any] = {}
    for label, grp in merged.groupby("_gender", observed=True):
        n = len(grp)
        p_cal = grp["churn_probability"]
        genders[str(label)] = {
            "n": n,
            "share_of_base": n / len(merged),
            "churn_rate": _safe_mean(p_cal),
            "mean_calibrated_risk": _safe_mean(p_cal),
            "prepaid_ratio": float(grp["is_prepaid"].mean()),
            "ecosystem_penetration": float(
                ((grp.get("rubika_user_flag", 0) == 1) |
                 (grp.get("ewano_user_flag", 0) == 1) |
                 (grp.get("hamrahman_user_flag", 0) == 1)).mean()
            ),
            "rubika_adoption": float((grp.get("rubika_user_flag", -1) == 1).mean()),
            "ewano_adoption": float((grp.get("ewano_user_flag", -1) == 1).mean()),
            "hamrah_man_adoption": float((grp.get("hamrahman_user_flag", 0) == 1).mean()),
            "volte_adoption": float((grp.get("volte_user_flag", -1) == 1).mean()),
            "mean_arpu": _safe_mean(grp["lifetime_arpu_toman"]),
            "mean_tenure_months": _safe_mean(grp["sim_tenure_months"]),
            "bill_shock_frequency": float(grp["possible_bill_shock_flag"].mean()),
            "mean_digital_engagement": _safe_mean(grp["digital_engagement_score"]),
        }
    return genders


def compute_seasonality_analytics(
    df: pd.DataFrame,
    rec: pd.DataFrame,
) -> dict[str, Any]:
    """Birth month seasonality — month-of-year churn associations.

    Uses birth_month_ordinal (1-12 mapped to Persian month labels) to
    compute per-month: n, share_of_base, mean_calibrated_risk,
    prepaid_ratio, mean_digital_engagement, mean_arpu.

    Args:
        df: Feature DataFrame (feature-schema) containing birth_month_ordinal.
        rec: Recommendation DataFrame (recommendation-engine).

    Returns:
        dict mapping Persian month label -> per-month metrics dict.
    """
    merged = rec.merge(
        df[["subscriber_id", "birth_month_ordinal",
            "is_prepaid", "digital_engagement_score",
            "lifetime_arpu_toman"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    merged["_birth_month"] = merged["birth_month_ordinal"].fillna(0).astype(int)

    months: dict[str, Any] = {}
    for ordinal, grp in merged.groupby("_birth_month", observed=True):
        n = len(grp)
        idx = int(ordinal) - 1
        label = MONTH_LABELS[idx] if 0 <= idx < 12 else f"month_{ordinal}"
        months[label] = {
            "n": n,
            "share_of_base": n / len(merged),
            "mean_calibrated_risk": _safe_mean(grp["churn_probability"]),
            "prepaid_ratio": float(grp["is_prepaid"].mean()),
            "mean_digital_engagement": _safe_mean(grp["digital_engagement_score"]),
            "mean_arpu": _safe_mean(grp["lifetime_arpu_toman"]),
        }
    return months


def compute_ecosystem_demographic_analytics(
    df: pd.DataFrame,
    rec: pd.DataFrame,
) -> dict[str, Any]:
    """Ecosystem adoption cross-tabulated by demographic dimensions.

    Computes three cross-tabulations:
      - gender_ecosystem: ecosystem adoption rate, risk, and ARPU by gender.
      - age_ecosystem: ecosystem adoption rate and risk by age cohort.
      - prepaid_ecosystem: ecosystem adoption rate and risk by prepaid/postpaid.

    All metrics are associative comparisons between adopters and non-adopters,
    not causal estimates of ecosystem impact on churn.

    Args:
        df: Feature DataFrame (feature-schema) with demographic and ecosystem flags.
        rec: Recommendation DataFrame (recommendation-engine).

    Returns:
        dict with keys 'gender_ecosystem', 'age_ecosystem',
        'prepaid_ecosystem', each containing per-group nested dicts.
    """
    merged = rec.merge(
        df[["subscriber_id", "age", "gender_female", "gender_male",
            "is_prepaid", "rubika_user_flag",
            "ewano_user_flag", "hamrahman_user_flag",
            "volte_user_flag", "digital_engagement_score",
            "lifetime_arpu_toman", "sim_tenure_months",
            "possible_bill_shock_flag"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )

    merged["_gender"] = merged["gender_female"].map({1: "female", 0: "male"}).fillna("unknown")
    merged["_ecosystem_adopted"] = (
        (merged.get("rubika_user_flag", 0) == 1) |
        (merged.get("ewano_user_flag", 0) == 1) |
        (merged.get("hamrahman_user_flag", 0) == 1)
    ).astype(int)
    merged["_age_cohort"] = merged["age"].apply(_cohort_label)

    interactions: dict[str, Any] = {
        "gender_ecosystem": {},
        "age_ecosystem": {},
        "prepaid_ecosystem": {},
    }

    for gender, grp in merged.groupby("_gender", observed=True):
        eco_on = grp[grp["_ecosystem_adopted"] == 1]
        eco_off = grp[grp["_ecosystem_adopted"] == 0]
        interactions["gender_ecosystem"][str(gender)] = {
            "n": len(grp),
            "ecosystem_adopted_n": int(len(eco_on)),
            "ecosystem_adopted_rate": float(len(eco_on) / max(len(grp), 1)),
            "mean_calibrated_risk_eco_adopted": _safe_mean(eco_on["churn_probability"]),
            "mean_calibrated_risk_eco_non_adopted": _safe_mean(eco_off["churn_probability"]),
            "mean_arpu_eco_adopted": _safe_mean(eco_on["lifetime_arpu_toman"]),
        }

    for cohort, grp in merged.groupby("_age_cohort", observed=True):
        eco_on = grp[grp["_ecosystem_adopted"] == 1]
        eco_off = grp[grp["_ecosystem_adopted"] == 0]
        interactions["age_ecosystem"][str(cohort)] = {
            "n": len(grp),
            "ecosystem_adopted_rate": float(len(eco_on) / max(len(grp), 1)),
            "mean_calibrated_risk_eco_adopted": _safe_mean(eco_on["churn_probability"]),
            "mean_calibrated_risk_eco_non_adopted": _safe_mean(eco_off["churn_probability"]),
        }

    prepaid = merged[merged["is_prepaid"] == 1]
    postpaid = merged[merged["is_prepaid"] == 0]
    for seg_name, seg_df in [("prepaid", prepaid), ("postpaid", postpaid)]:
        eco_on = seg_df[seg_df["_ecosystem_adopted"] == 1]
        eco_off = seg_df[seg_df["_ecosystem_adopted"] == 0]
        interactions["prepaid_ecosystem"][seg_name] = {
            "n": len(seg_df),
            "ecosystem_adopted_rate": float(len(eco_on) / max(len(seg_df), 1)),
            "mean_calibrated_risk_eco_adopted": _safe_mean(eco_on["churn_probability"]),
            "mean_calibrated_risk_eco_non_adopted": _safe_mean(eco_off["churn_probability"]),
        }

    return interactions


def compute_age_risk_distribution(
    df: pd.DataFrame,
    rec: pd.DataFrame,
) -> pd.DataFrame:
    """Age × calibrated risk distribution for dashboard scatter / heatmap.

    Merges age and is_prepaid from features with risk columns from
    recommendations. Adds _age_cohort label for dashboard grouping.

    Args:
        df: Feature DataFrame (feature-schema) with age, is_prepaid.
        rec: Recommendation DataFrame (recommendation-engine) with
            churn_probability, churn_probability_raw, risk_tier, rule_id.

    Returns:
        DataFrame with columns: subscriber_id, age, churn_probability,
        churn_probability_raw, risk_tier, is_prepaid, rule_id, _age_cohort.
    """
    merged = rec.merge(
        df[["subscriber_id", "age", "is_prepaid"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    out = merged[["subscriber_id", "age", "churn_probability", "churn_probability_raw",
                  "risk_tier", "is_prepaid", "rule_id"]].copy()
    out["_age_cohort"] = out["age"].apply(_cohort_label)
    return out


def compute_all_customer_intelligence(
    feature_path: Path = FEATURES_PATH,
    rec_path: Path = RECOMMENDATIONS_PATH,
) -> dict[str, Any]:
    """Orchestrate all demographic and customer intelligence analytics.

    Reads feature and recommendation parquet files, runs all five analytics
    functions (age_cohort, gender, seasonality, ecosystem_demographic,
    age_risk_distribution), and writes JSON/parquet outputs.

    Args:
        feature_path: Path to feature-schema feature parquet.
        rec_path: Path to recommendation-engine parquet.

    Returns:
        dict with schema_version, generated_at_utc, n_subscribers, n_cohorts,
        n_genders, n_seasonality_months, age_risk_distribution_path, and
        disclaimer.

    Side effects:
        Writes five artifacts under OUTPUT_ANALYTICS.
    """
    df = pd.read_parquet(feature_path)
    rec = pd.read_parquet(rec_path)

    age_cohort = compute_age_cohort_summary(df, rec)
    gender = compute_gender_analytics(df, rec)
    seasonality = compute_seasonality_analytics(df, rec)
    ecosystem_demo = compute_ecosystem_demographic_analytics(df, rec)
    age_risk = compute_age_risk_distribution(df, rec)

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_ANALYTICS / "age_cohort_summary.json", "w") as f:
        json.dump(age_cohort, f, indent=2, default=str)
    with open(OUTPUT_ANALYTICS / "gender_analytics.json", "w") as f:
        json.dump(gender, f, indent=2, default=str)
    with open(OUTPUT_ANALYTICS / "seasonality_analytics.json", "w") as f:
        json.dump(seasonality, f, indent=2, default=str)
    with open(OUTPUT_ANALYTICS / "ecosystem_demographic_analytics.json", "w") as f:
        json.dump(ecosystem_demo, f, indent=2, default=str)
    age_risk.to_parquet(OUTPUT_ANALYTICS / "age_risk_distribution.parquet", index=False)

    return {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_subscribers": int(len(rec)),
        "n_cohorts": len(age_cohort),
        "n_genders": len(gender),
        "n_seasonality_months": len(seasonality),
        "age_risk_distribution_path": str(OUTPUT_ANALYTICS / "age_risk_distribution.parquet"),
        # Associative wording required by platform policy: analytics never
        # claims demographics cause churn. All metrics describe snapshot associations.
        "disclaimer": (
            "All metrics describe observed associations in the current snapshot. "
            "They do not establish causal relationships between demographics and churn."
        ),
    }
