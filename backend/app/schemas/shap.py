"""
Schemas for SHAP explanation responses.

Pipeline position:
  Provides per-subscriber model explainability data. SHAP explanations enrich
  CRM displays with driver-level reasoning but never drive action selection.
  This is an explicit governance policy encoded in the schema default for
  ShapResponse.policy.

Workflow stage:
  GET /api/v1/shap/{subscriber_id} -> ShapResponse
  Embedded in SubscriberProfile for the unified subscriber detail view.
"""

from pydantic import BaseModel


class ShapDriver(BaseModel):
    """
    A single SHAP driver — one feature's contribution to a subscriber's churn risk.

    Fields:
        feature: Internal feature name (matches feature_columns contract).
        business_label: Human-readable feature name for CRM display.
        shap_value: Raw SHAP value (positive = pushes risk up, negative = down).
        effect: Categorical effect ('increases_risk' or 'decreases_risk').
        narrative: Natural-language sentence explaining the driver.
    """

    feature: str
    business_label: str
    shap_value: float
    effect: str
    narrative: str


class ShapResponse(BaseModel):
    """
    Complete SHAP explanation for one subscriber.

    Contains top positive and negative drivers ranked by absolute SHAP value,
    a natural-language narrative summary, and the single most impactful feature.

    The policy field is hardcoded to reinforce the governance invariant that
    SHAP is narrative-only and never selects actions. CRM teams see this string
    in every SHAP response.
    """

    subscriber_id: int
    positive_drivers: list[ShapDriver]
    negative_drivers: list[ShapDriver]
    narrative: str
    shap_top_driver: str | None = None
    shap_risk_up_drivers: str | None = None
    shap_risk_down_drivers: str | None = None
    policy: str = "SHAP explanations provide narrative support only and never select actions."
