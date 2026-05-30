"""
Ecosystem analytics endpoints — product adoption, segments, and high-risk lists.

Pipeline position:
  Analyzes the relationship between ecosystem product adoption (Rubika, EWANO,
  Hamrah Man, VoLTE) and churn risk. Observations are explicitly labeled as
  observed associations, not causal claims.

Workflow stage:
  GET /api/v1/ecosystem/summary — adoption rates and risk associations per product.
  GET /api/v1/ecosystem/segments — per-segment risk analysis and taxonomy.
  GET /api/v1/ecosystem/high-risk — high-risk subscribers by ecosystem segment.

Security:
  All endpoints require authentication via CurrentUser dependency.
"""

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import desc, func, select

from app.core.deps import CurrentUser, DbSession
from app.core.runtime_config import load_runtime_config
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationItem, RecommendationListResponse

router = APIRouter()


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


async def _usage(db: DbSession, column: Any, label: str, total: int) -> dict[str, Any]:
    """
    Compute adoption metrics for a single ecosystem product.

    Returns active/inactive counts, adoption rate, and mean calibrated risk for
    both groups. The observed_relationship string explicitly disclaims causation.

    Args:
        db: Database session.
        column: SQLAlchemy boolean column for the product flag.
        label: Human-readable product name.
        total: Total subscriber count for rate calculation.

    Returns:
        Dict with adoption statistics and an observed-relationship disclaimer.
    """
    active_n = await db.scalar(select(func.count()).select_from(Recommendation).where(column.is_(True))) or 0
    inactive_n = await db.scalar(select(func.count()).select_from(Recommendation).where(column.is_(False))) or 0
    active_risk = await db.scalar(select(func.avg(Recommendation.churn_probability)).where(column.is_(True)))
    inactive_risk = await db.scalar(select(func.avg(Recommendation.churn_probability)).where(column.is_(False)))
    return {
        "label": label,
        "active_n": active_n,
        "inactive_capable_n": inactive_n,
        "adoption_rate": round(active_n / total, 4) if total else 0.0,
        "mean_calibrated_risk_active": float(active_risk or 0.0),
        "mean_calibrated_risk_inactive_capable": float(inactive_risk or 0.0),
        "observed_relationship": (
            f"{label} adoption is associated with calibrated risk differences in this snapshot."
        ),
    }


@router.get("/summary")
async def ecosystem_summary(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    """
    Return ecosystem product adoption summary with churn risk associations.

    Computes adoption rates (Rubika, EWANO, Hamrah Man, VoLTE) and compares
    mean calibrated churn risk between adopters and non-adopters. All metrics
    are explicitly labeled as observed associations, not causal effects.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        Dict with book mean risk, per-product adoption stats, segment counts,
        and a disclaimer about non-causality.
    """
    runtime = load_runtime_config()
    total = await db.scalar(select(func.count()).select_from(Recommendation)) or 0
    manifest_analytics = runtime.ecosystem_analytics
    return {
        "disclaimer": (
            "Metrics describe observed relationships and associations in this snapshot; "
            "they are not causal product-effect claims."
        ),
        "book_mean_calibrated_risk": float(
            (await db.scalar(select(func.avg(Recommendation.churn_probability)))) or 0.0
        )
        or manifest_analytics.get("book_mean_calibrated_risk"),
        "rubika_adoption": await _usage(db, Recommendation.has_rubika, "Rubika", total),
        "ewano_adoption": await _usage(db, Recommendation.has_ewano, "EWANO", total),
        "hamrah_man_engagement": await _usage(db, Recommendation.has_hamrahman, "Hamrah Man", total),
        "volte_usage": await _usage(db, Recommendation.has_volte, "VoLTE", total),
        "ecosystem_segment_counts": runtime.ecosystem_segments,
        "manifest_analytics": manifest_analytics,
    }


@router.get("/segments")
async def ecosystem_segments(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    """
    Return per-segment risk analysis and the full segment taxonomy.

    Computes subscriber count and mean calibrated risk for each ecosystem segment
    present in the database, then fills in any taxonomy-defined segments not
    present with their manifest counts. Every segment is labeled with wording
    that reinforces the non-causal nature of the observation.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        Dict with segments list, taxonomy, and non-causality disclaimer.
    """
    runtime = load_runtime_config()
    rows = await db.execute(
        select(
            Recommendation.ecosystem_segment,
            func.count(),
            func.avg(Recommendation.churn_probability),
        ).group_by(Recommendation.ecosystem_segment)
    )
    segments = {
        str(seg or "unknown"): {
            "ecosystem_segment": str(seg or "unknown"),
            "n": int(count),
            "mean_calibrated_risk": float(avg or 0.0),
            "wording": "observed relationship",
        }
        for seg, count, avg in rows
    }
    for segment in runtime.ecosystem_taxonomy:
        segments.setdefault(
            segment,
            {
                "ecosystem_segment": segment,
                "n": runtime.ecosystem_segments.get(segment, 0),
                "mean_calibrated_risk": None,
                "wording": "associated with",
            },
        )
    return {
        "segments": list(segments.values()),
        "segment_taxonomy": runtime.ecosystem_taxonomy,
        "disclaimer": "Segment differences are associated with observed risk patterns, not causal effects.",
    }


@router.get("/high-risk", response_model=RecommendationListResponse)
async def ecosystem_high_risk(
    db: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    ecosystem_segment: str | None = None,
) -> RecommendationListResponse:
    """
    Return high-risk subscribers (Very High / High), optionally filtered by
    ecosystem segment.

    Sorted by churn_probability descending with campaign_queue_rank as secondary
    sort for CRM prioritization.

    Args:
        db: Database session.
        _user: Authenticated user.
        page: Page number (1-indexed, default 1).
        page_size: Items per page (default 50, max 500).
        ecosystem_segment: Optional ecosystem segment filter.

    Returns:
        Paginated list of high-risk RecommendationItem objects.
    """
    q = select(Recommendation).where(Recommendation.risk_tier.in_(["Very High", "High"]))
    count_q = select(func.count()).select_from(Recommendation).where(
        Recommendation.risk_tier.in_(["Very High", "High"])
    )
    if ecosystem_segment:
        q = q.where(Recommendation.ecosystem_segment == ecosystem_segment)
        count_q = count_q.where(Recommendation.ecosystem_segment == ecosystem_segment)
    total = await db.scalar(count_q) or 0
    q = (
        q.order_by(desc(Recommendation.churn_probability), Recommendation.campaign_queue_rank)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()
    return RecommendationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_item(row) for row in rows],
    )
