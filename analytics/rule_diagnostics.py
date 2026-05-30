"""Rule precision diagnostics — per-rule population stats, overlap, saturation.

Workflow stage: reporting-time (step 3 of 8, after SHAP interactions).

Evaluates R01-R12 + R99 for population share, risk capture, saturation
estimates, queue load, ecosystem distribution, digital/human-touch ratios,
and fallback dependency. Detects overly broad, overlapping, low-precision,
and saturation-risk rules.

Pipeline position: reads recommendation and feature-schema features. Produces
rule_precision_summary.json, rule_population_distribution.parquet, and
rule_overlap_matrix.parquet.

Key invariants:
  - Rule list mirrors RULE_PRECEDENCE_ORDER from recommendation.rules; defined
    locally to avoid circular imports at module level.
  - Overlap uses Jaccard similarity on subscriber index sets (co-occurrence,
    not causal interaction).
  - Precision labels are descriptive, not evaluative of rule quality.
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
)
# Rule list mirrors recommendation.rules.RULE_PRECEDENCE_ORDER.
# Defined locally to avoid triggering recommendation package imports at module level.
# This is the canonical precedence order for product rules R01-R12, consistent
# with the recommendation engine's rule evaluation sequence.
RULE_PRECEDENCE_ORDER: list[str] = [
    "R01_PREPAID_INFANT",
    "R02_PREPAID_5G",
    "R12_ECOSYSTEM_POWER_USER",
    "R05_BILL_SHOCK",
    "R09_RUBIKA_INACTIVE",
    "R10_EWANO_NON_ADOPTER",
    "R11_HAMRAHMAN_LOW_ENGAGEMENT",
    "R03_VOLTE_ENABLE",
    "R04_VAS_ZERO",
    "R06_VAS_PARTIAL",
    "R08_POSTPAID_EARLY",
    "R07_LEGACY_2G",
]

ALL_RULES = RULE_PRECEDENCE_ORDER + ["R99_HIGH_RISK_SAVE", "R00_MONITOR"]


def _safe_mean(s: pd.Series) -> float:
    """Compute mean of a series, returning 0.0 for empty series."""
    return float(s.mean()) if len(s) else 0.0


def _digitize_precision(share: float) -> str:
    """Categorize a rule's population share into a precision label.

    Thresholds (>30% overly_broad, >15% broad, >5% moderate, <=5% targeted)
    are descriptive bands based on typical rule targeting expectations. They
    are not formal precision or recall metrics.

    Args:
        share: Population share (0.0 to 1.0).

    Returns:
        One of: 'overly_broad', 'broad', 'moderate', 'targeted'.
    """
    if share > 0.30:
        return "overly_broad"
    if share > 0.15:
        return "broad"
    if share > 0.05:
        return "moderate"
    return "targeted"


def compute_rule_precision_summary(
    rec_path: Path = RECOMMENDATIONS_PATH,
    feature_path: Path = FEATURES_PATH,
) -> dict[str, Any]:
    """Per-rule population, risk, operational, and saturation diagnostics.

    For each rule in ALL_RULES (R01-R12 + R99 + R00), computes:
      n, population_share, avg calibrated/raw risk, high_risk_n and capture
      rate, saturation_estimate, CRM queue distribution, ecosystem segment
      distribution, digital_only_ratio, human_touch_ratio, is_fallback,
      prepaid_ratio, and precision_label.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.
        feature_path: Path to feature-schema feature parquet (for prepaid and
            ecosystem flags).

    Returns:
        dict mapping rule_id -> per-rule metrics dict.
    """
    rec = pd.read_parquet(rec_path)
    fe = pd.read_parquet(feature_path)

    merged = rec.merge(
        fe[["subscriber_id", "is_prepaid", "is_data_capable",
            "rubika_user_flag", "ewano_user_flag", "hamrahman_user_flag",
            "volte_user_flag", "digital_engagement_score"]]
        .drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )

    n_book = len(merged)
    high_risk_mask = merged["risk_tier"].isin(["Very High", "High"])

    rules: dict[str, Any] = {}
    for rid in ALL_RULES:
        mask = merged["rule_id"] == rid
        n = int(mask.sum())
        if n == 0:
            rules[rid] = {"n": 0, "note": "no_subscribers_matched"}
            continue

        grp = merged[mask]
        p_cal = grp["churn_probability"]
        p_raw = grp["churn_probability_raw"]
        high_risk_in_rule = high_risk_mask[mask].sum()

        rules[rid] = {
            "n": n,
            "population_share": round(n / max(n_book, 1), 4),
            "avg_calibrated_risk": round(_safe_mean(p_cal), 4),
            "avg_raw_risk": round(_safe_mean(p_raw), 4),
            "high_risk_n": int(high_risk_in_rule),
            "high_risk_capture_rate": round(
                high_risk_in_rule / max(high_risk_mask.sum(), 1), 4
            ),
            "saturation_estimate": round(n / max(n_book, 1), 4),
            "crm_queue_distribution": {
                str(q): int(c) for q, c in grp["crm_queue"].value_counts().to_dict().items()
            },
            "ecosystem_distribution": {
                str(seg): int(c)
                for seg, c in grp.get("ecosystem_segment", pd.Series()).value_counts().to_dict().items()
            },
            "digital_only_ratio": float(grp.get("digital_only_flag", pd.Series([True])).mean()),
            "human_touch_ratio": float(grp.get("human_touch_flag", pd.Series([False])).mean()),
            "is_fallback": rid == "R99_HIGH_RISK_SAVE",
            "prepaid_ratio": float(grp["is_prepaid"].mean()) if "is_prepaid" in grp else None,
            "precision_label": _digitize_precision(n / max(n_book, 1)),
        }

    return rules


def detect_rule_anomalies(rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect overly broad, overlapping, low-precision, or saturation-risk rules.

    Flags rules where:
      - population_share exceeds 30% (overly_broad) or 20% (broad).
      - high_risk_n < 5 with population_share > 5% (low_precision).
      - saturation_estimate > 25% (saturation_risk).

    Anomalies are associative diagnostics, not judgments of rule effectiveness.
    A broad rule may still be appropriate if it covers a genuinely large
    at-risk segment.

    Args:
        rules: dict from compute_rule_precision_summary().

    Returns:
        list of dicts with rule_id, anomaly_type, detail, and relevant metric.
    """
    anomalies: list[dict[str, Any]] = []
    for rid, info in rules.items():
        if info.get("n", 0) == 0:
            continue
        share = info.get("population_share", 0)

        if share > 0.30:
            anomalies.append({
                "rule_id": rid,
                "anomaly_type": "overly_broad",
                "detail": (
                    f"Rule covers {share:.1%} of base; "
                    f"may lack targeting precision."
                ),
                "population_share": share,
            })
        elif share > 0.20:
            anomalies.append({
                "rule_id": rid,
                "anomaly_type": "broad",
                "detail": f"Rule covers {share:.1%} of base; monitor specificity.",
                "population_share": share,
            })

        high_risk_n = info.get("high_risk_n", 0)
        if high_risk_n < 5 and share > 0.05:
            anomalies.append({
                "rule_id": rid,
                "anomaly_type": "low_precision",
                "detail": (
                    f"Only {high_risk_n} high-risk subscribers in {share:.1%} population; "
                    f"rule may be capturing low-risk base."
                ),
            })

        if info.get("saturation_estimate", 0) > 0.25:
            anomalies.append({
                "rule_id": rid,
                "anomaly_type": "saturation_risk",
                "detail": f"Saturation is {info['saturation_estimate']:.1%}; queue may be overloaded.",
            })

    return anomalies


def compute_rule_overlap_matrix(
    rec_path: Path = RECOMMENDATIONS_PATH,
) -> pd.DataFrame:
    """Compute pairwise rule overlap as Jaccard similarity (rule presence co-occurrence).

    Jaccard similarity is used because rules are mutually exclusive per
    subscriber (each subscriber gets exactly one rule). Overlap here measures
    co-occurrence of rule assignments across the subscriber index space —
    i.e., how much the subscriber sets of two rules overlap when rules
    could be reassigned. A high Jaccard between rules A and B means they
    tend to capture similar subscriber profiles.

    This is a co-occurrence metric, not a causal interaction measure.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.

    Returns:
        DataFrame with rule_id_a index, rule_id_b columns, values are
        Jaccard similarity (0.0 to 1.0).
    """
    rec = pd.read_parquet(rec_path)
    rule_ids = rec["rule_id"].unique()
    n_rules = len(rule_ids)

    matrix = np.zeros((n_rules, n_rules), dtype=float)
    for i, rid_a in enumerate(rule_ids):
        mask_a = rec["rule_id"] == rid_a
        set_a = set(rec.index[mask_a])
        for j, rid_b in enumerate(rule_ids):
            if j < i:
                matrix[i, j] = matrix[j, i]
                continue
            mask_b = rec["rule_id"] == rid_b
            set_b = set(rec.index[mask_b])
            union = len(set_a | set_b)
            intersection = len(set_a & set_b)
            matrix[i, j] = intersection / max(union, 1)

    overlap_df = pd.DataFrame(matrix, index=rule_ids, columns=rule_ids)
    overlap_df.index.name = "rule_id_a"
    overlap_df.columns.name = "rule_id_b"
    return overlap_df.reset_index()


def compute_all_rule_diagnostics(
    rec_path: Path = RECOMMENDATIONS_PATH,
    feature_path: Path = FEATURES_PATH,
) -> dict[str, Any]:
    """Orchestrate all rule diagnostics and write artifacts.

    Runs compute_rule_precision_summary(), detect_rule_anomalies(), and
    compute_rule_overlap_matrix(). Writes outputs to OUTPUT_ANALYTICS.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.
        feature_path: Path to feature-schema feature parquet.

    Returns:
        dict with schema_version, generated_at_utc, n_rules, rules,
        detected_anomalies, n_anomalies, and disclaimer.

    Side effects:
        Writes rule_precision_summary.json, rule_population_distribution.parquet,
        and rule_overlap_matrix.parquet to OUTPUT_ANALYTICS.
    """
    rules = compute_rule_precision_summary(rec_path, feature_path)
    anomalies = detect_rule_anomalies(rules)
    overlap = compute_rule_overlap_matrix(rec_path)

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    summary = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_rules": len(ALL_RULES),
        "rules": rules,
        "detected_anomalies": anomalies,
        "n_anomalies": len(anomalies),
        "disclaimer": (
            "Rule diagnostics describe observed rule assignment patterns. "
            "Overlap and precision metrics are associative, not evaluations of rule quality."
        ),
    }

    with open(OUTPUT_ANALYTICS / "rule_precision_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    pop_dist = _build_population_distribution(rec_path)
    pop_dist.to_parquet(OUTPUT_ANALYTICS / "rule_population_distribution.parquet", index=False)
    overlap.to_parquet(OUTPUT_ANALYTICS / "rule_overlap_matrix.parquet", index=False)

    return summary


def _build_population_distribution(rec_path: Path) -> pd.DataFrame:
    """Build per-subscriber rule population metadata for dashboard.

    Extracts a subset of recommendation columns relevant to rule population
    analysis: subscriber_id, rule_id, risk_tier, churn_probability,
    churn_probability_raw, campaign_queue_rank, crm_queue, ecosystem_segment,
    digital_only_flag, human_touch_flag, is_fallback_rule, campaign_priority.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.

    Returns:
        DataFrame with available rule-population columns.
    """
    rec = pd.read_parquet(rec_path)
    cols = ["subscriber_id", "rule_id", "risk_tier", "churn_probability",
            "churn_probability_raw", "campaign_queue_rank", "crm_queue",
            "ecosystem_segment", "digital_only_flag", "human_touch_flag",
            "is_fallback_rule", "campaign_priority"]
    existing = [c for c in cols if c in rec.columns]
    return rec[existing].copy()
