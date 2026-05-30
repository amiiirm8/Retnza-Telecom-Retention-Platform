"""
Recommendation listing and action-queue endpoints.

Pipeline position:
  Read-only views over the recommendations database table. CRM teams use these
  endpoints to browse, filter, and prioritize subscriber interventions.

Workflow stage:
  GET /api/v1/recommendations — paginated list with multi-dimensional filtering.
  GET /api/v1/recommendations/action-queue/* — curated named queues for CRM workflows.

Security:
  All endpoints require authentication via CurrentUser dependency.
  Pagination is capped at 500 rows per page.
"""

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import asc, desc, func, select

from app.core.deps import CurrentUser, DbSession
from app.models.recommendation import Recommendation
from app.schemas.recommendation import ActionQueueResponse, RecommendationItem, RecommendationListResponse

router = APIRouter()

# Allowed sort columns, mapping query param -> SQLAlchemy column.
# campaign_queue_rank is the default sort (ascending) for queue prioritization.
SORT_COLUMNS = {
    "campaign_queue_rank": Recommendation.campaign_queue_rank,
    "churn_probability": Recommendation.churn_probability,
    "churn_probability_raw": Recommendation.churn_probability_raw,
    "campaign_priority": Recommendation.campaign_priority,
    "risk_tier": Recommendation.risk_tier,
    "ecosystem_segment": Recommendation.ecosystem_segment,
}


def _item(row: Recommendation) -> RecommendationItem:
    """Map a Recommendation ORM row to a RecommendationItem schema."""
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


def _apply_filters(q: Any, count_q: Any, filters: dict[str, Any]) -> tuple[Any, Any]:
    """
    Dynamically apply filter clauses to both the data query and count query.

    Supports filtering by risk_tier (single or list), campaign_priority, rule_id,
    ecosystem_segment, crm_queue, channel (primary/secondary/group), campaign_type,
    digital_only, escalation_required, human_touch, and subscriber_id search.

    Both queries receive the same filter clauses to ensure the total count matches
    the filtered result set.
    """
    clauses = []
    if filters.get("risk_tier"):
        clauses.append(Recommendation.risk_tier == filters["risk_tier"])
    if filters.get("risk_tiers"):
        clauses.append(Recommendation.risk_tier.in_(filters["risk_tiers"]))
    if filters.get("campaign_priority"):
        clauses.append(Recommendation.campaign_priority == filters["campaign_priority"])
    if filters.get("rule_id"):
        clauses.append(Recommendation.rule_id == filters["rule_id"])
    if filters.get("ecosystem_segment"):
        clauses.append(Recommendation.ecosystem_segment == filters["ecosystem_segment"])
    if filters.get("crm_queue"):
        clauses.append(Recommendation.crm_queue == filters["crm_queue"])
    if filters.get("channel"):
        channel = filters["channel"]
        # Match across any of the three channel-related columns for flexible filtering.
        clauses.append(
            (Recommendation.primary_channel == channel)
            | (Recommendation.secondary_channel == channel)
            | (Recommendation.campaign_channel_group == channel)
        )
    if filters.get("campaign_type"):
        clauses.append(Recommendation.intervention_type == filters["campaign_type"])
    if filters.get("digital_only") is not None:
        clauses.append(Recommendation.digital_only_flag.is_(filters["digital_only"]))
    if filters.get("escalation_required") is not None:
        clauses.append(Recommendation.escalation_required.is_(filters["escalation_required"]))
    if filters.get("human_touch") is not None:
        clauses.append(Recommendation.human_touch_flag.is_(filters["human_touch"]))
    if filters.get("search") is not None:
        clauses.append(Recommendation.subscriber_id == filters["search"])
    for clause in clauses:
        q = q.where(clause)
        count_q = count_q.where(clause)
    return q, count_q


async def _list(
    db: DbSession,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_dir: str,
    filters: dict[str, Any],
) -> RecommendationListResponse:
    """
    Shared paginated listing logic used by all recommendation and queue endpoints.

    Applies filters, counts total matching rows, applies sort + pagination, and
    returns a RecommendationListResponse.

    Default sort is campaign_queue_rank ascending (CRM agents process lowest
    queue rank first). Secondary sort is churn_probability descending.
    """
    q = select(Recommendation)
    count_q = select(func.count()).select_from(Recommendation)
    q, count_q = _apply_filters(q, count_q, filters)
    total = await db.scalar(count_q) or 0
    sort_col = SORT_COLUMNS.get(sort_by, Recommendation.campaign_queue_rank)
    order = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
    q = q.order_by(order, desc(Recommendation.churn_probability)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return RecommendationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_item(row) for row in rows],
    )


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    risk_tier: str | None = None,
    campaign_priority: str | None = None,
    rule_id: str | None = None,
    ecosystem_segment: str | None = None,
    crm_queue: str | None = None,
    channel: str | None = None,
    campaign_type: str | None = None,
    digital_only: bool | None = None,
    escalation_required: bool | None = None,
    human_touch: bool | None = None,
    search: int | None = None,
    sort_by: str = Query("campaign_queue_rank"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> RecommendationListResponse:
    """
    List recommendations with pagination, filtering, and sorting.

    Supports multiple filter dimensions simultaneously. Results are sorted by
    campaign_queue_rank ascending by default (prioritized action order).

    Args:
        db: Database session.
        _user: Authenticated user.
        page: Page number (1-indexed, default 1).
        page_size: Items per page (default 50, max 500).
        risk_tier: Filter by single risk tier.
        campaign_priority: Filter by campaign priority (P1, P2, P3).
        rule_id: Filter by recommendation rule.
        ecosystem_segment: Filter by ecosystem segment.
        crm_queue: Filter by CRM queue name.
        channel: Filter by any channel (primary, secondary, or group).
        campaign_type: Filter by intervention type.
        digital_only: Filter by digital-only flag.
        escalation_required: Filter by escalation requirement.
        human_touch: Filter by human touch flag.
        search: Exact subscriber ID search.
        sort_by: Column to sort by (default campaign_queue_rank).
        sort_dir: Sort direction (asc or desc, default asc).

    Returns:
        Paginated list of RecommendationItem objects.
    """
    return await _list(
        db,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filters={
            "risk_tier": risk_tier,
            "risk_tiers": None,
            "campaign_priority": campaign_priority,
            "rule_id": rule_id,
            "ecosystem_segment": ecosystem_segment,
            "crm_queue": crm_queue,
            "channel": channel,
            "campaign_type": campaign_type,
            "digital_only": digital_only,
            "escalation_required": escalation_required,
            "human_touch": human_touch,
            "search": search,
        },
    )


async def _queue_response(
    db: DbSession,
    *,
    queue_type: str,
    page: int,
    page_size: int,
    filters: dict[str, Any],
) -> ActionQueueResponse:
    """
    Build a named ActionQueueResponse using shared _list logic.

    Delegates to _list with a fixed sort (campaign_queue_rank asc) and wraps
    the result with queue_type and active filters metadata.
    """
    result = await _list(
        db,
        page=page,
        page_size=page_size,
        sort_by="campaign_queue_rank",
        sort_dir="asc",
        filters=filters,
    )
    return ActionQueueResponse(
        queue_type=queue_type,
        filters={k: v for k, v in filters.items() if v is not None},
        **result.model_dump(),
    )


@router.get("/action-queue", response_model=ActionQueueResponse)
async def action_queue(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    risk_tier: str | None = None,
    rule_id: str | None = None,
    ecosystem_segment: str | None = None,
    channel: str | None = None,
    campaign_type: str | None = None,
) -> ActionQueueResponse:
    """
    Custom action queue with user-specified filters.

    Args:
        risk_tier: Filter by risk tier.
        rule_id: Filter by recommendation rule.
        ecosystem_segment: Filter by ecosystem segment.
        channel: Filter by channel.
        campaign_type: Filter by intervention type.

    Returns:
        Filtered ActionQueueResponse with queue_type='custom'.
    """
    return await _queue_response(
        db,
        queue_type="custom",
        page=page,
        page_size=page_size,
        filters={
            "risk_tier": risk_tier,
            "rule_id": rule_id,
            "ecosystem_segment": ecosystem_segment,
            "channel": channel,
            "campaign_type": campaign_type,
        },
    )


@router.get("/action-queue/high-risk", response_model=ActionQueueResponse)
async def high_risk_queue(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> ActionQueueResponse:
    """
    Pre-built queue for Very High and High risk subscribers.

    CRM agents use this as their primary work queue for urgent interventions.
    """
    return await _queue_response(
        db,
        queue_type="high-risk",
        page=page,
        page_size=page_size,
        filters={"risk_tiers": ["Very High", "High"]},
    )


@router.get("/action-queue/campaign/{priority}", response_model=ActionQueueResponse)
async def priority_queue(
    priority: str,
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> ActionQueueResponse:
    """
    Pre-built queue for a specific campaign priority (P1, P2, P3).

    Args:
        priority: Campaign priority label (case-insensitive, uppercased internally).
    """
    return await _queue_response(
        db,
        queue_type=f"campaign-{priority.upper()}",
        page=page,
        page_size=page_size,
        filters={"campaign_priority": priority.upper()},
    )


@router.get("/action-queue/digital-only", response_model=ActionQueueResponse)
async def digital_only_queue(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> ActionQueueResponse:
    """
    Pre-built queue for subscribers flagged as digital-only.

    These subscribers can be reached through digital channels (SMS, push, in-app)
    and do not require human interaction.
    """
    return await _queue_response(
        db,
        queue_type="digital-only",
        page=page,
        page_size=page_size,
        filters={"digital_only": True},
    )


@router.get("/action-queue/escalation-required", response_model=ActionQueueResponse)
async def escalation_queue(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> ActionQueueResponse:
    """
    Pre-built queue for subscribers requiring escalation.

    These subscribers have triggered conditions that need supervisor or
    specialized team review before action execution.
    """
    return await _queue_response(
        db,
        queue_type="escalation-required",
        page=page,
        page_size=page_size,
        filters={"escalation_required": True},
    )


@router.get("/action-queue/human-touch", response_model=ActionQueueResponse)
async def human_touch_queue(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> ActionQueueResponse:
    """
    Pre-built queue for subscribers needing human-touch intervention.

    These subscribers require phone calls or in-person contact rather than
    fully automated digital communication.
    """
    return await _queue_response(
        db,
        queue_type="human-touch",
        page=page,
        page_size=page_size,
        filters={"human_touch": True},
    )
