"""
Subscriber profile endpoint — unified view of a single subscriber's ML output.

Pipeline position:
  The richest endpoint in the API. Combines demographic profile, churn scores,
  recommendation, ecosystem profile, SHAP explanations, campaign metadata, and
  governance metadata into one response for CRM agents.

Workflow stage:
  GET /api/v1/subscribers/{subscriber_id} -> SubscriberProfile

Security:
  Requires authentication via CurrentUser dependency.
  Returns 404 if the subscriber does not exist in the database.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.runtime_config import load_runtime_config
from app.models.recommendation import Recommendation
from app.models.shap_explanation import ShapExplanation
from app.models.subscriber import Subscriber
from app.schemas.recommendation import RecommendationItem
from app.schemas.shap import ShapDriver
from app.schemas.subscriber import (
    CampaignMetadata,
    GovernanceMetadata,
    SubscriberEcosystemProfile,
    SubscriberProfile,
    SubscriberScore,
    SubscriberShapExplanation,
)

router = APIRouter()


def _drivers(raw: str | None) -> list[ShapDriver]:
    """
    Parse a JSON blob of SHAP drivers into a list of ShapDriver objects.

    Returns an empty list on any parsing failure to avoid breaking the subscriber
    profile endpoint due to corrupt SHAP data.
    """
    if not raw:
        return []
    try:
        return [ShapDriver(**item) for item in json.loads(raw)]
    except (TypeError, json.JSONDecodeError, ValueError):
        return []


def _recommendation_item(row: Recommendation | None) -> RecommendationItem | None:
    """
    Map a Recommendation ORM row to a RecommendationItem schema, or None.

    Args:
        row: Recommendation row or None.

    Returns:
        RecommendationItem or None if no recommendation exists for the subscriber.
    """
    if row is None:
        return None
    return RecommendationItem(
        subscriber_id=row.subscriber_id,
        churn_probability=row.churn_probability,
        churn_probability_raw=row.churn_probability_raw,
        risk_tier=row.risk_tier,
        rule_id=row.rule_id,
        recommended_action=row.recommended_action,
        campaign_priority=row.campaign_priority,
        campaign_cost_tier=row.campaign_cost_tier,
        campaign_queue_rank=row.campaign_queue_rank,
        crm_queue=row.crm_queue,
        digital_only_flag=row.digital_only_flag,
        escalation_required=row.escalation_required,
        human_touch_flag=row.human_touch_flag,
        primary_channel=row.primary_channel,
        secondary_channel=row.secondary_channel,
        campaign_channel_group=row.campaign_channel_group,
        intervention_type=row.intervention_type,
        ecosystem_segment=row.ecosystem_segment,
        ecosystem_retention_strategy=row.ecosystem_retention_strategy,
        rule_top_driver=row.rule_top_driver,
        shap_top_driver=row.shap_top_driver,
        final_top_driver=row.final_top_driver,
        final_top_driver_source=row.final_top_driver_source,
        top_driver=row.top_driver,
    )


def _ecosystem_profile(sub: Subscriber, rec: Recommendation | None) -> SubscriberEcosystemProfile:
    """
    Build an ecosystem profile from either the recommendation row or subscriber record.

    Prefers the recommendation row as source when available (it has the enriched
    ecosystem fields from the pipeline), falling back to the base subscriber record.
    """
    source: Any = rec or sub
    return SubscriberEcosystemProfile(
        has_rubika=getattr(source, "has_rubika", None),
        has_ewano=getattr(source, "has_ewano", None),
        has_hamrahman=getattr(source, "has_hamrahman", None),
        has_volte=getattr(source, "has_volte", None),
        ecosystem_product_count=getattr(source, "ecosystem_product_count", None),
        ecosystem_engagement_level=getattr(source, "ecosystem_engagement_level", None),
        ecosystem_segment=getattr(source, "ecosystem_segment", None),
        ecosystem_risk_gap=getattr(source, "ecosystem_risk_gap", None),
        ecosystem_retention_strategy=getattr(source, "ecosystem_retention_strategy", None),
    )


@router.get("/{subscriber_id}", response_model=SubscriberProfile)
async def get_subscriber(subscriber_id: int, db: DbSession, _user: CurrentUser) -> SubscriberProfile:
    """
    Return the full ML profile for a single subscriber.

    Aggregates data from the subscriber record, their recommendation row, SHAP
    explanation, and current runtime config into one rich response. Any component
    that is missing (e.g., no recommendation yet) returns null for relevant fields.

    Args:
        subscriber_id: Subscriber ID to look up.
        db: Database session (injected dependency).
        _user: Authenticated user (enforced by auth dependency).

    Returns:
        SubscriberProfile with all ML output and metadata.

    Raises:
        HTTPException 404: If the subscriber does not exist.
    """
    sub = await db.get(Subscriber, subscriber_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    rec_result = await db.execute(
        select(Recommendation).where(Recommendation.subscriber_id == subscriber_id)
    )
    recommendation = rec_result.scalar_one_or_none()
    shap_result = await db.execute(
        select(ShapExplanation).where(ShapExplanation.subscriber_id == subscriber_id)
    )
    shap_row = shap_result.scalar_one_or_none()
    runtime = load_runtime_config()

    profile = {
        "subscriber_id": sub.id,
        "age": sub.age,
        "gender": sub.gender,
        "sim_card_type": sub.sim_card_type,
        "sim_tenure_months": sub.sim_tenure_months,
        "mobile_data_generation": sub.mobile_data_generation,
        "monthly_spend_toman": sub.monthly_spend_toman,
        "churn_actual": sub.churn_actual,
    }
    score = SubscriberScore(
        churn_probability=recommendation.churn_probability if recommendation else None,
        churn_probability_raw=recommendation.churn_probability_raw if recommendation else None,
        risk_tier=recommendation.risk_tier if recommendation else None,
        calibration_method=runtime.calibration_method,
    )
    shap = SubscriberShapExplanation(
        positive_drivers=_drivers(shap_row.positive_drivers_json if shap_row else None),
        negative_drivers=_drivers(shap_row.negative_drivers_json if shap_row else None),
        narrative=shap_row.narrative if shap_row else None,
        shap_top_driver=(
            shap_row.shap_top_driver if shap_row else recommendation.shap_top_driver if recommendation else None
        ),
        shap_risk_up_drivers=(
            shap_row.shap_risk_up_drivers if shap_row else recommendation.shap_risk_up_drivers if recommendation else None
        ),
        shap_risk_down_drivers=(
            shap_row.shap_risk_down_drivers if shap_row else recommendation.shap_risk_down_drivers if recommendation else None
        ),
    )
    campaign = CampaignMetadata(
        campaign_priority=recommendation.campaign_priority if recommendation else None,
        campaign_cost_tier=recommendation.campaign_cost_tier if recommendation else None,
        crm_queue=recommendation.crm_queue if recommendation else None,
        primary_channel=recommendation.primary_channel if recommendation else None,
        secondary_channel=recommendation.secondary_channel if recommendation else None,
        campaign_channel_group=recommendation.campaign_channel_group if recommendation else None,
        digital_only_flag=recommendation.digital_only_flag if recommendation else None,
        escalation_required=recommendation.escalation_required if recommendation else None,
        human_touch_flag=recommendation.human_touch_flag if recommendation else None,
        campaign_urgency_days=recommendation.campaign_urgency_days if recommendation else None,
        contact_channel=recommendation.contact_channel if recommendation else None,
        offer_budget=recommendation.offer_budget if recommendation else None,
    )
    return SubscriberProfile(
        subscriber_id=sub.id,
        profile=profile,
        score=score,
        risk_band=score.risk_tier,
        recommendation=_recommendation_item(recommendation),
        ecosystem_profile=_ecosystem_profile(sub, recommendation),
        shap_explanations=shap,
        recommendation_rationale={
            "rule_id": recommendation.rule_id if recommendation else None,
            "rule_top_driver": recommendation.rule_top_driver if recommendation else None,
            "final_top_driver": recommendation.final_top_driver if recommendation else None,
            "final_top_driver_source": recommendation.final_top_driver_source if recommendation else None,
            "policy": "Actions are rule-driven; SHAP is narrative support only.",
        },
        campaign_metadata=campaign,
        governance_metadata=GovernanceMetadata(
            schema_version=runtime.schema_version,
            bundle_schema_version=runtime.bundle_schema_version,
            feature_contract_version=runtime.feature_schema_version,
            recommendation_schema_version=runtime.recommendation_schema_version,
            shap_schema_version=runtime.shap_schema_version,
            compatibility_status=runtime.compatibility_status,
            champion_family=runtime.champion_family,
        ),
    )
