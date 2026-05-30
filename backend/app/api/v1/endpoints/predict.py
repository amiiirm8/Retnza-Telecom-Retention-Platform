"""
Live prediction and batch-scoring endpoints.

Pipeline position:
  The primary real-time scoring interface. Accepts single subscriber features
  (predict_live) or bulk uploads (batch_score) and returns CRM-ready predictions.

Workflow stage:
  POST /api/v1/predict — real-time single-subscriber scoring.
  POST /api/v1/batch-score — ad-hoc batch scoring for QA and validation.

Security:
  Both endpoints require authentication via CurrentUser dependency.
"""

import io

import pandas as pd
from fastapi import APIRouter, File, UploadFile

from app.core.deps import CurrentUser, ML
from app.schemas.predict import BatchScoreResponse, PredictRequest, PredictResponse

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
async def predict_live(body: PredictRequest, ml: ML, _user: CurrentUser) -> PredictResponse:
    """
    Score a single subscriber in real time.

    Accepts subscriber features (either pre-built feature vectors or raw cleaned
    fields) and returns the calibrated churn probability, risk tier, and CRM-ready
    recommendation metadata.

    Args:
        body: PredictRequest containing subscriber features.
        ml: Cached MLService instance (injected dependency).
        _user: Authenticated user (enforced by auth dependency).

    Returns:
        PredictResponse with churn probabilities, risk tier, recommendation action,
        driver attribution, and campaign metadata.
    """
    result = ml.score_feature_dict(body.features)
    return PredictResponse(**{k: result.get(k) for k in PredictResponse.model_fields})


@router.post("/batch-score", response_model=BatchScoreResponse)
async def batch_score(
    ml: ML,
    _user: CurrentUser,
    file: UploadFile = File(...),
) -> BatchScoreResponse:
    """
    Score a batch of subscribers from an uploaded Parquet or CSV file.

    Designed for ad-hoc validation and QA. Returns the count of rows scored plus
    a 20-row preview. Full production scoring runs through the batch pipeline.

    Args:
        ml: Cached MLService instance (injected dependency).
        _user: Authenticated user (enforced by auth dependency).
        file: Uploaded file in Parquet or CSV format.

    Returns:
        BatchScoreResponse with rows_scored count and preview of first 20 rows.
    """
    content = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".parquet"):
        df = pd.read_parquet(io.BytesIO(content))
    elif name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_csv(io.BytesIO(content))
    scored = ml.score_dataframe(df)
    preview = scored.head(20).to_dict(orient="records")
    return BatchScoreResponse(rows_scored=len(scored), preview=preview)
