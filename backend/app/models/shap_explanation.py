"""
ShapExplanation SQLAlchemy model — per-subscriber SHAP explanation storage.

Pipeline position:
  Loaded from the SHAP Parquet file by the batch pipeline and persisted for
  online retrieval. Each subscriber has at most one explanation row (unique
  FK constraint on subscriber_id).

Workflow stage:
  Queried by the SHAP endpoint (GET /api/v1/shap/{id}) and the subscriber
  profile endpoint. SHAP data is narrative-only and never drives action selection.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ShapExplanation(Base):
    """
    Stored SHAP explanation for one subscriber.

    Positive and negative drivers are stored as JSON blobs (Text columns)
    to allow flexible driver schemas without migrations. The narrative,
    top_feature, and shap_risk_up/down_drivers provide condensed explainability
    for CRM display.

    Key invariants:
      - subscriber_id is unique (one explanation per subscriber).
      - shap_schema_version and feature_contract_version enable audit traceability.
      - SHAP data is narrative-only per governance policy — no action selection logic
        reads from this table.
    """

    __tablename__ = "shap_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"), index=True, unique=True)
    positive_drivers_json: Mapped[str] = mapped_column(Text)
    negative_drivers_json: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str | None] = mapped_column(Text)
    top_feature: Mapped[str | None] = mapped_column(String(128))
    top_business_label: Mapped[str | None] = mapped_column(String(256))
    shap_top_driver: Mapped[str | None] = mapped_column(String(256))
    shap_risk_up_drivers: Mapped[str | None] = mapped_column(Text)
    shap_risk_down_drivers: Mapped[str | None] = mapped_column(Text)
    shap_schema_version: Mapped[str | None] = mapped_column(String(64))
    feature_contract_version: Mapped[str | None] = mapped_column(String(64))
    top_shap_value: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscriber: Mapped["Subscriber"] = relationship(back_populates="shap_explanations")
