from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runtime_config import load_runtime_config
from app.models.recommendation import Recommendation
from app.models.subscriber import Subscriber
from app.schemas.dashboard import ChartSeries, ChartsResponse, KPIResponse


async def get_kpis(session: AsyncSession) -> KPIResponse:
    total = await session.scalar(select(func.count()).select_from(Subscriber)) or 0
    churn_count = await session.scalar(
        select(func.count()).select_from(Subscriber).where(Subscriber.churn_actual.is_(True))
    ) or 0
    avg_pred = await session.scalar(select(func.avg(Recommendation.churn_probability))) or 0.0
    avg_raw = await session.scalar(select(func.avg(Recommendation.churn_probability_raw))) or 0.0
    p1 = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.campaign_priority == "P1")
    ) or 0
    p2 = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.campaign_priority == "P2")
    ) or 0
    p3 = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.campaign_priority == "P3")
    ) or 0
    high = await session.scalar(
        select(func.count())
        .select_from(Recommendation)
        .where(Recommendation.risk_tier.in_(["Very High", "High"]))
    ) or 0
    digital = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.digital_only_flag.is_(True))
    ) or 0
    escalation = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.escalation_required.is_(True))
    ) or 0
    human = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.human_touch_flag.is_(True))
    ) or 0
    fallback = await session.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.is_fallback_rule.is_(True))
    ) or 0
    runtime = load_runtime_config()
    rate = churn_count / total if total else 0.0
    return KPIResponse(
        total_subscribers=total,
        actual_churn_rate=round(rate, 4),
        avg_predicted_churn=round(float(avg_pred), 4),
        avg_raw_churn_score=round(float(avg_raw), 4),
        p1_action_count=p1,
        p2_action_count=p2,
        p3_action_count=p3,
        high_risk_count=high,
        digital_only_count=digital,
        escalation_required_count=escalation,
        human_touch_count=human,
        fallback_rule_count=fallback,
        compatibility_status=runtime.compatibility_status,
        executive_summary=(
            "Executive view uses calibrated risk for business reporting; raw scores remain for ranking."
        ),
    )


async def get_charts(session: AsyncSession) -> ChartsResponse:
    risk_rows = await session.execute(
        select(Recommendation.risk_tier, func.count())
        .group_by(Recommendation.risk_tier)
    )
    priority_rows = await session.execute(
        select(Recommendation.campaign_priority, func.count())
        .group_by(Recommendation.campaign_priority)
    )
    rule_rows = await session.execute(
        select(Recommendation.rule_id, func.count()).group_by(Recommendation.rule_id).limit(12)
    )
    sim_rows = await session.execute(
        select(Subscriber.sim_card_type, func.count())
        .where(Subscriber.churn_actual.is_(True))
        .group_by(Subscriber.sim_card_type)
    )
    ecosystem_rows = await session.execute(
        select(Recommendation.ecosystem_segment, func.count()).group_by(Recommendation.ecosystem_segment)
    )
    crm_rows = await session.execute(
        select(Recommendation.crm_queue, func.count()).group_by(Recommendation.crm_queue)
    )
    return ChartsResponse(
        risk_distribution=[ChartSeries(name=r[0], value=float(r[1])) for r in risk_rows],
        campaign_priority_distribution=[ChartSeries(name=r[0], value=float(r[1])) for r in priority_rows],
        rule_distribution=[ChartSeries(name=r[0], value=float(r[1])) for r in rule_rows],
        churn_by_sim_type=[ChartSeries(name=str(r[0] or "unknown"), value=float(r[1])) for r in sim_rows],
        ecosystem_segment_distribution=[
            ChartSeries(name=str(r[0] or "unknown"), value=float(r[1])) for r in ecosystem_rows
        ],
        crm_queue_distribution=[
            ChartSeries(name=str(r[0] or "unknown"), value=float(r[1])) for r in crm_rows
        ],
    )
