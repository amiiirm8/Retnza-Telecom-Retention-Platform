"""
ChurnPrediction SQLAlchemy model — stores per-subscriber scoring history.

Pipeline position:
  Written by the batch scoring pipeline after MLService.score_dataframe produces
  raw and calibrated probabilities. Links predictions to a specific model version
  for audit and reproducibility.

Workflow stage:
  Inserted during batch scoring; queried by the subscriber detail endpoint and
  monitoring dashboards for historical score comparison.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChurnPrediction(Base):
    """
    One scored prediction for a subscriber at a point in time.

    Captures both raw and calibrated probabilities, the risk tier assignment,
    and the champion metadata (family, calibration method, schema versions) that
    produced the score. The model_version_id FK enables full audit traceability
    back to the exact model version used.

    Key fields:
        churn_probability_raw: Uncalibrated output from the base model; ranking only.
        churn_probability: Calibrated probability driving business decisions.
        risk_tier: Very High / High / Medium / Low derived from thresholds.
        scored_at: Timestamp (server default) for time-series analysis.
    """

    __tablename__ = "churn_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"), index=True)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"), index=True)
    churn_probability: Mapped[float] = mapped_column(Float)
    churn_probability_raw: Mapped[float] = mapped_column(Float)
    risk_tier: Mapped[str] = mapped_column(String(32), index=True)
    champion_family: Mapped[str | None] = mapped_column(String(64))
    calibration_method: Mapped[str | None] = mapped_column(String(32))
    model_schema_version: Mapped[str | None] = mapped_column(String(64))
    feature_contract_version: Mapped[str | None] = mapped_column(String(64))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    subscriber: Mapped["Subscriber"] = relationship(back_populates="predictions")
