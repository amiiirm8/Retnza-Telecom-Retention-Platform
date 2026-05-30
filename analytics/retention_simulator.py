"""Retention KPI / ROI scenario simulator (NOT uplift / NOT causal).

Workflow stage: reporting-time (step 4 of 8).

Supports optimistic, realistic, and conservative scenarios given save rate,
conversion rate, campaign reach, cost, ARPU retention, and ecosystem uplift
assumptions. Produces retained subscribers, retained revenue, churn reduction
estimates, protected ARPU, ROI, and digital vs human-touch efficiency.

Pipeline position: runs after rule diagnostics, before campaign saturation.
Reads recommendation data to compute base rates and segment sizes.

Key invariants:
  - NOT uplift modeling. Scenarios are illustrative projections based on
    assumed parameters, not causal treatment effect estimates.
  - All outputs include a disclaimer making this explicit.
  - Recommended scenario is 'realistic' by default (mid-range assumptions).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    OUTPUT_ANALYTICS,
    RECOMMENDATIONS_PATH,
)


@dataclass
class ScenarioParams:
    """Assumptions for a single simulation scenario.

    All parameters are illustrative input assumptions, not estimated effects.
    Used by simulate_scenario() to produce KPI projections.

    Attributes:
        label: Scenario name (optimistic, realistic, conservative).
        save_rate: Fraction of reached high-risk subscribers retained.
        conversion_rate: Fraction of saved subscribers who convert on upsell.
        campaign_reach: Fraction of high-risk base reached by campaign.
        campaign_cost_per_subscriber: Cost per reached subscriber.
        avg_arpu_retention_months: Months of ARPU retained per saved sub.
        arpu_monthly: Average monthly ARPU (toman).
        ecosystem_uplift_factor: Fractional revenue uplift from ecosystem cross-sell.
        digital_cost_per_subscriber: Cost per digital-only intervention.
        human_touch_cost_per_subscriber: Cost per human-touch intervention.
    """
    label: str
    save_rate: float
    conversion_rate: float
    campaign_reach: float
    campaign_cost_per_subscriber: float
    avg_arpu_retention_months: int
    arpu_monthly: float
    ecosystem_uplift_factor: float
    digital_cost_per_subscriber: float = 0.50
    human_touch_cost_per_subscriber: float = 10.0


SCENARIOS = {
    "optimistic": ScenarioParams(
        label="optimistic",
        save_rate=0.35,
        conversion_rate=0.25,
        campaign_reach=0.90,
        campaign_cost_per_subscriber=2.00,
        avg_arpu_retention_months=6,
        arpu_monthly=85000,
        ecosystem_uplift_factor=0.15,
    ),
    "realistic": ScenarioParams(
        label="realistic",
        save_rate=0.20,
        conversion_rate=0.15,
        campaign_reach=0.75,
        campaign_cost_per_subscriber=3.50,
        avg_arpu_retention_months=4,
        arpu_monthly=75000,
        ecosystem_uplift_factor=0.08,
    ),
    "conservative": ScenarioParams(
        label="conservative",
        save_rate=0.10,
        conversion_rate=0.08,
        campaign_reach=0.60,
        campaign_cost_per_subscriber=5.00,
        avg_arpu_retention_months=3,
        arpu_monthly=65000,
        ecosystem_uplift_factor=0.04,
    ),
}


def simulate_scenario(
    params: ScenarioParams,
    n_high_risk: int,
    n_digital_only: int,
    n_human_touch: int,
    base_churn_rate: float,
) -> dict[str, Any]:
    """Run a single retention scenario with given assumptions.

    Computes: reached/saved/converted/retained subscriber counts, retained
    revenue (base + ecosystem uplift), campaign costs (digital + human-touch),
    churn reduction estimate, protected ARPU, ROI, and channel efficiency.

    All outputs are illustrative projections based on assumed parameters,
    not causal estimates.

    Args:
        params: ScenarioParams defining save_rate, conversion_rate, costs, etc.
        n_high_risk: Number of Very High + High risk subscribers.
        n_digital_only: Number of digital-only intervention subscribers.
        n_human_touch: Number of human-touch intervention subscribers.
        base_churn_rate: Mean churn probability across the base.

    Returns:
        dict with scenario name, assumptions, inputs, outputs (including
        retained_subscribers, retained_revenue_toman, roi, etc.), and
        disclaimer.
    """
    reached = int(n_high_risk * params.campaign_reach)
    saved = int(reached * params.save_rate)
    converted = int(saved * params.conversion_rate)

    retained_subscribers = saved + converted
    retained_revenue = retained_subscribers * params.arpu_monthly * params.avg_arpu_retention_months
    ecosystem_revenue_boost = retained_revenue * params.ecosystem_uplift_factor
    total_retained_revenue = retained_revenue + ecosystem_revenue_boost

    digital_cost = n_digital_only * params.digital_cost_per_subscriber * params.campaign_reach
    human_touch_cost = n_human_touch * params.human_touch_cost_per_subscriber * params.campaign_reach
    total_campaign_cost = reached * params.campaign_cost_per_subscriber + digital_cost + human_touch_cost

    churn_reduction_estimate = saved / max(n_high_risk, 1) * base_churn_rate
    protected_arpu = total_retained_revenue / max(retained_subscribers, 1) / max(params.avg_arpu_retention_months, 1)

    roi = (
        (total_retained_revenue - total_campaign_cost) / max(total_campaign_cost, 1)
        if total_campaign_cost > 0
        else 0.0
    )

    digital_efficiency = saved / max(digital_cost, 1) if digital_cost > 0 else 0
    human_touch_efficiency = saved / max(human_touch_cost, 1) if human_touch_cost > 0 else 0

    return {
        "scenario": params.label,
        "assumptions": {
            "save_rate": params.save_rate,
            "conversion_rate": params.conversion_rate,
            "campaign_reach": params.campaign_reach,
            "campaign_cost_per_subscriber": params.campaign_cost_per_subscriber,
            "arpu_monthly": params.arpu_monthly,
            "avg_retention_months": params.avg_arpu_retention_months,
            "ecosystem_uplift_factor": params.ecosystem_uplift_factor,
        },
        "inputs": {
            "n_high_risk_subscribers": n_high_risk,
            "n_digital_only": n_digital_only,
            "n_human_touch": n_human_touch,
            "base_churn_rate": base_churn_rate,
        },
        "outputs": {
            "reached_subscribers": reached,
            "saved_subscribers": saved,
            "converted_subscribers": converted,
            "retained_subscribers": retained_subscribers,
            "retained_revenue_toman": round(total_retained_revenue, 0),
            "churn_reduction_estimate": round(churn_reduction_estimate, 4),
            "protected_arpu_toman": round(protected_arpu, 0),
            "total_campaign_cost_toman": round(total_campaign_cost, 0),
            "roi": round(roi, 2),
            "digital_channel_efficiency": round(digital_efficiency, 2),
            "human_touch_efficiency": round(human_touch_efficiency, 2),
            "digital_cost_toman": round(digital_cost, 0),
            "human_touch_cost_toman": round(human_touch_cost, 0),
        },
        "disclaimer": (
            f"{params.label.capitalize()} scenario — estimates are illustrative and "
            f"based on assumed parameters, not causal uplift modeling. "
            f"Actual results depend on campaign execution and market conditions."
        ),
    }


def compute_retention_simulation(
    rec_path: Path = RECOMMENDATIONS_PATH,
) -> dict[str, Any]:
    """Run all simulation scenarios and produce ROI table.

    Reads recommendation data, computes base metrics (n_high_risk, etc.),
    runs all three scenarios (optimistic, realistic, conservative), and
    produces the executive KPI summary with ROI table.

    Args:
        rec_path: Path to subscriber_recommendations.parquet.

    Returns:
        dict with schema_version, generated_at_utc, n_high_risk,
        n_digital_only, n_human_touch, base_churn_rate, scenarios (3),
        recommended_scenario, recommendation_rationale, and disclaimer.

    Side effects:
        Writes retention_simulation_summary.json and
        campaign_roi_table.parquet to OUTPUT_ANALYTICS.
    """
    rec = pd.read_parquet(rec_path)

    n_high_risk = int(rec["risk_tier"].isin(["Very High", "High"]).sum())
    n_digital_only = int(rec.get("digital_only_flag", pd.Series([True])).sum())
    n_human_touch = int(rec.get("human_touch_flag", pd.Series([False])).sum())
    base_churn_rate = float(rec["churn_probability"].mean())

    results: dict[str, Any] = {}
    roi_rows: list[dict[str, Any]] = []

    for scenario_key, params in SCENARIOS.items():
        result = simulate_scenario(
            params, n_high_risk, n_digital_only, n_human_touch, base_churn_rate,
        )
        results[scenario_key] = result
        roi_rows.append({
            "scenario": scenario_key,
            "retained_subscribers": result["outputs"]["retained_subscribers"],
            "retained_revenue_toman": result["outputs"]["retained_revenue_toman"],
            "churn_reduction_estimate": result["outputs"]["churn_reduction_estimate"],
            "protected_arpu_toman": result["outputs"]["protected_arpu_toman"],
            "total_cost_toman": result["outputs"]["total_campaign_cost_toman"],
            "roi": result["outputs"]["roi"],
            "digital_efficiency": result["outputs"]["digital_channel_efficiency"],
            "human_touch_efficiency": result["outputs"]["human_touch_efficiency"],
        })

    roi_df = pd.DataFrame(roi_rows)

    executive_kpi = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_high_risk": n_high_risk,
        "n_digital_only": n_digital_only,
        "n_human_touch": n_human_touch,
        "base_churn_rate": round(base_churn_rate, 4),
        "scenarios": results,
        "recommended_scenario": "realistic",
        "recommendation_rationale": (
            "Realistic scenario uses mid-range assumptions consistent with "
            "observed industry retention campaign benchmarks. "
            "Optimistic assumes above-average conversion; conservative assumes "
            "minimum guaranteed performance."
        ),
        # Scenarios are illustrative, not causal uplift estimates. This platform
        # does not perform treatment effect estimation or A/B uplift modeling.
        # Parameters (save_rate, conversion_rate, etc.) are user assumptions,
        # not statistically estimated effects.
        "disclaimer": (
            "These are illustrative KPI projections, not causal estimates. "
            "Retention simulation does not use uplift modeling or treatment effect estimation. "
            "All figures are based on assumed scenario parameters and observed base rates."
        ),
    }

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_ANALYTICS / "retention_simulation_summary.json", "w") as f:
        json.dump(executive_kpi, f, indent=2, default=str)
    roi_df.to_parquet(OUTPUT_ANALYTICS / "campaign_roi_table.parquet", index=False)

    return executive_kpi


def compute_executive_kpi_snapshot(
    executive_kpi: dict[str, Any],
) -> dict[str, Any]:
    """Build condensed executive KPI snapshot from simulation results.

    Extracts key metrics (retained subscribers, revenue, ROI, cost) for
    each scenario into a lightweight dict for dashboard consumption.

    Args:
        executive_kpi: Full KPI dict from compute_retention_simulation().

    Returns:
        dict with schema_version, generated_at_utc, high_risk_subscribers,
        base_churn_rate, and projections (per-scenario KPI subset).
    """
    snapshot = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "high_risk_subscribers": executive_kpi["n_high_risk"],
        "base_churn_rate": executive_kpi["base_churn_rate"],
        "projections": {},
    }
    for scenario, result in executive_kpi["scenarios"].items():
        snapshot["projections"][scenario] = {
            "retained_subscribers": result["outputs"]["retained_subscribers"],
            "retained_revenue_toman": result["outputs"]["retained_revenue_toman"],
            "roi": result["outputs"]["roi"],
            "campaign_cost_toman": result["outputs"]["total_campaign_cost_toman"],
        }
    return snapshot
