"""
Schemas for the recommendations listing and action-queue endpoints.

Pipeline position:
  Read-only views over the recommendation Parquet rows stored in the database.
  Used by the CRM dashboard to browse, filter, and prioritize intervention
  queues (high-risk, digital-only, escalation-required, human-touch, etc.).

Workflow stage:
  GET /api/v1/recommendations?risk_tier=...&campaign_priority=... -> RecommendationListResponse
  GET /api/v1/recommendations/action-queue/high-risk -> ActionQueueResponse
"""

from typing import Any

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    """
    Single recommendation row as stored in the recommendations database table.

    Represents a fully resolved CRM action for one subscriber, including:
      - Churn risk (raw + calibrated)
      - Action metadata (rule, action, priority, channels, cost tier)
      - Driver attribution (rule_top_driver, shap_top_driver, final_top_driver)
      - Ecosystem segmentation and retention strategy
      - Queue ordering (campaign_queue_rank for priority sorting)

    The raw vs calibrated distinction is preserved throughout to support both
    ranking use cases (raw) and business threshold decisions (calibrated).
    """

    subscriber_id: int
    churn_probability_raw: float
    churn_probability: float
    risk_tier: str
    rule_id: str
    recommended_action: str
    campaign_priority: str
    campaign_cost_tier: str | None = None
    campaign_queue_rank: float
    crm_queue: str | None = None
    digital_only_flag: bool | None = None
    escalation_required: bool | None = None
    human_touch_flag: bool
    primary_channel: str | None = None
    secondary_channel: str | None = None
    campaign_channel_group: str | None = None
    intervention_type: str | None = None
    ecosystem_segment: str | None = None
    ecosystem_retention_strategy: str | None = None
    rule_top_driver: str | None = None
    shap_top_driver: str | None = None
    final_top_driver: str | None = None
    final_top_driver_source: str | None = None
    top_driver: str | None = None


class RecommendationListResponse(BaseModel):
    """
    Paginated list of recommendation items.

    Used by the CRM dashboard for browsing and filtering the full recommendation
    set. Supports sortable columns (campaign_queue_rank, churn_probability, etc.)
    and multiple filter dimensions (risk_tier, campaign_priority, ecosystem_segment).
    """

    total: int
    page: int
    page_size: int
    items: list[RecommendationItem]


class ActionQueueResponse(RecommendationListResponse):
    """
    A named action queue with applied filter metadata.

    Extends RecommendationListResponse with a queue_type label (e.g., 'high-risk',
    'digital-only', 'campaign-P1') and the exact filter dict that was applied.
    This lets CRM dashboards display curated work queues with clear labeling.
    """

    queue_type: str
    filters: dict[str, Any]
