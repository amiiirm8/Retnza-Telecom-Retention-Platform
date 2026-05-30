"""Production rule-based retention decisioning (Production rule-based retention decisioning).

Orchestrates the full recommendation pipeline:
  1. Load champion model → score subscribers → calibrate probabilities
  2. Apply business rules in precedence order → assign rule_id, action
  3. Resolve delivery channels, costs, urgency
  4. Compute ecosystem segmentation and analytics
  5. Optionally merge SHAP explanations for Very High / High risk tiers
  6. Write artifacts: parquet, CSV, manifest JSON

Pipeline stage: inference/reporting-time (never training).

Key invariants:
  - All actions are rule-driven; SHAP is narrative-only and NEVER selects actions.
  - R99 fallback catches high-risk subscribers with no rule match.
  - High-risk subscribers are never left on R00_MONITOR (corrective override).
  - Ecosystem metrics are associative, not causal.
  - campaign_queue_rank is sort key for CRM campaign prioritization.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from feature_engineering.builders import build_features
from modeling.scoring import assign_risk_tier as model_assign_risk_tier
from modeling.scoring import calibrate_raw_proba, predict_raw_proba
from recommendation.config import (
    CHAMPION_MANIFEST_PATH,
    CHAMPION_PATH,
    CLEANED_PATH,
    OUTPUT_DIR,
    RECOMMENDATION_ENGINE_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
    RuntimeConfig,
    load_runtime_config,
)
from recommendation.ecosystem import compute_ecosystem_analytics, compute_ecosystem_fields
from recommendation.operational import resolve_delivery
from recommendation.rules import (
    CAMPAIGN_PRIORITY_BY_TIER,
    COST_TIER_DEFINITIONS,
    FALLBACK_RULE,
    RULE_PRECEDENCE_ORDER,
    RecommendationRule,
    _build_rules,
)

from recommendation.shap_merge import merge_shap_explanations

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def assign_risk_tier(
    probability: float,
    thresholds: dict[str, float] | None = None,
) -> str:
    """Delegate to modeling scoring with runtime thresholds.

    Thin wrapper that routes to modeling.scoring.assign_risk_tier using
    thresholds resolved from champion artifacts (not hardcoded values).

    Args:
        probability: Calibrated churn probability [0, 1].
        thresholds: Dict mapping tier names to lower-bound cutoffs
            (e.g. {"Very High": 0.6, "High": 0.3, "Medium": 0.15}).
            Falls back to modeling.config defaults if None.

    Returns:
        Risk tier label: "Very High", "High", "Medium", or "Low".

    Side effects:
        None.
    """
    return model_assign_risk_tier(probability, thresholds)


def apply_recommendations(
    df: pd.DataFrame,
    churn_probability: np.ndarray,
    *,
    rules: list[RecommendationRule] | None = None,
    runtime: RuntimeConfig | None = None,
) -> pd.DataFrame:
    """
    Rule-driven retention actions on calibrated probabilities.

    Adds ecosystem fields and structured operational metadata.
    """
    runtime = runtime or load_runtime_config()
    thresholds = runtime.risk_tier_thresholds
    rules = rules or _build_rules()
    # Build precedence index from ordered list — lower index = higher priority.
    precedence = {rid: i for i, rid in enumerate(RULE_PRECEDENCE_ORDER)}
    high_threshold = thresholds["High"]

    eco = compute_ecosystem_fields(df)
    work = df.reset_index(drop=True).copy()
    work["_churn_probability"] = churn_probability
    work["_risk_tier"] = [assign_risk_tier(float(p), thresholds) for p in churn_probability]

    rows: list[dict[str, Any]] = []
    for idx in range(len(work)):
        row_s = work.loc[idx]
        prob = float(churn_probability[idx])
        tier = assign_risk_tier(prob, thresholds)

        # Evaluate all rules; pick the highest-precedence match.
        # Rule evaluation is order-independent — precedence is determined
        # by RULE_PRECEDENCE_ORDER, not by evaluation order.
        fired = [r for r in rules if r.evaluate(row_s)]
        if fired:
            fired.sort(key=lambda r: precedence.get(r.rule_id, 999))
            winner = fired[0]
        elif prob >= high_threshold:
            # R99 fallback: high risk with no matching product rule.
            # This exists because not all high-risk profiles are covered by
            # product rules; the fallback ensures actionable output for every
            # high-risk subscriber.
            winner = FALLBACK_RULE
        else:
            # Medium/Low risk with no rule match → monitor only.
            winner = None

        if winner is None:
            rid = "R00_MONITOR"
            rule_driver = "Low model risk"
            action = "Monitor: include in quarterly digital health SMS (no outbound call)."
            rule_pri = "P4"
            cp = "P4"
        else:
            rid = winner.rule_id
            rule_driver = winner.top_driver_label
            action = winner.recommended_action
            rule_pri = winner.rule_priority
            # Campaign priority starts from risk tier, but is promoted to P1
            # if the matched rule itself is P1 (e.g. a Very High tier rule
            # that is also P1 priority gets P1 campaign treatment).
            cp = CAMPAIGN_PRIORITY_BY_TIER[tier]
            if winner.rule_priority == "P1" and cp == "P2":
                cp = "P1"

        delivery = resolve_delivery(rid, tier)
        row_out: dict[str, Any] = {
            "subscriber_id": int(work["subscriber_id"].iloc[idx]),
            "churn_probability": round(prob, 4),
            "risk_tier": tier,
            "rule_id": rid,
            "rule_top_driver": rule_driver,
            "top_driver": rule_driver,
            "recommended_action": action,
            "rule_priority": rule_pri,
            "campaign_priority": cp,
            **delivery,
        }
        for c in eco.columns:
            row_out[c] = eco.iloc[idx][c]
        rows.append(row_out)

    out = pd.DataFrame(rows)

    # Safety net: high-risk subscribers must never remain on R00_MONITOR.
    # This can happen if the individual row's rule evaluation returned None
    # (low risk) but the subscriber still falls under Very High / High tier
    # due to the model score. The corrective override forces them to R99.
    mask_fix = out["risk_tier"].isin(["Very High", "High"]) & (out["rule_id"] == "R00_MONITOR")
    if mask_fix.any():
        out.loc[mask_fix, "rule_id"] = FALLBACK_RULE.rule_id
        out.loc[mask_fix, "rule_top_driver"] = FALLBACK_RULE.top_driver_label
        out.loc[mask_fix, "top_driver"] = FALLBACK_RULE.top_driver_label
        out.loc[mask_fix, "recommended_action"] = FALLBACK_RULE.recommended_action
        out.loc[mask_fix, "rule_priority"] = FALLBACK_RULE.rule_priority
        # Force campaign priority to P1 regardless of tier; high-risk
        # subscribers need immediate attention even if rule didn't match.
        out.loc[mask_fix, "campaign_priority"] = "P1"
        for col, val in (
            ("primary_channel", "desk_call"),
            ("campaign_cost_tier", "C4"),
            ("offer_budget_numeric_tier", 4),
            ("intervention_type", "high_touch_human"),
            ("human_touch_flag", True),
            ("escalation_required", True),
            ("digital_only_flag", False),
        ):
            out.loc[mask_fix, col] = val

    out["final_top_driver"] = out["rule_top_driver"]
    out["final_top_driver_source"] = "rule"
    out["shap_top_driver"] = None

    # Queue rank = priority integer (1-4) + fraction based on risk score.
    # Within same priority, higher churn probability gets lower rank (= earlier).
    # The tiny (1-p) * 0.001 tiebreaker prevents random ordering within tiers
    # while keeping priority grouping clean.
    out["campaign_queue_rank"] = (
        out["campaign_priority"].map({"P1": 1, "P2": 2, "P3": 3, "P4": 4})
        + (1 - out["churn_probability"]) * 0.001
    )
    return out.sort_values(["campaign_queue_rank", "churn_probability"], ascending=[True, False])


def _sample_subscriber_rows(rec: pd.DataFrame, fe: pd.DataFrame) -> list[dict[str, Any]]:
    """Select representative subscriber examples for manifest documentation.

    Picks one row per illustrative rule to help stakeholders understand
    what each rule looks like in practice (ecosystem, power user, fallback).

    Args:
        rec: Recommendation output DataFrame.
        fe: Feature-engineered DataFrame for additional columns.

    Returns:
        List of dicts with subscriber details and resolution notes.
        Empty list if no matching rows are found.
    """
    out_cols = [
        "subscriber_id",
        "churn_probability",
        "churn_probability_raw",
        "risk_tier",
        "rule_id",
        "rule_top_driver",
        "final_top_driver",
        "final_top_driver_source",
        "ecosystem_segment",
        "recommended_action",
        "campaign_priority",
        "crm_queue",
    ]
    feat_cols = [
        "subscriber_id",
        "is_prepaid",
        "sim_tenure_months",
        "rubika_user_flag",
        "ewano_user_flag",
        "hamrahman_user_flag",
    ]
    merged = rec.merge(fe[feat_cols], on="subscriber_id", how="left")
    samples: list[dict[str, Any]] = []

    def _pick(mask: pd.Series, label: str, note: str) -> None:
        sub = merged.loc[mask]
        if sub.empty:
            return
        row = sub.iloc[0]
        samples.append(
            {
                "example_label": label,
                "resolution_note": note,
                **{c: row[c] for c in out_cols if c in row.index},
            }
        )

    _pick(
        merged["rule_id"] == "R09_RUBIKA_INACTIVE",
        "rubika_inactive_ecosystem",
        "Ecosystem rule for capable Rubika non-adopters at medium+ risk.",
    )
    _pick(
        merged["rule_id"] == "R12_ECOSYSTEM_POWER_USER",
        "ecosystem_power_user_loyalty",
        "Multi-product ecosystem user — loyalty preservation not acquisition discount.",
    )
    _pick(
        merged["rule_id"] == "R99_HIGH_RISK_SAVE",
        "high_risk_fallback",
        "Rule-driven fallback when no product rule matches.",
    )
    return samples


def generate_recommendations(
    merge_shap_path: Path | None = None,
    *,
    champion_path: Path = CHAMPION_PATH,
    cleaned_path: Path = CLEANED_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Score population, apply rules, optional SHAP overlay, write artifacts.

    This is the main entry point for the recommendation pipeline. It:
      1. Loads champion model and config
      2. Builds features from cleaned subscriber data
      3. Scores and calibrates churn probabilities
      4. Applies business rules → per-subscriber recommendations
      5. Optionally merges SHAP explanations for narrative enrichment
      6. Computes ecosystem analytics
      7. Writes output parquet, CSV, and manifest JSON

    Args:
        merge_shap_path: Path to SHAP values parquet for narrative overlay.
            If None, searches default location
            (outputs/explainability/subscriber_shap_values.parquet).
        champion_path: Path to champion model .joblib file.
        cleaned_path: Path to cleaned subscriber parquet.

    Returns:
        Tuple of (recommendations DataFrame, manifest dict).

    Side effects:
        Writes three artifacts to OUTPUT_DIR:
          - subscriber_recommendations.parquet
          - subscriber_recommendations.csv
          - recommendation_manifest.json

    Failure modes:
        - Missing champion_path → joblib load error (hard failure).
        - Missing cleaned_path → file not found error (hard failure).
        - Missing/mismatched SHAP → skipped overlay (soft failure, logged).
        - Schema drift → warning in manifest, execution continues.
    """
    bundle = joblib.load(champion_path)
    manifest_champion = (
        json.loads(CHAMPION_MANIFEST_PATH.read_text(encoding="utf-8"))
        if CHAMPION_MANIFEST_PATH.is_file()
        else {}
    )
    runtime = RuntimeConfig.from_champion_artifacts(bundle, manifest_champion)

    q_monthly = float(bundle["monthly_spend_q75"])
    q_arpu = float(bundle.get("lifetime_arpu_q75", bundle["monthly_spend_q75"]))

    cleaned = pd.read_parquet(cleaned_path)
    fe = build_features(
        cleaned,
        monthly_spend_q75=q_monthly,
        lifetime_arpu_q75=q_arpu,
    )
    cols = list(bundle["feature_columns"])
    X = fe[cols].values.astype(np.float64)
    p_raw = predict_raw_proba(bundle, X)
    p_cal = calibrate_raw_proba(bundle, p_raw)

    rec = apply_recommendations(fe, p_cal, runtime=runtime)
    rec["churn_probability_raw"] = np.round(p_raw, 4)

    shap_validation: dict[str, Any] = {"merged": False}
    if merge_shap_path is None:
        default_shap = PROJECT_ROOT / "outputs" / "explainability" / "subscriber_shap_values.parquet"
        merge_shap_path = default_shap if default_shap.is_file() else None

    if merge_shap_path and merge_shap_path.is_file():
        rec, shap_validation = merge_shap_explanations(
            rec, merge_shap_path, cols, bundle
        )
        shap_validation["merged"] = shap_validation.get("compatible", False)
    else:
        # No SHAP available: final driver is purely rule-driven.
        # SHAP never selects actions — only enriches narrative — so the
        # absence of SHAP does not change any recommendation.
        rec["shap_top_driver"] = None
        rec["final_top_driver"] = rec["rule_top_driver"]
        rec["final_top_driver_source"] = "rule"
        shap_validation["note"] = "SHAP parquet not provided; rule-only explanations"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "subscriber_recommendations.parquet"
    rec.to_parquet(out_path, index=False)
    rec.to_csv(OUTPUT_DIR / "subscriber_recommendations.csv", index=False)

    ecosystem_analytics = compute_ecosystem_analytics(rec, fe)
    rules_doc = [r.to_dict() for r in _build_rules()] + [FALLBACK_RULE.to_dict()]
    fallback_share = float((rec["rule_id"] == "R99_HIGH_RISK_SAVE").mean())

    manifest: dict[str, Any] = {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "recommendation_engine_version": RECOMMENDATION_ENGINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "compatible_champion_schema": bundle.get("schema_version"),
        "compatible_feature_schema": "task4-v2",
        "compatible_modeling_schema": manifest_champion.get("schema_version"),
        "compatible_shap_schema": "task7-shap-v4",
        "engine_type": "rule_based_retention_decisioning",
        "not_uplift_modeling": True,
        "not_causal_inference": True,
        "not_treatment_effect_estimation": True,
        "pipeline_order": (
            "raw score (ranking) → calibrated score (CRM) → risk tier → "
            "business rules → ecosystem fields → optional SHAP narrative overlay"
        ),
        "scores": {
            "churn_probability": "calibrated — CRM thresholds, risk bands, operating policy",
            "churn_probability_raw": "base model — ranking, top-k, queue prioritization",
        },
        "explanation_traceability": {
            "rule_top_driver": "From matched business rule only",
            "shap_top_driver": "From model SHAP when merge valid",
            "final_top_driver": "rule_top_driver OR shap overlay (Very High / High only)",
            "final_top_driver_source": "rule | shap_overlay",
            "shap_does_not_select_actions": True,
        },
        "risk_tier_thresholds": runtime.risk_tier_thresholds,
        "threshold_source": runtime.threshold_source,
        "threshold_warnings": runtime.threshold_warnings,
        "operating_threshold_from_champion": runtime.operating_threshold,
        "cost_tier_definitions": COST_TIER_DEFINITIONS,
        "rule_precedence_order": RULE_PRECEDENCE_ORDER,
        "ecosystem_rules": ["R09_RUBIKA_INACTIVE", "R10_EWANO_NON_ADOPTER", "R11_HAMRAHMAN_LOW_ENGAGEMENT", "R12_ECOSYSTEM_POWER_USER"],
        "intervention_policy": (
            "recommended_action and rule_id are always rule-driven. "
            "SHAP enriches narrative for high tiers only."
        ),
        "shap_merge_validation": shap_validation,
        "production_cautions": [
            "Re-tune thresholds when calibration or prevalence drifts.",
            "Ecosystem metrics are associative — not causal product effects.",
            "Monitor R99 fallback_share; should stay minority of book.",
        ],
        "fallback_rule_share": fallback_share,
        "n_subscribers": int(len(rec)),
        "risk_tier_counts": rec["risk_tier"].value_counts().to_dict(),
        "campaign_priority_counts": rec["campaign_priority"].value_counts().to_dict(),
        "rule_id_counts": rec["rule_id"].value_counts().to_dict(),
        "ecosystem_segment_counts": rec["ecosystem_segment"].value_counts().to_dict()
        if "ecosystem_segment" in rec.columns
        else {},
        "ecosystem_analytics": ecosystem_analytics,
        "high_risk_without_monitor": int(
            rec[rec["risk_tier"].isin(["Very High", "High"])]["rule_id"].ne("R00_MONITOR").sum()
        ),
        "business_rules": rules_doc,
        "sample_subscribers": _sample_subscriber_rows(rec, fe),
        "output_path": str(out_path),
    }
    (OUTPUT_DIR / "recommendation_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return rec, manifest


# Re-export for API / tests
from recommendation.rules import CAMPAIGN_PRIORITY_BY_TIER  # noqa: F401

__all__ = [
    "CAMPAIGN_PRIORITY_BY_TIER",
    "RecommendationRule",
    "apply_recommendations",
    "assign_risk_tier",
    "generate_recommendations",
]
