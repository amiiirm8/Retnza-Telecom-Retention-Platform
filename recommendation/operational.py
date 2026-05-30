"""Structured CRM / BI operational metadata for retention campaigns.

Maps rule_id + risk_tier to concrete delivery fields used by CRM systems:
channels, cost tiers, urgency, queue labels, and intervention types.

Pipeline stage: inference/reporting-time (called by engine.py for every
subscriber after rule matching).

Key invariants:
  - All metadata is deterministic (pure lookup + tier-based demotion logic).
  - Low/Medium risk tiers demote costs and channels to avoid over-spending
    on subscribers who are not high-value retention targets.
  - C0-C4 cost tiers map to numeric budget levels for BI aggregation.
  - CRM queue labels align with operator campaign management system.
"""

from __future__ import annotations

from typing import Any

# Numeric offer budget tier: 0=none … 4=desk / ARPU-capped.
# Maps cost tier strings to integers for numeric aggregation in BI tools.
OFFER_BUDGET_NUMERIC: dict[str, int] = {
    "C0": 0,
    "C1": 1,
    "C2": 2,
    "C3": 3,
    "C4": 4,
}

OFFER_BUDGET_CAP_TYPE: dict[str, str] = {
    "C0": "none",
    "C1": "standard_digital",
    "C2": "targeted_bundle",
    "C3": "enhanced_bundle",
    "C4": "arpu_capped_save",
}

# Target response window in days per risk tier.
# Used by CRM to set SLAs. Low = None (no campaign urgency).
CAMPAIGN_URGENCY_DAYS: dict[str, int | None] = {
    "Very High": 2,
    "High": 7,
    "Medium": 30,
    "Low": None,
}

# CRM queue assignment for campaign management system.
# P1 = priority 1 (immediate), P2 = nurture, P4 = health check (no campaign).
CRM_QUEUE_BY_TIER: dict[str, str] = {
    "Very High": "retention_desk_p1",
    "High": "outbound_sms_call_p1",
    "Medium": "digital_nurture_p2",
    "Low": "monitor_health_p4",
}

CHANNEL_GROUP: dict[str, str] = {
    "desk_call": "human_outbound",
    "SMS": "digital_sms",
    "app_push": "digital_app",
    "USSD": "digital_ussd",
}

# Per-rule operational metadata: channels, costs, flags per rule_id.
# Each entry defines the default delivery for a rule before risk-tier
# adjustments are applied by resolve_delivery().
# R00_MONITOR is the no-action default. R99_HIGH_RISK_SAVE is the catch-all.
RULE_OPERATIONAL_META: dict[str, dict[str, Any]] = {
    "R01_PREPAID_INFANT": {
        "primary_channel": "SMS",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "low_medium",
    },
    "R02_PREPAID_5G": {
        "primary_channel": "SMS",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
    },
    "R03_VOLTE_ENABLE": {
        "primary_channel": "SMS",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C1",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "low",
    },
    "R04_VAS_ZERO": {
        "primary_channel": "USSD",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
    },
    "R05_BILL_SHOCK": {
        "primary_channel": "SMS",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
    },
    "R06_VAS_PARTIAL": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
    },
    "R07_LEGACY_2G": {
        "primary_channel": "SMS",
        "secondary_channel": "app_push",
        "campaign_cost_tier": "C1",
        "human_touch": False,
        "low_risk_channel_override": "SMS",
        "digital_only_flag": True,
        "retention_cost_estimate": "low",
    },
    "R08_POSTPAID_EARLY": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
    },
    "R09_RUBIKA_INACTIVE": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "low_medium",
        "campaign_channel_group": "ecosystem_digital",
    },
    "R10_EWANO_NON_ADOPTER": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C2",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium",
        "campaign_channel_group": "ecosystem_wallet",
    },
    "R11_HAMRAHMAN_LOW_ENGAGEMENT": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C1",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "low",
        "campaign_channel_group": "ecosystem_app",
    },
    "R12_ECOSYSTEM_POWER_USER": {
        "primary_channel": "app_push",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C3",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "medium_high",
        "campaign_channel_group": "loyalty_vip",
    },
    "R99_HIGH_RISK_SAVE": {
        "primary_channel": "desk_call",
        "secondary_channel": "SMS",
        "campaign_cost_tier": "C4",
        "human_touch": True,
        "digital_only_flag": False,
        "escalation_required": True,
        "retention_cost_estimate": "high",
        "is_fallback": True,
    },
    "R00_MONITOR": {
        "primary_channel": "SMS",
        "secondary_channel": None,
        "campaign_cost_tier": "C0",
        "human_touch": False,
        "digital_only_flag": True,
        "retention_cost_estimate": "minimal",
    },
}

# Tier-level operational parameters applied to all subscribers in a risk band.
# These override rule-level defaults in resolve_delivery() for consistency
# across subscribers in the same risk tier.
RISK_BAND_OPERATIONS: dict[str, dict[str, Any]] = {
    "Very High": {
        "campaign_urgency_days": 2,
        "contact_channel": "Outbound call + SMS",
        "offer_budget": "High (up to 1× monthly ARPU cap)",
    },
    "High": {
        "campaign_urgency_days": 7,
        "contact_channel": "SMS journey + optional call",
        "offer_budget": "Medium (targeted bundle / bonus data)",
    },
    "Medium": {
        "campaign_urgency_days": 30,
        "contact_channel": "Digital SMS / app push",
        "offer_budget": "Low (standard retention nudge)",
    },
    "Low": {
        "campaign_urgency_days": None,
        "contact_channel": "Quarterly health SMS",
        "offer_budget": "None",
    },
}


def resolve_delivery(rule_id: str, risk_tier: str) -> dict[str, Any]:
    """Map rule + risk tier to structured operational delivery fields.

    Rule-level defaults from RULE_OPERATIONAL_META are applied first, then
    risk-tier adjustments override them:
      - Low/Medium risk: demotes human touch, escalation, and cost tiers
        to avoid over-investing in low-value retention targets.
      - Cost demotion logic: C3/C4 → C2 (Medium) or C1 (Low).
        This prevents expensive desk-call budgets from being allocated to
        subscribers who are not at high risk.
      - Desk call channel is overridden to SMS for Low/Medium risk.
      - Intervention type is classified as high_touch_human (Very High/High
        with human touch), digital_retention (any rule but no human), or
        monitor_only (R00_MONITOR).

    Args:
        rule_id: The matched rule identifier (e.g. "R01_PREPAID_INFANT").
        risk_tier: Risk tier label ("Very High", "High", "Medium", "Low").

    Returns:
        Dict with keys: primary_channel, secondary_channel, campaign_cost_tier,
        offer_budget_numeric_tier, offer_budget_cap_type, human_touch_flag,
        digital_only_flag, escalation_required, action_assigned,
        intervention_type, is_fallback_rule, campaign_urgency_days, crm_queue,
        campaign_channel_group, retention_cost_estimate, contact_channel,
        offer_budget.

    Side effects:
        None.
    """
    meta = RULE_OPERATIONAL_META.get(rule_id, RULE_OPERATIONAL_META["R00_MONITOR"])
    primary = meta["primary_channel"]
    secondary = meta.get("secondary_channel")
    cost = meta["campaign_cost_tier"]
    human = bool(meta.get("human_touch", False))
    escalation = bool(meta.get("escalation_required", False))
    digital_only = bool(meta.get("digital_only_flag", True))

    # Low/Medium risk subscribers should not receive expensive human-touch
    # interventions or high-cost offers — the expected retention value does
    # not justify the spend.
    if risk_tier in ("Low", "Medium"):
        human = False
        escalation = False
        # Demote cost: C3/C4 → C2 for Medium, C1 for Low.
        if cost in ("C3", "C4"):
            cost = "C2" if risk_tier == "Medium" else "C1"
        # Desk call is too expensive for low-risk. Override to SMS
        # if the rule defines a low_risk_channel_override.
        if primary == "desk_call":
            primary = meta.get("low_risk_channel_override", "SMS")
            digital_only = True

    # Low risk: cap cost at C1 even if rule default is higher.
    if risk_tier == "Low" and cost not in ("C0", "C1"):
        cost = "C1"

    tier_ops = RISK_BAND_OPERATIONS.get(risk_tier, RISK_BAND_OPERATIONS["Low"])
    urgency_days = tier_ops.get("campaign_urgency_days")
    if human and risk_tier in ("Very High", "High"):
        intervention = "high_touch_human"
    elif rule_id != "R00_MONITOR":
        intervention = "digital_retention"
    else:
        intervention = "monitor_only"

    return {
        "primary_channel": primary,
        "secondary_channel": secondary or "",
        "campaign_cost_tier": cost,
        "offer_budget_numeric_tier": OFFER_BUDGET_NUMERIC.get(cost, 0),
        "offer_budget_cap_type": OFFER_BUDGET_CAP_TYPE.get(cost, "none"),
        "human_touch_flag": human,
        "digital_only_flag": digital_only and not human,
        "escalation_required": escalation and risk_tier in ("Very High", "High"),
        "action_assigned": rule_id != "R00_MONITOR",
        "intervention_type": intervention,
        "is_fallback_rule": bool(meta.get("is_fallback", False)),
        "campaign_urgency_days": urgency_days,
        "crm_queue": CRM_QUEUE_BY_TIER.get(risk_tier, "monitor_health_p4"),
        "campaign_channel_group": meta.get("campaign_channel_group")
        or CHANNEL_GROUP.get(primary, "digital_other"),
        "retention_cost_estimate": meta.get("retention_cost_estimate", "unknown"),
        "contact_channel": tier_ops["contact_channel"],
        "offer_budget": tier_ops["offer_budget"],
    }
