"""
Unified subscriber profile schema for the single-subscriber detail view.

Pipeline position:
  Combines score, SHAP explanations, recommendation, ecosystem profile, campaign
  metadata, and governance metadata into one response. This is the richest
  response schema in the API, designed for CRM agents who need full context on
  a single subscriber.

Workflow stage:
  GET /api/v1/subscribers/{subscriber_id} -> SubscriberProfile
"""

from pydantic import BaseModel, Field

from app.schemas.recommendation import RecommendationItem
from app.schemas.shap import ShapDriver


class SubscriberScore(BaseModel):
    """
    Churn prediction scores for a subscriber.

    Maintains both raw and calibrated scores with explicit usage guidance strings
    so consumers understand which score to use for which purpose.

    Fields:
        churn_probability_raw: Uncalibrated model output; for ranking only.
        churn_probability: Calibrated risk; for business thresholds and CRM.
        risk_tier: Resolved risk tier (Very High / High / Medium / Low).
        calibration_method: Which calibrator was used (e.g., 'isotonic', 'platt').
        raw_score_use: Static reminder that raw scores are ranking-only.
        calibrated_score_use: Static reminder of calibrated score usage.
    """

    churn_probability_raw: float | None = None
    churn_probability: float | None = None
    risk_tier: str | None = None
    calibration_method: str | None = None
    raw_score_use: str = "ranking/top-k only"
    calibrated_score_use: str = "CRM thresholds, risk bands, and business reporting"


class SubscriberEcosystemProfile(BaseModel):
    """
    Ecosystem product adoption and engagement profile for a subscriber.

    Tracks which ecosystem products (Rubika, EWANO, Hamrah Man, VoLTE) the
    subscriber uses and computes engagement level, segment, and retention
    strategy from this data.
    """

    has_rubika: bool | None = None
    has_ewano: bool | None = None
    has_hamrahman: bool | None = None
    has_volte: bool | None = None
    ecosystem_product_count: int | None = None
    ecosystem_engagement_level: str | None = None
    ecosystem_segment: str | None = None
    ecosystem_risk_gap: bool | None = None
    ecosystem_retention_strategy: str | None = None


class SubscriberShapExplanation(BaseModel):
    """
    SHAP-based explanation for a subscriber's predicted churn risk.

    Contains the top positive/negative drivers with narrative descriptions.
    The policy field reinforces that SHAP is narrative-only — it provides
    context for CRM agents but does not drive action selection.
    """

    positive_drivers: list[ShapDriver] = Field(default_factory=list)
    negative_drivers: list[ShapDriver] = Field(default_factory=list)
    narrative: str | None = None
    shap_top_driver: str | None = None
    shap_risk_up_drivers: str | None = None
    shap_risk_down_drivers: str | None = None
    policy: str = "SHAP explanations provide narrative support only and never select actions."


class CampaignMetadata(BaseModel):
    """
    Campaign execution metadata for a subscriber's recommended action.

    Includes channel strategy (primary, secondary, channel group), execution
    flags (digital_only, escalation_required, human_touch), urgency, and
    budget/offer details. Used by CRM systems to execute the recommended action.
    """

    campaign_priority: str | None = None
    campaign_cost_tier: str | None = None
    crm_queue: str | None = None
    primary_channel: str | None = None
    secondary_channel: str | None = None
    campaign_channel_group: str | None = None
    digital_only_flag: bool | None = None
    escalation_required: bool | None = None
    human_touch_flag: bool | None = None
    campaign_urgency_days: float | None = None
    contact_channel: str | None = None
    offer_budget: str | None = None


class GovernanceMetadata(BaseModel):
    """
    Schema version and compatibility info for the current champion model.

    Enables CRM systems to verify which model version produced the predictions
    and whether the artifact stack is fully compatible. Critical for audit
    traceability and multi-version deployment scenarios.
    """

    schema_version: str | None = None
    bundle_schema_version: str | None = None
    feature_contract_version: str | None = None
    recommendation_schema_version: str | None = None
    shap_schema_version: str | None = None
    compatibility_status: str | None = None
    champion_family: str | None = None


class SubscriberProfile(BaseModel):
    """
    Complete subscriber profile aggregating all ML output and metadata.

    This is the richest response in the API, designed for CRM agents who need:
      - Demographic profile
      - Churn scores (raw + calibrated) with risk tier
      - Recommendation with full action metadata
      - Ecosystem product adoption profile
      - SHAP explanations with driver-level reasoning
      - Campaign metadata for execution
      - Governance metadata for audit

    The recommendation_rationale dict explains why the specific action was chosen
    (rule vs. SHAP-driven), reinforcing the governance policy.
    """

    subscriber_id: int
    profile: dict
    score: SubscriberScore
    risk_band: str | None = None
    recommendation: RecommendationItem | None = None
    ecosystem_profile: SubscriberEcosystemProfile
    shap_explanations: SubscriberShapExplanation
    recommendation_rationale: dict
    campaign_metadata: CampaignMetadata
    governance_metadata: GovernanceMetadata
