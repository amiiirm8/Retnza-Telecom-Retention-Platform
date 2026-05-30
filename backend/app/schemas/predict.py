"""
Request/response schemas for the live prediction and batch-scoring endpoints.

Pipeline position:
  The predict endpoint is the primary real-time scoring API. Accepts subscriber
  features (raw cleaned fields or pre-built feature vectors), returns CRM-ready
  recommendation metadata including the calibrated churn probability, risk tier,
  and driver attribution.

Workflow stage:
  POST /api/v1/predict  -> PredictRequest -> MLService.score_feature_dict -> PredictResponse
  POST /api/v1/batch-score -> UploadFile -> MLService.score_dataframe -> BatchScoreResponse
"""

from typing import Any

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """
    Single-subscriber prediction request payload.

    Accepts either:
      - Active feature-contract keys (pre-built feature vector, skip pipeline).
      - Cleaned subscriber fields (age, gender, usage, VAS flags, etc.) that go
        through the shared feature-engineering package.

    The flexibility allows both CRM systems (which may send raw fields) and
    batch pipelines (which may send pre-computed features) to use the same endpoint.
    """

    features: dict[str, Any] = Field(
        ...,
        description="Either active feature-contract values or cleaned subscriber fields.",
    )


class PredictResponse(BaseModel):
    """
    Single-subscriber prediction response with CRM-ready recommendation metadata.

    Contains both raw and calibrated churn probabilities by design:
      - churn_probability_raw: Uncalibrated model output; used for ranking and
        cross-version PR-AUC monitoring. Consistent ordering across calibrator swaps.
      - churn_probability: Calibrated risk; used for business thresholds, tier
        assignment, and CRM decisions.

    The top_driver field is resolved via fallback: final_top_driver > rule_top_driver.
    """

    churn_probability: float
    churn_probability_raw: float
    risk_tier: str
    recommended_action: str
    top_driver: str
    rule_id: str
    campaign_priority: str
    campaign_cost_tier: str | None = None
    crm_queue: str | None = None
    digital_only_flag: bool | None = None
    escalation_required: bool | None = None
    ecosystem_segment: str | None = None
    ecosystem_retention_strategy: str | None = None
    rule_top_driver: str | None = None
    shap_top_driver: str | None = None
    final_top_driver: str | None = None
    final_top_driver_source: str | None = None


class BatchScoreResponse(BaseModel):
    """
    Batch scoring response summarizing processed rows.

    Returns a count of scored rows plus a preview (first 20 rows) for quick
    inspection. Full results are written to Parquet/CSV by the batch pipeline;
    this endpoint is designed for ad-hoc validation and QA, not bulk export.
    """

    rows_scored: int
    preview: list[dict]
