"""Campaign saturation analytics — queue sizes, channel load, overload risk.

Analyses CRM queue loads, SMS volume, outbound-call load, P1 concentration,
fallback concentration, and channel overload risk indicators.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.config import (
    ANALYTICS_SCHEMA_VERSION,
    OUTPUT_ANALYTICS,
    RECOMMENDATIONS_PATH,
    RECOMMENDATIONS_MANIFEST_PATH,
)

# Saturation thresholds are advisory, not hard limits.
# Chosen based on operational experience: P1 >50% overwhelms desk, fallback >20%
# indicates rule gap, SMS >60% risks fatigue, outbound call >30% exceeds capacity,
# human-touch >40% exceeds agent availability.
# These are not equilibrium or optimization thresholds; they flag advisory concerns.
SATURATION_THRESHOLD_P1 = 0.50
SATURATION_THRESHOLD_FALLBACK = 0.20
SATURATION_THRESHOLD_SMS = 0.60
SATURATION_THRESHOLD_CALL = 0.30
SATURATION_THRESHOLD_CHANNEL = 0.40


def compute_campaign_saturation(
    rec_path: Path = RECOMMENDATIONS_PATH,
    manifest_path: Path = RECOMMENDATIONS_MANIFEST_PATH,
) -> dict[str, Any]:
    """Compute campaign saturation and channel overload risk metrics.

    Analyses CRM queue loads, P1 concentration, fallback rule dependency,
    SMS/outbound-call/app-push channel saturation, and digital vs human-touch
    intervention ratios. Flags overload risks where advisory thresholds are
    exceeded.

    Args:
        rec_path: Path to subscriber_recommendations.parquet (recommendation).
        manifest_path: Path to recommendation_manifest.json (for metadata).

    Returns:
        dict with keys: schema_version, generated_at_utc, n_total_subscribers,
        queue_breakdown, total_queued, p1_count, p1_concentration,
        fallback_count, fallback_concentration, channel_breakdown,
        sms_volume_pct, outbound_call_volume_pct, app_push_volume_pct,
        digital_only_pct, human_touch_pct, overload_risks, n_overload_risks,
        saturation_disclaimer.

    Side effects:
        Writes campaign_saturation_summary.json and crm_queue_loads.parquet
        to OUTPUT_ANALYTICS.
    """
    rec = pd.read_parquet(rec_path)
    n_book = len(rec)

    queue_loads = rec["crm_queue"].value_counts().to_dict()
    total_queued = sum(queue_loads.values())

    p1_count = int((rec["campaign_priority"] == "P1").sum())
    p1_concentration = p1_count / max(n_book, 1)

    fallback_count = int((rec["rule_id"] == "R99_HIGH_RISK_SAVE").sum())
    fallback_concentration = fallback_count / max(n_book, 1)

    digital_only_count = int(rec.get("digital_only_flag", pd.Series([True])).sum())
    digital_only_pct = digital_only_count / max(n_book, 1)

    human_touch_count = int(rec.get("human_touch_flag", pd.Series([False])).sum())
    human_touch_pct = human_touch_count / max(n_book, 1)

    sms_count = int((rec.get("primary_channel", "") == "SMS").sum())
    sms_volume_pct = sms_count / max(n_book, 1)

    call_count = int((rec.get("primary_channel", "") == "desk_call").sum())
    call_volume_pct = call_count / max(n_book, 1)

    app_push_count = int((rec.get("primary_channel", "") == "app_push").sum())
    app_push_pct = app_push_count / max(n_book, 1)

    channel_breakdown = {
        str(ch): int(c)
        for ch, c in rec.get("primary_channel", pd.Series()).value_counts().to_dict().items()
    }

    overload_risks: list[dict[str, Any]] = []
    if p1_concentration > SATURATION_THRESHOLD_P1:
        overload_risks.append({
            "risk_area": "p1_concentration",
            "metric": "p1_share",
            "value": round(p1_concentration, 4),
            "threshold": SATURATION_THRESHOLD_P1,
            "detail": (
                f"P1 campaigns represent {p1_concentration:.1%} of queue; "
                f"may overload retention desk capacity."
            ),
        })
    if fallback_concentration > SATURATION_THRESHOLD_FALLBACK:
        overload_risks.append({
            "risk_area": "fallback_rule_dependency",
            "metric": "fallback_share",
            "value": round(fallback_concentration, 4),
            "threshold": SATURATION_THRESHOLD_FALLBACK,
            "detail": (
                f"Fallback rule R99 covers {fallback_concentration:.1%} of high-risk base; "
                f"indicates product rules may need expansion."
            ),
        })
    if sms_volume_pct > SATURATION_THRESHOLD_SMS:
        overload_risks.append({
            "risk_area": "sms_channel_saturation",
            "metric": "sms_share",
            "value": round(sms_volume_pct, 4),
            "threshold": SATURATION_THRESHOLD_SMS,
            "detail": (
                f"SMS channel used for {sms_volume_pct:.1%} of actions; "
                f"risk of SMS fatigue and campaign blindness."
            ),
        })
    if call_volume_pct > SATURATION_THRESHOLD_CALL:
        overload_risks.append({
            "risk_area": "outbound_call_saturation",
            "metric": "call_share",
            "value": round(call_volume_pct, 4),
            "threshold": SATURATION_THRESHOLD_CALL,
            "detail": (
                f"Outbound calls represent {call_volume_pct:.1%} of actions; "
                f"may exceed contact centre capacity."
            ),
        })
    if human_touch_pct > SATURATION_THRESHOLD_CHANNEL:
        overload_risks.append({
            "risk_area": "human_touch_saturation",
            "metric": "human_touch_share",
            "value": round(human_touch_pct, 4),
            "threshold": SATURATION_THRESHOLD_CHANNEL,
            "detail": (
                f"Human-touch interventions represent {human_touch_pct:.1%} of actions; "
                f"may exceed agent availability."
            ),
        })

    summary = {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_total_subscribers": n_book,
        "queue_breakdown": {str(k): int(v) for k, v in queue_loads.items()},
        "total_queued": total_queued,
        "p1_count": p1_count,
        "p1_concentration": round(p1_concentration, 4),
        "fallback_count": fallback_count,
        "fallback_concentration": round(fallback_concentration, 4),
        "channel_breakdown": channel_breakdown,
        "sms_volume_pct": round(sms_volume_pct, 4),
        "outbound_call_volume_pct": round(call_volume_pct, 4),
        "app_push_volume_pct": round(app_push_pct, 4),
        "digital_only_pct": round(digital_only_pct, 4),
        "human_touch_pct": round(human_touch_pct, 4),
        "overload_risks": overload_risks,
        "n_overload_risks": len(overload_risks),
        "saturation_disclaimer": (
            "Saturation thresholds are advisory. Actual operational capacity "
            "depends on contact centre staffing, campaign schedule, and channel throughput."
        ),
    }

    OUTPUT_ANALYTICS.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_ANALYTICS / "campaign_saturation_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    crm_loads = rec[["subscriber_id", "crm_queue", "campaign_priority", "rule_id",
                     "primary_channel", "human_touch_flag", "digital_only_flag",
                     "is_fallback_rule", "churn_probability", "risk_tier"]].copy()
    crm_loads.to_parquet(OUTPUT_ANALYTICS / "crm_queue_loads.parquet", index=False)

    return summary
