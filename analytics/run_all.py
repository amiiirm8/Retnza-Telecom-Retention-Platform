#!/usr/bin/env python
"""Orchestrate all analytics layer computations and artifact generation.

Workflow stage: reporting-time. Entry point for the full analytics pipeline.

Usage:
    python -m analytics.run_all

Sequences (8 steps, all reporting-time):
  1. Customer/demographic intelligence  (customer_intelligence)
  2. SHAP interaction analysis          (shap_interactions)
  3. Rule precision diagnostics         (rule_diagnostics)
  4. Retention KPI/ROI simulation       (retention_simulator)
  5. Campaign saturation analytics      (campaign_saturation)
  6. Executive storytelling              (executive_summary)
  7. Dashboard artifact generation      (internal)
  8. Governance validations             (governance_checks)

Pipeline position: top-level orchestrator. Imports all analytics modules and
runs them sequentially. Exits with code 1 if governance checks find
compatibility issues.

Key invariants:
  - Steps are ordered so each step's outputs are available to downstream steps.
  - Governance runs last as a compatibility gate.
  - All outputs go to OUTPUT_ANALYTICS and OUTPUT_DASHBOARD.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    OUTPUT_ANALYTICS,
    OUTPUT_DASHBOARD,
    RECOMMENDATIONS_PATH,
    FEATURES_PATH,
)
from analytics.customer_intelligence import compute_all_customer_intelligence
from analytics.shap_interactions import compute_shap_interactions
from analytics.rule_diagnostics import compute_all_rule_diagnostics
from analytics.retention_simulator import (
    compute_retention_simulation,
    compute_executive_kpi_snapshot,
)
from analytics.campaign_saturation import compute_campaign_saturation
from analytics.executive_summary import generate_all_executive_artifacts
from analytics.behavioral_segmentation import compute_behavioral_segments
from analytics.governance_checks import (
    run_all_governance_checks,
    write_governance_report,
)


def _timer(label: str) -> None:
    """Print a timestamped progress message for pipeline step tracking."""
    print(f"  [{time.strftime('%H:%M:%S')}] {label}", flush=True)


def run_analytics_pipeline(
    feature_path: Path = FEATURES_PATH,
    rec_path: Path = RECOMMENDATIONS_PATH,
) -> dict[str, Any]:
    """Execute full analytics pipeline and return summary manifest.

    Runs all 8 steps sequentially, collects per-module status, and writes
    the analytics_manifest.json. Steps are hard-ordered by dependency:
    customer_intelligence and shap_interactions are independent, but
    executive_storytelling depends on campaign_saturation, which depends
    on retention_simulation, which depends on rule_diagnostics.

    Args:
        feature_path: Path to feature-schema feature parquet.
        rec_path: Path to recommendation-engine parquet.

    Returns:
        dict (analytics manifest) with schema_version, generated_at_utc,
        pipeline_order, modules (per-step status), artifacts (file listing),
        compatible flag, and governance_status.

    Side effects:
        Creates all analytics and dashboard output files.
    """
    manifest: dict[str, Any] = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_order": [
            "customer_intelligence",
            "shap_interactions",
            "rule_diagnostics",
            "retention_simulation",
            "campaign_saturation",
            "executive_storytelling",
            "behavioral_segmentation",
            "dashboard_artifacts",
            "governance_validations",
        ],
        "modules": {},
        "artifacts": [],
    }

    # 1. Customer / demographic intelligence
    _timer("1/8  Customer intelligence...")
    ci_result = compute_all_customer_intelligence(feature_path, rec_path)
    manifest["modules"]["customer_intelligence"] = {
        "status": "completed",
        "n_cohorts": ci_result.get("n_cohorts", 0),
        "n_genders": ci_result.get("n_genders", 0),
    }

    # 2. SHAP interaction analysis
    _timer("2/8  SHAP interaction analysis...")
    si_result = compute_shap_interactions(feature_path=feature_path, rec_path=rec_path)
    manifest["modules"]["shap_interactions"] = {
        "status": "completed",
        "n_pairs": si_result.get("n_pairs", 0),
    }

    # 3. Rule diagnostics
    _timer("3/8  Rule precision diagnostics...")
    rd_result = compute_all_rule_diagnostics(rec_path, feature_path)
    manifest["modules"]["rule_diagnostics"] = {
        "status": "completed",
        "n_rules": rd_result.get("n_rules", 0),
        "n_anomalies": rd_result.get("n_anomalies", 0),
    }

    # 4. Retention simulation
    _timer("4/8  Retention KPI/ROI simulation...")
    sim_result = compute_retention_simulation(rec_path)
    kpi_snapshot = compute_executive_kpi_snapshot(sim_result)
    manifest["modules"]["retention_simulation"] = {
        "status": "completed",
        "scenarios": list(sim_result.get("scenarios", {})),
    }

    with open(OUTPUT_ANALYTICS / "executive_kpi_snapshot.json", "w") as f:
        json.dump(kpi_snapshot, f, indent=2, default=str)

    # 5. Campaign saturation
    _timer("5/8  Campaign saturation analytics...")
    sat_result = compute_campaign_saturation(rec_path)
    manifest["modules"]["campaign_saturation"] = {
        "status": "completed",
        "n_overload_risks": sat_result.get("n_overload_risks", 0),
    }

    # 6. Executive storytelling
    _timer("6/9  Executive storytelling...")
    exec_result = generate_all_executive_artifacts(saturation=sat_result)
    manifest["modules"]["executive_storytelling"] = {
        "status": "completed",
        "n_narrative_sections": len(exec_result.get("narratives", {})),
    }

    # 7. Behavioral Segmentation
    _timer("7/9  Behavioral segmentation...")
    seg_result = compute_behavioral_segments(feature_path, rec_path)
    manifest["modules"]["behavioral_segmentation"] = {
        "status": "completed",
        "n_clusters": seg_result.get("n_clusters", 0),
    }

    # 8. Dashboard artifacts
    _timer("8/9  Dashboard artifacts...")
    _generate_dashboard_artifacts(rec_path, feature_path, sim_result, rd_result)
    manifest["modules"]["dashboard_artifacts"] = {
        "status": "completed",
    }

    # 9. Governance validations
    _timer("9/9  Governance validations...")
    gov_report = run_all_governance_checks()
    write_governance_report(gov_report)
    manifest["modules"]["governance_validations"] = {
        "status": "completed",
        "compatible": gov_report.compatible,
        "n_errors": len(gov_report.errors),
        "n_warnings": len(gov_report.warnings),
        "n_stale_artifacts": len(gov_report.stale_artifacts),
    }

    # Collect artifact listing
    for pattern in [
        "age_cohort_summary.json",
        "gender_analytics.json",
        "seasonality_analytics.json",
        "ecosystem_demographic_analytics.json",
        "age_risk_distribution.parquet",
        "shap_interaction_summary.json",
        "shap_interaction_top_pairs.parquet",
        "rule_precision_summary.json",
        "rule_population_distribution.parquet",
        "rule_overlap_matrix.parquet",
        "retention_simulation_summary.json",
        "campaign_roi_table.parquet",
        "executive_kpi_snapshot.json",
        "campaign_saturation_summary.json",
        "crm_queue_loads.parquet",
        "executive_summary.json",
        "executive_storytelling.md",
        "behavioral_segments_summary.json",
        "governance_checks_report.json",
    ]:
        p = OUTPUT_ANALYTICS / pattern
        if p.exists():
            manifest["artifacts"].append(str(p))

    dash_patterns = [
        "demographic_overview.parquet",
        "ecosystem_overview.parquet",
        "campaign_overview.parquet",
        "rule_overview.parquet",
        "model_health_overview.json",
        "executive_summary.json",
        "behavioral_segments.parquet",
    ]
    for pat in dash_patterns:
        p = OUTPUT_DASHBOARD / pat
        if p.exists():
            manifest["artifacts"].append(str(p))

    manifest["compatible"] = gov_report.compatible
    manifest["governance_status"] = "passed" if gov_report.compatible else "issues_detected"

    (OUTPUT_ANALYTICS / "analytics_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print(f"Analytics pipeline complete. {len(manifest['artifacts'])} artifacts generated.")
    print(f"Governance: {manifest['governance_status']}")
    if gov_report.warnings:
        for w in gov_report.warnings:
            print(f"  ⚠  {w}")
    if gov_report.errors:
        for e in gov_report.errors:
            print(f"  ✘  {e}")
    print(f"{'='*60}")

    return manifest


def _generate_dashboard_artifacts(
    rec_path: Path,
    feature_path: Path,
    sim_result: dict[str, Any],
    rd_result: dict[str, Any],
) -> None:
    """Generate dashboard-ready parquet and JSON artifacts.

    Merges recommendation and feature data, then writes six dashboard
    artifacts:
      - demographic_overview.parquet
      - ecosystem_overview.parquet
      - campaign_overview.parquet
      - rule_overview.parquet
      - model_health_overview.json
      - executive_summary.json (slim version from executive_summary.json)

    Args:
        rec_path: Path to recommendation parquet.
        feature_path: Path to feature parquet.
        sim_result: dict from compute_retention_simulation().
        rd_result: dict from compute_all_rule_diagnostics().

    Side effects:
        Creates OUTPUT_DASHBOARD directory and writes all six artifacts.
    """
    OUTPUT_DASHBOARD.mkdir(parents=True, exist_ok=True)

    rec = pd.read_parquet(rec_path)
    fe = pd.read_parquet(feature_path)

    merged = rec.merge(
        fe[["subscriber_id", "age", "gender_female", "gender_male",
            "is_prepaid", "sim_tenure_months", "lifetime_arpu_toman",
            "digital_engagement_score", "possible_bill_shock_flag",
            "rubika_user_flag", "ewano_user_flag", "hamrahman_user_flag",
            "volte_user_flag"]].drop_duplicates("subscriber_id"),
        on="subscriber_id", how="left",
    )

    dashboard_cols = [
        "subscriber_id", "churn_probability", "churn_probability_raw",
        "risk_tier", "rule_id", "campaign_priority", "crm_queue",
        "ecosystem_segment", "digital_only_flag", "human_touch_flag",
        "is_fallback_rule", "age", "is_prepaid", "sim_tenure_months",
        "lifetime_arpu_toman", "digital_engagement_score",
    ]
    existing = [c for c in dashboard_cols if c in merged.columns]
    demographic_overview = merged[existing].copy()
    demographic_overview.to_parquet(OUTPUT_DASHBOARD / "demographic_overview.parquet", index=False)

    eco_cols = [
        "subscriber_id", "ecosystem_segment", "has_rubika", "has_ewano",
        "has_hamrahman", "has_volte", "ecosystem_product_count",
        "ecosystem_engagement_level", "churn_probability", "risk_tier",
    ]
    existing_eco = [c for c in eco_cols if c in rec.columns]
    ecosystem_overview = rec[existing_eco].copy() if existing_eco else pd.DataFrame()
    if not ecosystem_overview.empty:
        ecosystem_overview.to_parquet(OUTPUT_DASHBOARD / "ecosystem_overview.parquet", index=False)

    campaign_cols = [
        "subscriber_id", "campaign_priority", "crm_queue", "rule_id",
        "primary_channel", "human_touch_flag", "digital_only_flag",
        "churn_probability", "risk_tier", "campaign_queue_rank",
        "is_fallback_rule",
    ]
    existing_camp = [c for c in campaign_cols if c in rec.columns]
    campaign_overview = rec[existing_camp].copy() if existing_camp else pd.DataFrame()
    if not campaign_overview.empty:
        campaign_overview.to_parquet(OUTPUT_DASHBOARD / "campaign_overview.parquet", index=False)

    rule_cols = [
        "subscriber_id", "rule_id", "risk_tier", "churn_probability",
        "crm_queue", "ecosystem_segment", "digital_only_flag",
        "human_touch_flag",
    ]
    existing_rule = [c for c in rule_cols if c in rec.columns]
    rule_overview = rec[existing_rule].copy() if existing_rule else pd.DataFrame()
    if not rule_overview.empty:
        rule_overview.to_parquet(OUTPUT_DASHBOARD / "rule_overview.parquet", index=False)

    model_health = {
        "mean_calibrated_risk": float(rec["churn_probability"].mean()),
        "risk_tier_counts": rec["risk_tier"].value_counts().to_dict(),
        "rule_id_counts": rec["rule_id"].value_counts().to_dict(),
        "simulation_scenarios": {
            k: {
                "retained": v["outputs"]["retained_subscribers"],
                "revenue_toman": v["outputs"]["retained_revenue_toman"],
                "roi": v["outputs"]["roi"],
            }
            for k, v in sim_result.get("scenarios", {}).items()
        },
        "rule_anomalies": rd_result.get("detected_anomalies", []),
    }
    (OUTPUT_DASHBOARD / "model_health_overview.json").write_text(
        json.dumps(model_health, indent=2, default=str), encoding="utf-8"
    )

    exec_summary = {}
    exec_path = OUTPUT_ANALYTICS / "executive_summary.json"
    if exec_path.is_file():
        exec_summary = json.loads(exec_path.read_text(encoding="utf-8"))
    summary_slim = {
        "mean_calibrated_risk": exec_summary.get("mean_calibrated_risk"),
        "n_subscribers": exec_summary.get("n_subscribers"),
        "narratives": exec_summary.get("narratives", {}),
        "generated_at_utc": exec_summary.get("generated_at_utc"),
    }
    (OUTPUT_DASHBOARD / "executive_summary.json").write_text(
        json.dumps(summary_slim, indent=2, default=str), encoding="utf-8"
    )


def main() -> None:
    """CLI entry point for the analytics pipeline.

    Parses no arguments (all paths from config). Runs the full pipeline,
    prints progress, and exits with code 1 if governance checks fail.
    """
    _timer("Starting analytics pipeline...")
    print(f"  Schema: {ANALYTICS_SCHEMA_VERSION}")
    print(f"  Output: {OUTPUT_ANALYTICS}")
    print()
    manifest = run_analytics_pipeline()
    if not manifest.get("compatible", True):
        print("\nWARNING: Governance checks found compatibility issues.")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
