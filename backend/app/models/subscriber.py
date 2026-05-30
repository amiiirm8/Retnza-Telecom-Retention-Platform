from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(16))
    sim_card_type: Mapped[str | None] = mapped_column(String(16))
    sim_tenure_months: Mapped[float | None] = mapped_column(Float)
    mobile_data_generation: Mapped[str | None] = mapped_column(String(8))
    monthly_spend_toman: Mapped[float | None] = mapped_column(Float)
    cumulative_spend_toman: Mapped[float | None] = mapped_column(Float)
    churn_actual: Mapped[bool | None] = mapped_column(Boolean)
    is_prepaid: Mapped[bool | None] = mapped_column(Boolean)
    is_data_capable: Mapped[bool | None] = mapped_column(Boolean)
    has_rubika: Mapped[bool | None] = mapped_column(Boolean)
    has_ewano: Mapped[bool | None] = mapped_column(Boolean)
    has_hamrahman: Mapped[bool | None] = mapped_column(Boolean)
    has_volte: Mapped[bool | None] = mapped_column(Boolean)
    ecosystem_product_count: Mapped[int | None] = mapped_column(Integer)
    ecosystem_engagement_level: Mapped[str | None] = mapped_column(String(32), index=True)
    ecosystem_segment: Mapped[str | None] = mapped_column(String(64), index=True)
    ecosystem_risk_gap: Mapped[bool | None] = mapped_column(Boolean)
    ecosystem_retention_strategy: Mapped[str | None] = mapped_column(String(128), index=True)
    attributes_json: Mapped[str | None] = mapped_column(String)  # extended attrs snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    predictions: Mapped[list["ChurnPrediction"]] = relationship(back_populates="subscriber")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="subscriber")
    shap_explanations: Mapped[list["ShapExplanation"]] = relationship(back_populates="subscriber")
