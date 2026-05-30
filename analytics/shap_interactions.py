"""SHAP interaction analysis — pairwise feature interaction summaries.

Workflow stage: reporting-time (step 2 of 8, after customer intelligence).

Computes mean interaction SHAP, direction, affected population,
associated churn delta, and narrative summaries for specified feature pairs.
Only reads from existing SHAP artifacts — never re-computes base SHAP.

Pipeline position: reads shap-explainability, feature-schema features, and
recommendation-engine. Produces shap_interaction_summary.json and
shap_interaction_top_pairs.parquet.

Key invariants:
  - Interaction SHAP uses product proxy (SHAP_a * SHAP_b * sign(f_a * f_b)),
    not formal Shapley interaction values. This is an associative heuristic.
  - All narratives say 'associative, not causal'.
  - Only reads from existing SHAP artifacts — no base SHAP recomputation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    FEATURES_PATH,
    OUTPUT_ANALYTICS,
    RECOMMENDATIONS_PATH,
    SHAP_VALUES_PATH,
)

# Predefined feature pairs for interaction analysis. Each tuple is
# (feature_a, feature_b, label). Pairs were selected based on domain
# knowledge of likely second-order associations in telecom churn.
# These are illustrative analytical pairs, not a comprehensive interaction search.
INTERACTION_PAIRS: list[tuple[str, str, str]] = [
    ("is_prepaid", "mobile_gen_ordinal", "prepaid_5g"),
    ("sim_tenure_months", "ecosystem_service_count", "tenure_ecosystem"),
    ("volte_user_flag", "is_data_capable", "volte_data_capable"),
    ("age", "digital_engagement_score", "age_digital_engagement"),
    ("ecosystem_service_count", "is_prepaid", "ecosystem_prepaid"),
    ("possible_bill_shock_flag", "lifetime_arpu_toman", "bill_shock_arpu"),
    ("gender_female", "ecosystem_service_count", "gender_ecosystem"),
    ("is_prepaid", "rubika_user_flag", "prepaid_rubika"),
]


def _safe_mean(s: pd.Series) -> float:
    """Compute mean of a series, returning 0.0 for empty series."""
    return float(s.mean()) if len(s) else 0.0


def _narrative_direction(mean_interaction: float) -> str:
    """Categorize mean interaction SHAP into direction label.

    Thresholds (±0.005) chosen to filter noise around zero; interactions
    within this band are considered neutral. This is a descriptive label,
    not a statistical significance test.

    Args:
        mean_interaction: Mean interaction SHAP value.

    Returns:
        'positive_interaction', 'negative_interaction', or 'neutral'.
    """
    if mean_interaction > 0.005:
        return "positive_interaction"
    if mean_interaction < -0.005:
        return "negative_interaction"
    return "neutral"


def _build_narrative(
    pair_label: str,
    mean_interaction: float,
    affected_pct: float,
    churn_delta: float,
) -> str:
    """Build an associative narrative string for a feature interaction pair.

    Uses 'amplifying'/'dampening' wording and explicitly tags the narrative
    as associative, not causal.

    Args:
        pair_label: Human-readable label for the feature pair.
        mean_interaction: Mean interaction SHAP value.
        affected_pct: Percentage of population with non-zero interaction.
        churn_delta: Mean churn probability difference between high and low
            interaction groups.

    Returns:
        Narrative string.
    """
    direction = "amplifying" if mean_interaction > 0 else "dampening"
    return (
        f"The observed interaction between {pair_label} shows a {direction} pattern "
        f"(mean interaction SHAP: {mean_interaction:.4f}). "
        f"This affects {affected_pct:.1f}% of the population and is associated with "
        f"a churn probability delta of {churn_delta:+.3f} (associative, not causal)."
    )


def compute_shap_interactions(
    shap_path: Path = SHAP_VALUES_PATH,
    feature_path: Path = FEATURES_PATH,
    rec_path: Path = RECOMMENDATIONS_PATH,
) -> dict[str, Any]:
    """Compute interaction SHAP summaries for predefined feature pairs.

    For each pair in INTERACTION_PAIRS, computes:
      - Interaction SHAP proxy: SHAP_a * SHAP_b * sign(f_a * f_b)
      - Mean and std of interaction SHAP
      - Direction label (positive/negative/neutral)
      - Affected population count and percentage
      - Churn probability delta between high and low interaction groups
      - Narrative string (associative wording)

    Args:
        shap_path: Path to subscriber_shap_values.parquet.
        feature_path: Path to feature-schema feature parquet.
        rec_path: Path to recommendation-engine parquet.

    Returns:
        dict with schema_version, generated_at_utc, n_pairs, interactions
        (per-pair results), and disclaimer.

    Side effects:
        Writes shap_interaction_summary.json and
        shap_interaction_top_pairs.parquet to OUTPUT_ANALYTICS.
    """
    shap_df = pd.read_parquet(shap_path)
    fe = pd.read_parquet(feature_path)
    rec = pd.read_parquet(rec_path)

    # Merge SHAP values with feature values and recommendations
    merge_cols = ["subscriber_id"]
    for feat_a, feat_b, _ in INTERACTION_PAIRS:
        merge_cols.extend([feat_a, feat_b])
    merge_cols = list(set(merge_cols))

    merged = shap_df.merge(
        fe[merge_cols].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    merged = merged.merge(
        rec[["subscriber_id", "churn_probability", "risk_tier"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )

    interactions: dict[str, Any] = {}
    top_rows: list[dict[str, Any]] = []

    for feat_a, feat_b, label in INTERACTION_PAIRS:
        shap_a_col = f"shap_{feat_a}"
        shap_b_col = f"shap_{feat_b}"

        if shap_a_col not in shap_df.columns or shap_b_col not in shap_df.columns:
            interactions[label] = {
                "pair": (feat_a, feat_b),
                "note": f"SHAP columns missing for {feat_a} or {feat_b}",
            }
            continue

        shap_a = merged[shap_a_col].values
        shap_b = merged[shap_b_col].values
        feat_a_vals = merged[feat_a].values if feat_a in merged.columns else np.zeros(len(merged))
        feat_b_vals = merged[feat_b].values if feat_b in merged.columns else np.zeros(len(merged))

        # Interaction SHAP uses a product proxy (SHAP_a * SHAP_b * sign(f_a * f_b))
        # as a second-order approximation. This is not a formal Shapley interaction
        # value — it is an associative heuristic for identifying co-occurring
        # feature influences in the model's prediction space.
        interaction_shap = shap_a * shap_b * np.sign(feat_a_vals * feat_b_vals + 1e-10)
        mean_interaction = float(np.mean(interaction_shap))
        std_interaction = float(np.std(interaction_shap))

        # Affected population defined as subscribers with non-zero interaction
        # signal (|interaction| > 1e-6). Threshold chosen to eliminate floating-
        # point noise while preserving genuine co-occurrence signal.
        affected_mask = np.abs(interaction_shap) > 1e-6
        affected_pct = float(affected_mask.mean() * 100)

        # Churn delta between high and low interaction groups
        high_interaction = merged[affected_mask]["churn_probability"] if affected_mask.any() else pd.Series([0.0])
        low_interaction = merged[~affected_mask]["churn_probability"] if (~affected_mask).any() else pd.Series([0.0])
        churn_delta = float(_safe_mean(high_interaction) - _safe_mean(low_interaction))

        narrative = _build_narrative(
            label.replace("_", " / "),
            mean_interaction,
            affected_pct,
            churn_delta,
        )

        interactions[label] = {
            "pair": (feat_a, feat_b),
            "pair_label": label.replace("_", " & "),
            "mean_interaction_shap": mean_interaction,
            "std_interaction_shap": std_interaction,
            "direction": _narrative_direction(mean_interaction),
            "affected_population": int(affected_mask.sum()),
            "affected_population_pct": round(affected_pct, 2),
            "churn_probability_delta_high_vs_low_interaction": round(churn_delta, 4),
            "population_mean_risk": _safe_mean(merged["churn_probability"]),
            "narrative": narrative,
        }

        # Per-subscriber interaction for top-pairs parquet
        for i in range(len(merged)):
            top_rows.append({
                "subscriber_id": int(merged["subscriber_id"].iloc[i]),
                "pair_label": label,
                "feature_a": feat_a,
                "feature_b": feat_b,
                "interaction_shap": float(interaction_shap[i]),
                "feature_a_value": (
                    float(feat_a_vals[i])
                    if not np.isnan(feat_a_vals[i]) else None
                ),
                "feature_b_value": (
                    float(feat_b_vals[i])
                    if not np.isnan(feat_b_vals[i]) else None
                ),
                "churn_probability": float(merged["churn_probability"].iloc[i]),
            })

    top_pairs_df = pd.DataFrame(top_rows)
    top_pairs_df = top_pairs_df.sort_values("interaction_shap", ascending=False)

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    summary = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_pairs": len(INTERACTION_PAIRS),
        "interactions": interactions,
        # Interactions are associative summaries of model predictions, not
        # causal interaction effects in the real world. The product proxy is
        # a heuristic, not a formal Shapley interaction index.
        "disclaimer": (
            "Interaction SHAP values are associative summaries, not causal interaction effects. "
            "They describe observed second-order relationships in model predictions."
        ),
    }

    with open(OUTPUT_ANALYTICS / "shap_interaction_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    top_pairs_df.to_parquet(OUTPUT_ANALYTICS / "shap_interaction_top_pairs.parquet", index=False)

    return summary
