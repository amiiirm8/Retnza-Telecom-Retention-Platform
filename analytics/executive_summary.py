"""Executive storytelling — associative narratives for decision-makers.

Workflow stage: reporting-time (step 6 of 8, depends on campaign_saturation).

Generates executive-safe narratives for churn landscape, ecosystem observations,
prepaid volatility, tenure stability, campaign operations, and model health.
All narratives use associative wording ('associated with', 'observed relationship')
and never use causal wording.

Pipeline position: penultimate narrative layer. Aggregates results from all
prior analytics modules into human-readable JSON and markdown reports.

Key invariants:
  - All narratives are associative by policy (no 'causes', 'drives', 'impacts').
  - SHAP narratives inform but never override rule-based actions.
  - Disclaimer is embedded in every output artifact.
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
    RECOMMENDATIONS_MANIFEST_PATH,
    RECOMMENDATIONS_PATH,
    SHAP_MANIFEST_PATH,
)


def _safe_mean(s: pd.Series) -> float:
    """Compute mean of a series, returning 0.0 for empty series."""
    return float(s.mean()) if len(s) else 0.0


def _pct_str(val: float) -> str:
    """Format a float as a percentage string (e.g. 0.123 -> '12.3%')."""
    return f"{val * 100:.1f}%"


def build_churn_landscape_narrative(rec: pd.DataFrame) -> list[str]:
    """Narrative bullets on overall churn distribution.

    Computes mean calibrated risk, counts by risk tier, and formats
    associative bullet points for executive consumption.

    Args:
        rec: Recommendation DataFrame with churn_probability and risk_tier.

    Returns:
        list of human-readable narrative strings (associative wording).
    """
    n = len(rec)
    mean_risk = _safe_mean(rec["churn_probability"])
    vh_count = int((rec["risk_tier"] == "Very High").sum())
    h_count = int((rec["risk_tier"] == "High").sum())
    m_count = int((rec["risk_tier"] == "Medium").sum())
    l_count = int((rec["risk_tier"] == "Low").sum())

    return [
        f"Base churn probability averages {mean_risk:.3f} across {n} subscribers "
        f"(observed in this snapshot).",
        f"High-risk segments (Very High + High) represent "
        f"{vh_count + h_count} subscribers ({_pct_str((vh_count + h_count) / n)}), "
        f"with Very High alone at {vh_count} ({_pct_str(vh_count / n)}).",
        f"Medium-risk tier includes {m_count} subscribers ({_pct_str(m_count / n)}); "
        f"Low-risk represents {l_count} ({_pct_str(l_count / n)}).",
    ]


def build_ecosystem_narrative(rec: pd.DataFrame) -> list[str]:
    """Narrative bullets on ecosystem product adoption and churn association.

    For each ecosystem product (Rubika, EWANO, Hamrah Man, VoLTE), compares
    mean churn probability between adopters and non-adopters. Also reports
    top ecosystem segments by volume.

    All comparisons use 'associated with' wording (not causal).

    Args:
        rec: Recommendation DataFrame with ecosystem columns.

    Returns:
        list of associative narrative strings.
    """
    bullets: list[str] = []
    for product, col in [
        ("Rubika", "has_rubika"),
        ("EWANO", "has_ewano"),
        ("Hamrah Man", "has_hamrahman"),
        ("VoLTE", "has_volte"),
    ]:
        if col not in rec.columns:
            continue
        active = rec[rec[col] == 1]
        inactive = rec[rec[col] == 0]
        if len(active) > 0 and len(inactive) > 0:
            delta = _safe_mean(active["churn_probability"]) - _safe_mean(inactive["churn_probability"])
            direction = "lower" if delta < 0 else "higher"
            bullets.append(
                f"{product} adoption is associated with {direction} mean churn probability "
                f"(difference of {abs(delta):.3f}) compared to non-adopters "
                f"(observed association, not causal)."
            )

    eco_col = "ecosystem_segment"
    if eco_col in rec.columns:
        seg_counts = rec[eco_col].value_counts()
        top = seg_counts.head(3)
        for seg, cnt in top.items():
            seg_risk = _safe_mean(rec[rec[eco_col] == seg]["churn_probability"])
            bullets.append(
                f"The '{seg}' segment includes {cnt} subscribers "
                f"(mean risk {seg_risk:.3f})."
            )

    return bullets


def build_prepaid_narrative(rec: pd.DataFrame, fe: pd.DataFrame) -> list[str]:
    """Narrative bullets on prepaid vs postpaid churn association.

    Merges is_prepaid flag from features and compares mean churn probability
    between prepaid and postpaid segments.

    Args:
        rec: Recommendation DataFrame.
        fe: Feature DataFrame with is_prepaid column.

    Returns:
        list of associative narrative strings.
    """
    merged = rec.merge(
        fe[["subscriber_id", "is_prepaid"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    prepaid = merged[merged["is_prepaid"] == 1]
    postpaid = merged[merged["is_prepaid"] == 0]
    if len(prepaid) == 0 or len(postpaid) == 0:
        return ["Prepaid vs postpaid comparison not available in this snapshot."]

    prepaid_risk = _safe_mean(prepaid["churn_probability"])
    postpaid_risk = _safe_mean(postpaid["churn_probability"])
    delta = prepaid_risk - postpaid_risk
    direction = "higher" if delta > 0 else "lower"
    return [
        f"Prepaid subscribers ({len(prepaid)}) show {direction} mean churn probability "
        f"({prepaid_risk:.3f}) compared to postpaid ({postpaid_risk:.3f}); "
        f"a difference of {abs(delta):.3f} (observed association).",
        f"Prepaid represents {_pct_str(len(prepaid) / max(len(merged), 1))} of the base.",
    ]


def build_tenure_narrative(rec: pd.DataFrame, fe: pd.DataFrame) -> list[str]:
    """Narrative bullets on tenure stability patterns.

    Compares mean churn probability between early-lifecycle (<=12 months)
    and tenured subscribers using early_lifecycle_flag from features.

    Args:
        rec: Recommendation DataFrame.
        fe: Feature DataFrame with sim_tenure_months and early_lifecycle_flag.

    Returns:
        list of associative narrative strings.
    """
    merged = rec.merge(
        fe[["subscriber_id", "sim_tenure_months", "early_lifecycle_flag"]]
        .drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )
    early = merged[merged["early_lifecycle_flag"] == 1]
    tenured = merged[merged["early_lifecycle_flag"] == 0]
    if len(early) == 0 or len(tenured) == 0:
        return ["Tenure cohort comparison not available in this snapshot."]

    early_risk = _safe_mean(early["churn_probability"])
    tenured_risk = _safe_mean(tenured["churn_probability"])
    return [
        f"Early-lifecycle subscribers (tenure <= 12 months, n={len(early)}) show "
        f"mean churn probability {early_risk:.3f} vs {tenured_risk:.3f} for tenured subscribers "
        f"(n={len(tenured)}). Early lifecycle is associated with elevated churn risk.",
    ]


def build_campaign_narrative(
    rec: pd.DataFrame,
    saturation: dict[str, Any] | None = None,
) -> list[str]:
    """Narrative bullets on campaign operations and saturation.

    Reports top 5 rules by frequency, P1 share, and fallback rule R99
    coverage. If saturation data is provided, includes overload risk count.

    Args:
        rec: Recommendation DataFrame with rule_id, campaign_priority.
        saturation: Optional dict from compute_campaign_saturation().

    Returns:
        list of narrative strings about campaign operations.
    """
    bullets: list[str] = []
    rule_counts = rec["rule_id"].value_counts()
    top_rules = rule_counts.head(5)
    for rid, cnt in top_rules.items():
        share = cnt / max(len(rec), 1)
        bullets.append(
            f"Rule {rid} covers {cnt} subscribers ({_pct_str(share)}) — "
            f"the most frequently assigned action."
        )

    p1_share = (rec["campaign_priority"] == "P1").mean()
    bullets.append(
        f"P1 (urgent) campaigns represent {_pct_str(p1_share)} of all actions, "
        f"requiring immediate operational attention."
    )

    fallback_share = (rec["rule_id"] == "R99_HIGH_RISK_SAVE").mean()
    if fallback_share > 0.10:
        bullets.append(
            f"R99 fallback covers {_pct_str(fallback_share)} of subscribers; "
            f"this may indicate that product rules are not capturing the full "
            f"high-risk profile of the base."
        )

    if saturation and saturation.get("overload_risks"):
        bullets.append(
            f"{saturation['n_overload_risks']} saturation risk(s) detected — "
            f"review campaign_saturation_summary.json for details."
        )

    return bullets


def build_model_health_narrative(
    manifest: dict[str, Any] | None = None,
    shap_manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Narrative on model calibration, stability, and drift.

    Reports schema versions from champion and recommendation manifests,
    risk tier distribution, SHAP schema, top global SHAP drivers, and
    associative wording for model-level observations.

    Args:
        manifest: Recommendation manifest dict (recommendation_manifest.json).
        shap_manifest: SHAP manifest dict (explainability_manifest.json).

    Returns:
        list of narrative strings about model health.
    """
    bullets: list[str] = []
    if manifest:
        fallback_share = manifest.get("fallback_rule_share", 0)
        bullets.append(
            f"Champion bundle schema: {manifest.get('schema_version', 'unknown')}. "
            f"Fallback rule share: {_pct_str(fallback_share)}."
        )
        risk_counts = manifest.get("risk_tier_counts", {})
        if risk_counts:
            total = sum(risk_counts.values())
            parts = ", ".join(
                f"{tier}: {cnt} ({_pct_str(cnt / max(total, 1))})"
                for tier, cnt in sorted(risk_counts.items(), key=lambda x: -x[1])
            )
            bullets.append(f"Risk tier distribution — {parts}.")

    if shap_manifest:
        bullets.append(
            f"SHAP schema: {shap_manifest.get('schema_version', 'unknown')}. "
            "SHAP values explain the ranking (base model) layer only; "
            "calibration is monotonic and not explained."
        )
        top_drivers = shap_manifest.get("top_global_drivers", [])
        if top_drivers:
            top_names = [d.get("feature", "?") for d in top_drivers[:3]]
            bullets.append(
                f"Top SHAP drivers: {', '.join(top_names)}. "
                "These features show the strongest association with churn predictions "
                "in the current model (associative, not causal)."
            )

    bullets.append(
        "Model health metrics (calibration, stability, drift) are monitored "
        "separately via the model monitoring dashboard and drift reports."
    )
    return bullets


def build_executive_summary(
    rec_path: Path = RECOMMENDATIONS_PATH,
    feature_path: Path = FEATURES_PATH,
    manifest_path: Path = RECOMMENDATIONS_MANIFEST_PATH,
    shap_manifest_path: Path = SHAP_MANIFEST_PATH,
    saturation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Orchestrate executive narratives across all domains.

    Reads recommendations, features, and manifests; runs all six narrative
    builders; assembles the complete executive summary dict with wrapping
    policy and metadata.

    Args:
        rec_path: Path to recommendation parquet.
        feature_path: Path to feature parquet.
        manifest_path: Path to recommendation manifest JSON.
        shap_manifest_path: Path to SHAP manifest JSON.
        saturation: Optional campaign saturation dict for campaign narrative.

    Returns:
        dict with schema_version, generated_at_utc, n_subscribers,
        mean_calibrated_risk, narratives (dict of 6 sections), wording_policy,
        dashboard_ready.
    """
    rec = pd.read_parquet(rec_path)
    fe = pd.read_parquet(feature_path)

    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    shap_manifest: dict[str, Any] = {}
    if shap_manifest_path.is_file():
        shap_manifest = json.loads(shap_manifest_path.read_text(encoding="utf-8"))

    narratives = {
        "churn_landscape": build_churn_landscape_narrative(rec),
        "ecosystem_observations": build_ecosystem_narrative(rec),
        "prepaid_volatility": build_prepaid_narrative(rec, fe),
        "tenure_stability": build_tenure_narrative(rec, fe),
        "campaign_operations": build_campaign_narrative(rec, saturation),
        "model_health": build_model_health_narrative(manifest, shap_manifest),
    }

    summary = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_subscribers": int(len(rec)),
        "mean_calibrated_risk": _safe_mean(rec["churn_probability"]),
        "narratives": narratives,
        # Associative wording is required by platform policy. This is not
        # an uplift or causal inference platform; analytics describe observed
        # patterns, not treatment effects.
        "wording_policy": (
            "All narratives use associative wording ('associated with', "
            "'observed relationship'). No causal claims are made. "
            "SHAP narratives inform but never override rule-based actions."
        ),
        "dashboard_ready": True,
    }

    return summary


def generate_executive_storytelling_md(summary: dict[str, Any]) -> str:
    """Generate an executive-friendly markdown report.

    Converts the structured executive summary into a formatted markdown
    document with sections for each narrative domain and a methodological
    note reinforcing associative wording.

    Args:
        summary: dict from build_executive_summary().

    Returns:
        Markdown string ready for file output.
    """
    lines: list[str] = [
        "# Executive Intelligence Summary",
        "",
        f"*Generated: {summary['generated_at_utc']}*",
        f"*Base: {summary['n_subscribers']} subscribers, "
        f"mean calibrated risk: {summary['mean_calibrated_risk']:.3f}*",
        "",
        "---",
        "## Churn Landscape",
        "",
    ]
    lines.extend(f"- {b}" for b in summary["narratives"]["churn_landscape"])

    lines.extend(["", "---", "## Ecosystem Observations", ""])
    lines.extend(f"- {b}" for b in summary["narratives"]["ecosystem_observations"])

    lines.extend(["", "---", "## Prepaid Volatility", ""])
    lines.extend(f"- {b}" for b in summary["narratives"]["prepaid_volatility"])

    lines.extend(["", "---", "## Tenure Stability", ""])
    lines.extend(f"- {b}" for b in summary["narratives"]["tenure_stability"])

    lines.extend(["", "---", "## Campaign Operations", ""])
    lines.extend(f"- {b}" for b in summary["narratives"]["campaign_operations"])

    lines.extend(["", "---", "## Model Health / Calibration / Stability", ""])
    lines.extend(f"- {b}" for b in summary["narratives"]["model_health"])

    lines.extend([
        "",
        "---",
        "## Methodological Note",
        "",
        summary["wording_policy"],
        "",
        "*SHAP explains the ranking (base model) layer only. "
        "Calibration is monotonic and not explained. "
        "Recommendations are rule-based decisions; SHAP narratives "
        "enrich explanations for high-risk tiers only.*",
    ])

    return "\n".join(lines)


def generate_all_executive_artifacts(
    saturation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write executive summary JSON and markdown storytelling.

    Top-level entry point for executive narrative generation. Builds summary,
    generates markdown, writes both artifacts, and returns the summary dict.

    Args:
        saturation: Optional campaign saturation dict from
            compute_campaign_saturation().

    Returns:
        Executive summary dict (same as build_executive_summary return).

    Side effects:
        Writes executive_summary.json and executive_storytelling.md
        to OUTPUT_ANALYTICS.
    """
    summary = build_executive_summary(saturation=saturation)
    md = generate_executive_storytelling_md(summary)

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_ANALYTICS / "executive_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    (OUTPUT_ANALYTICS / "executive_storytelling.md").write_text(md, encoding="utf-8")

    return summary
