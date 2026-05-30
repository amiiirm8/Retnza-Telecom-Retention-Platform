"""Rule-based retention logic (not uplift / not causal).

Defines all business rules for retention recommendations, their precedence
order, the R99 fallback rule, and campaign priority mappings.

Pipeline stage: inference/reporting-time (rules engine.py uses these to
select per-subscriber actions).

Key invariants:
  - Every rule is deterministic (pure function of subscriber features).
  - Rules are evaluated in precedence order; the highest-precedence match wins.
  - R99 is a fallback for high-risk subscribers matched by no product rule.
  - SHAP does NOT select actions — rules always determine rule_id and action.
  - Ecosystem rules (R09-R12) reference registry-aligned column constants.
  - The FALLBACK_RULE's evaluate always returns True; it is only selected
    by engine.py when no other rule matched AND risk >= High threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from recommendation.ecosystem import COL_CAPABLE, COL_DIGITAL, COL_EWANO, COL_HAMRAHMAN, COL_RUBIKA, COL_VOLTE

RuleEvaluator = Callable[[pd.Series], bool]

MEDIUM_PLUS_TIERS = frozenset({"Medium", "High", "Very High"})


@dataclass(frozen=True)
class RecommendationRule:
    """A single deterministic retention business rule.

    Each rule represents a subscriber segment + recommended treatment.
    Rules are immutable (frozen=True) and evaluated in precedence order.

    Attributes:
        rule_id: Unique identifier (e.g. "R01_PREPAID_INFANT").
        trigger_condition: Human-readable summary of the matching criteria.
        top_driver_key: Feature column name that drives the rule match.
        top_driver_label: Business-friendly label for the top driver.
        business_rationale: Why this segment exists (business logic).
        recommended_action: CRM-readable action text for the treatment.
        expected_impact: Expected business outcome of the action.
        rule_priority: P1 (highest) through P4 (lowest).
        evaluate: Callable(row) -> bool predicate for matching.
        ecosystem_rule: True if this is an ecosystem product rule (R09-R12).
    """

    rule_id: str
    trigger_condition: str
    top_driver_key: str
    top_driver_label: str
    business_rationale: str
    recommended_action: str
    expected_impact: str
    rule_priority: str
    evaluate: RuleEvaluator
    ecosystem_rule: bool = False

    def to_dict(self) -> dict[str, str]:
        """Serialize rule to dict for manifest JSON / API responses.

        The evaluate callable is intentionally excluded (not serializable).
        The ecosystem_rule bool is stored as a string for JSON compatibility.

        Returns:
            Dict with rule metadata suitable for JSON serialization.
        """
        return {
            "rule_id": self.rule_id,
            "trigger_condition": self.trigger_condition,
            "top_driver": self.top_driver_label,
            "business_rationale": self.business_rationale,
            "recommended_action": self.recommended_action,
            "expected_impact": self.expected_impact,
            "rule_priority": self.rule_priority,
            "ecosystem_rule": str(self.ecosystem_rule),
        }


def _risk_medium_plus(row: pd.Series, risk_tier: str | None = None) -> bool:
    """Check if subscriber's risk is Medium or higher.

    Used by ecosystem rules (R09-R12) to gate their activation — ecosystem
    onboarding is not recommended for Low-risk subscribers.

    Args:
        row: Subscriber feature row (unused if risk_tier is provided).
        risk_tier: Pre-computed risk tier label (avoids recomputation).

    Returns:
        True if tier is Medium, High, or Very High.
        Falls back to churn_probability >= 0.15 if risk_tier is None.
    """
    if risk_tier:
        return risk_tier in MEDIUM_PLUS_TIERS
    return float(row.get("_churn_probability", 0)) >= 0.15


def _build_rules() -> list[RecommendationRule]:
    """Construct the full list of retention recommendation rules.

    Returns all product rules in no particular order (callers must apply
    RULE_PRECEDENCE_ORDER for matching). Rules are instantiated with
    lambda evaluators that reference the subscriber row dict.

    Returns:
        List of RecommendationRule instances. Does not include FALLBACK_RULE.
    """
    return [
        RecommendationRule(
            rule_id="R01_PREPAID_INFANT",
            trigger_condition="is_prepaid=1 AND sim_tenure_months<=6",
            top_driver_key="is_prepaid",
            top_driver_label="Prepaid SIM + very short tenure",
            business_rationale=(
                "Infant prepaid accounts show the highest observed churn; early recharge and "
                "onboarding friction drive exit before habit formation."
            ),
            recommended_action=(
                "Prepaid Welcome Save: 30-day onboarding SMS journey + 20% bonus credit on the "
                "next two recharges completed within 45 days (auto-applied on recharge)."
            ),
            expected_impact="Reduce first-90-day prepaid churn; target +15–25% recharge retention in cohort.",
            rule_priority="P1",
            evaluate=lambda r: r["is_prepaid"] == 1 and r["sim_tenure_months"] <= 6,
        ),
        RecommendationRule(
            rule_id="R02_PREPAID_5G",
            trigger_condition="prepaid_5g_risk_flag=1",
            top_driver_key="prepaid_5g_risk_flag",
            top_driver_label="Prepaid on 5G",
            business_rationale=(
                "Prepaid 5G subscribers combine high-speed product expectations with prepaid "
                "volatility; model and EDA both flag this segment as elevated risk."
            ),
            recommended_action=(
                "5G Retention Pack: 3-month discounted 5G night-unlimited add-on + outbound "
                "migration assessment for postpaid plan with waived SIM swap fee."
            ),
            expected_impact="Stabilize prepaid 5G base; improve stickiness via bundled data and postpaid path.",
            rule_priority="P1",
            evaluate=lambda r: r["prepaid_5g_risk_flag"] == 1,
        ),
        RecommendationRule(
            rule_id="R12_ECOSYSTEM_POWER_USER",
            trigger_condition="Rubika+EWANO+HamrahMan+VoLTE active",
            top_driver_key="ecosystem_embedded",
            top_driver_label="Multi-product ecosystem power user",
            business_rationale=(
                "Multi-product ecosystem users often show lower churn; preserve with loyalty "
                "programs rather than acquisition-style discounting."
            ),
            recommended_action=(
                "VIP Loyalty Preservation: premium bundle retention, priority support queue, "
                "cross-product rewards (Rubika + EWANO + Hamrah Man), no aggressive discounting."
            ),
            expected_impact="Preserve high-value ecosystem customers; prevent premium erosion.",
            rule_priority="P2",
            ecosystem_rule=True,
            evaluate=lambda r: (
                r.get(COL_RUBIKA, -1) == 1
                and r.get(COL_EWANO, -1) == 1
                and r.get(COL_HAMRAHMAN, 0) == 1
                and r.get(COL_VOLTE, -1) == 1
            ),
        ),
        RecommendationRule(
            rule_id="R05_BILL_SHOCK",
            trigger_condition="high_monthly_spend_flag=1 OR monthly_to_lifetime_arpu_ratio>=1.25",
            top_driver_key="monthly_to_lifetime_arpu_ratio",
            top_driver_label="High monthly spend or bill spike vs history",
            business_rationale=(
                "Elevated monthly spend or spend spike vs lifetime average suggests bill shock "
                "or plan mismatch—associated with higher churn in the model."
            ),
            recommended_action=(
                "Bill Shock Prevention: proactive SMS with itemized spend + optional plan downgrade "
                "or 15% discount on next monthly invoice for 6-month stay commitment (digital accept)."
            ),
            expected_impact="Lower involuntary churn from bill disputes; protect ARPU on high-value lines.",
            rule_priority="P2",
            evaluate=lambda r: r["high_monthly_spend_flag"] == 1
            or r["monthly_to_lifetime_arpu_ratio"] >= 1.25,
        ),
        RecommendationRule(
            rule_id="R09_RUBIKA_INACTIVE",
            trigger_condition="rubika_user_flag=0 AND is_data_capable=1 AND medium+ risk",
            top_driver_key=COL_RUBIKA,
            top_driver_label="Rubika non-adopter (data-capable)",
            business_rationale=(
                "Lack of Rubika engagement may indicate weak platform stickiness and low "
                "embeddedness in the operator social ecosystem."
            ),
            recommended_action=(
                "Rubika Onboarding: discounted in-app traffic, exclusive content bundle, "
                "social engagement incentives via app push + SMS deep link."
            ),
            expected_impact="Improve ecosystem attachment and digital engagement; reduce switching likelihood.",
            rule_priority="P2",
            ecosystem_rule=True,
            evaluate=lambda r: (
                r.get(COL_RUBIKA, -1) == 0
                and r.get(COL_CAPABLE, 0) == 1
                and _risk_medium_plus(r, r.get("_risk_tier"))
            ),
        ),
        RecommendationRule(
            rule_id="R10_EWANO_NON_ADOPTER",
            trigger_condition="ewano_user_flag=0 AND (prepaid OR early tenure) AND data capable",
            top_driver_key=COL_EWANO,
            top_driver_label="EWANO non-adopter",
            business_rationale=(
                "Financial ecosystem participation is associated with recharge retention through "
                "payment habit formation and wallet dependency."
            ),
            recommended_action=(
                "EWANO Activation: cashback on first bill payment, recharge bonus via EWANO wallet, "
                "targeted app journey for prepaid and early-tenure segments."
            ),
            expected_impact="Increase wallet adoption and ecosystem switching costs.",
            rule_priority="P2",
            ecosystem_rule=True,
            evaluate=lambda r: (
                r.get(COL_EWANO, -1) == 0
                and r.get(COL_CAPABLE, 0) == 1
                and (r["is_prepaid"] == 1 or r.get("early_lifecycle_flag", 0) == 1)
                and _risk_medium_plus(r, r.get("_risk_tier"))
            ),
        ),
        RecommendationRule(
            rule_id="R11_HAMRAHMAN_LOW_ENGAGEMENT",
            trigger_condition="hamrahman_user_flag=0 OR low digital_engagement_score",
            top_driver_key=COL_HAMRAHMAN,
            top_driver_label="Low Hamrah Man / digital ecosystem engagement",
            business_rationale=(
                "Low self-service and app adoption often correlates with weaker engagement "
                "and higher friction in digital servicing."
            ),
            recommended_action=(
                "Hamrah Man Onboarding: app-only retention offers, usage rewards, guided "
                "self-service setup journey (SMS + app push)."
            ),
            expected_impact="Increase app engagement and digital servicing stickiness.",
            rule_priority="P2",
            ecosystem_rule=True,
            evaluate=lambda r: (
                r.get(COL_CAPABLE, 0) == 1
                and _risk_medium_plus(r, r.get("_risk_tier"))
                and (
                    r.get(COL_HAMRAHMAN, 0) == 0
                    or r.get(COL_DIGITAL, 0) <= 1
                )
            ),
        ),
        RecommendationRule(
            rule_id="R03_VOLTE_ENABLE",
            trigger_condition="volte_non_adopter_capable=1 AND is_data_capable=1",
            top_driver_key="volte_non_adopter_capable",
            top_driver_label="VoLTE not adopted (data-capable)",
            business_rationale=(
                "Non-adoption of VoLTE among data-capable users correlates with higher churn; "
                "often indicates handset/settings friction or under-provisioned experience."
            ),
            recommended_action=(
                "VoLTE Activation Push: one-tap provisioning SMS + 5GB bonus data after first "
                "successful VoLTE call within 14 days (tracked via network provisioning)."
            ),
            expected_impact="Increase VoLTE attach rate; expected churn reduction among capable non-adopters.",
            rule_priority="P2",
            evaluate=lambda r: r["volte_non_adopter_capable"] == 1 and r["is_data_capable"] == 1,
        ),
        RecommendationRule(
            rule_id="R04_VAS_ZERO",
            trigger_condition="zero_vas_capable_flag=1",
            top_driver_key="zero_vas_capable_flag",
            top_driver_label="Data-capable with no active VAS",
            business_rationale=(
                "Zero VAS among data-capable customers signals low product embedding; EDA shows "
                "steep churn gradient as VAS count increases."
            ),
            recommended_action=(
                "VAS Starter Bundle: 60-day trial of operator cloud (5GB) + night internet at "
                "50% off; single opt-in via USSD *code* or app banner."
            ),
            expected_impact="Lift VAS adoption and switching costs; improve 90-day retention in zero-VAS cohort.",
            rule_priority="P2",
            evaluate=lambda r: r["zero_vas_capable_flag"] == 1,
        ),
        RecommendationRule(
            rule_id="R06_VAS_PARTIAL",
            trigger_condition="is_data_capable=1 AND vas_adoption_count IN (1,2)",
            top_driver_key="vas_adoption_count",
            top_driver_label="Low VAS penetration (1–2 products)",
            business_rationale=(
                "Partial VAS adoption leaves uplift room; expanding to 3+ VAS products is "
                "associated with materially lower churn in EDA."
            ),
            recommended_action=(
                "Stickiness Cross-sell: 7-day international roaming pass + super-app financial "
                "wallet activation with 50,000 Toman cashback on first bill payment via wallet."
            ),
            expected_impact="Increase multi-product attach; move customers up VAS adoption ladder.",
            rule_priority="P3",
            evaluate=lambda r: r["is_data_capable"] == 1 and r["vas_adoption_count"] in (1, 2),
        ),
        RecommendationRule(
            rule_id="R08_POSTPAID_EARLY",
            trigger_condition="is_prepaid=0 AND early_lifecycle_flag=1",
            top_driver_key="early_lifecycle_flag",
            top_driver_label="First-year postpaid subscriber",
            business_rationale=(
                "Postpaid early lifecycle still shows elevated churn risk vs tenured base; "
                "loyalty lock before month-12 decision window."
            ),
            recommended_action=(
                "Postpaid Loyalty Lock: 10% loyalty discount on months 7–12 when customer "
                "accepts e-bill + auto-pay setup within 14 days (contract amendment digital)."
            ),
            expected_impact="Extend postpaid tenure through first contract year; reduce early postpaid churn.",
            rule_priority="P3",
            evaluate=lambda r: r["is_prepaid"] == 0 and r["early_lifecycle_flag"] == 1,
        ),
        RecommendationRule(
            rule_id="R07_LEGACY_2G",
            trigger_condition="is_data_capable=0 (2G)",
            top_driver_key="is_data_capable",
            top_driver_label="Legacy 2G / voice-centric line",
            business_rationale=(
                "2G subscribers lack data service context; upsell path is migration to 3G/4G "
                "rather than data VAS campaigns."
            ),
            recommended_action=(
                "Legacy Migration Offer: free SIM swap + 3-month introductory 4G data pack "
                "(5GB/month) at 40% discount when upgrading network generation in-store or app."
            ),
            expected_impact="Migrate voice-only users to data-capable plans; reduce segment churn via modern plan fit.",
            rule_priority="P3",
            evaluate=lambda r: r["is_data_capable"] == 0,
        ),
    ]


# Precedence order for rule matching — first in list wins.
# Rationale:
#   - P1 rules (infant, 5G) fire first (highest urgency segments).
#   - R12 ecosystem power user fires before other ecosystem rules because
#     a subscriber who qualifies as both "power user" and "inactive Rubika"
#     should be treated as a power user (positive framing).
#   - Product/ecosystem rules (R03-R12) fire before VAS cross-sell (R06)
#     and legacy migration (R07) because they address specific risk drivers.
#   - R07_LEGACY_2G fires last because 2G subscribers are structurally
#     different (no data) and should only be matched if no data-capable
#     rule is relevant.
RULE_PRECEDENCE_ORDER = [
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

# Fallback rule for high-risk subscribers with no product rule match.
# evaluate always returns True — the caller (engine.py) selects this rule
# only when risk >= High AND no product rule fired. It is NOT in the
# _build_rules() list because it should never be evaluated in the normal
# precedence loop (it would match everyone).
FALLBACK_RULE = RecommendationRule(
    rule_id="R99_HIGH_RISK_SAVE",
    trigger_condition="churn_probability>=High tier AND no_other_rule_matched",
    top_driver_key="churn_probability",
    top_driver_label="Elevated model churn score (composite)",
    business_rationale=(
        "Safety-net only: fires when calibrated risk >= High tier and no product rule matched. "
        "Not a preferred campaign—use sparingly vs targeted plays."
    ),
    recommended_action=(
        "Retention Desk Save Call: specialist callback within 48h with personalized offer "
        "(credit up to 1× monthly ARPU cap or equivalent free data for 30 days)."
    ),
    expected_impact="Catch-all for high-risk saves; prevent unactioned high-score customers.",
    rule_priority="P1",
    evaluate=lambda r: True,
)

# Risk-tier → campaign priority mapping used by engine.py.
# Very High and High both map to P1 (same-day/week queue).
# Medium maps to P2 (digital nurture queue).
# Low maps to P4 (health monitoring) — no campaign action.
# Note: P3 is not used for risk-tier mapping but is used by some rules
# (e.g. R06_VAS_PARTIAL, R07_LEGACY_2G, R08_POSTPAID_EARLY).
CAMPAIGN_PRIORITY_BY_TIER = {
    "Very High": "P1",
    "High": "P1",
    "Medium": "P2",
    "Low": "P4",
}

COST_TIER_DEFINITIONS = {
    "C0": "No offer spend (monitoring / health SMS only)",
    "C1": "Low (automated SMS / app push, no agent)",
    "C2": "Medium (USSD / digital bundle / auto-credit)",
    "C3": "Medium-high (optional outbound call queue)",
    "C4": "High (retention desk call + ARPU-capped save offer)",
}
