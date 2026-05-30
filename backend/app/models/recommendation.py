"""
Recommendation SQLAlchemy model — the richest per-subscriber analytics row.

Pipeline position:
  Loaded from the recommendation Parquet file by the batch pipeline. This is
  the primary table queried by the CRM dashboard for listing, filtering, and
  queue-based views of subscriber actions.

Workflow stage:
  Queried by recommendations, subscribers, ecosystem, and dashboard endpoints.
  Contains everything needed for CRM action execution: churn risk, rule/action
  metadata, channel strategy, ecosystem profile, and driver attribution.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Recommendation(Base):
    """
    Complete CRM-ready recommendation for one subscriber.

    This is the most column-rich model in the schema. It aggregates:
      - Churn risk: raw + calibrated scores, risk tier.
      - Action metadata: rule_id, recommended_action, fallback status.
      - Campaign execution: priority, cost tier, channels, urgency, queue rank.
      - Driver attribution: rule_top_driver, shap_top_driver, final_top_driver
        with source indicator (rule or SHAP).
      - Ecosystem profile: product adoption flags, engagement level, segment.
      - Schema governance: recommendation_schema_version, model_schema_version,
        feature_contract_version for audit.

    Key invariants:
      - campaign_queue_rank is indexed for fast queue ordering.
      - is_fallback_rule flag distinguishes rule-based from fallback actions.
      - The three-tier driver system (rule -> SHAP -> final) reflects the
        recommendation pipeline: rules pick the action, SHAP adds narrative,
        and final_top_driver is the resolved single source of truth.
    """

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"), index=True)
    churn_probability: Mapped[float] = mapped_column(Float, index=True)
    churn_probability_raw: Mapped[float] = mapped_column(Float)
    risk_tier: Mapped[str] = mapped_column(String(32), index=True)
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    rule_top_driver: Mapped[str | None] = mapped_column(String(256))
    shap_top_driver: Mapped[str | None] = mapped_column(String(256))
    final_top_driver: Mapped[str | None] = mapped_column(String(256))
    final_top_driver_source: Mapped[str | None] = mapped_column(String(32))
    top_driver: Mapped[str | None] = mapped_column(String(256))
    recommended_action: Mapped[str] = mapped_column(Text)
    rule_priority: Mapped[str | None] = mapped_column(String(8), index=True)
    campaign_priority: Mapped[str] = mapped_column(String(8), index=True)
    campaign_queue_rank: Mapped[float] = mapped_column(Float, index=True)
    primary_channel: Mapped[str | None] = mapped_column(String(32))
    secondary_channel: Mapped[str | None] = mapped_column(String(32))
    intervention_type: Mapped[str | None] = mapped_column(String(32))
    human_touch_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    digital_only_flag: Mapped[bool | None] = mapped_column(Boolean, index=True)
    escalation_required: Mapped[bool | None] = mapped_column(Boolean, index=True)
    action_assigned: Mapped[bool | None] = mapped_column(Boolean)
    is_fallback_rule: Mapped[bool | None] = mapped_column(Boolean, index=True)
    campaign_cost_tier: Mapped[str | None] = mapped_column(String(8))
    offer_budget_numeric_tier: Mapped[int | None] = mapped_column(Integer)
    offer_budget_cap_type: Mapped[str | None] = mapped_column(String(64))
    campaign_urgency_days: Mapped[float | None] = mapped_column(Float)
    crm_queue: Mapped[str | None] = mapped_column(String(64), index=True)
    campaign_channel_group: Mapped[str | None] = mapped_column(String(64), index=True)
    retention_cost_estimate: Mapped[str | None] = mapped_column(String(64))
    contact_channel: Mapped[str | None] = mapped_column(String(128))
    offer_budget: Mapped[str | None] = mapped_column(String(256))
    has_rubika: Mapped[bool | None] = mapped_column(Boolean, index=True)
    has_ewano: Mapped[bool | None] = mapped_column(Boolean, index=True)
    has_hamrahman: Mapped[bool | None] = mapped_column(Boolean)
    has_volte: Mapped[bool | None] = mapped_column(Boolean)
    ecosystem_product_count: Mapped[int | None] = mapped_column(Integer)
    ecosystem_engagement_level: Mapped[str | None] = mapped_column(String(32), index=True)
    ecosystem_segment: Mapped[str | None] = mapped_column(String(64), index=True)
    ecosystem_risk_gap: Mapped[bool | None] = mapped_column(Boolean)
    ecosystem_retention_strategy: Mapped[str | None] = mapped_column(String(128), index=True)
    shap_summary: Mapped[str | None] = mapped_column(Text)
    shap_risk_up_drivers: Mapped[str | None] = mapped_column(Text)
    shap_risk_down_drivers: Mapped[str | None] = mapped_column(Text)
    recommendation_schema_version: Mapped[str | None] = mapped_column(String(64))
    model_schema_version: Mapped[str | None] = mapped_column(String(64))
    feature_contract_version: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscriber: Mapped["Subscriber"] = relationship(back_populates="recommendations")
