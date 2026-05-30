"""
ModelVersion SQLAlchemy model — registry of all deployed model versions.

Pipeline position:
  Inserted during model deployment/staging. Each row represents one trained
  model bundle that has passed governance validation. The is_active flag
  identifies which version is currently champion.

Workflow stage:
  Queried by the model monitoring endpoint (/health) to report which version
  is serving predictions, along with its holdout metrics and schema versions.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelVersion(Base):
    """
    Registry entry for a single deployed model version.

    Tracks the complete version lineage: family, calibration method, all schema
    versions (model bundle, feature contract, recommendation, SHAP), holdout
    test metrics (PR-AUC, Brier, ECE), and the artifact path on disk.

    Key invariants:
      - version_tag is unique across all versions.
      - Only one version should have is_active=True at a time (the champion).
      - compatibility_status records the artifact validation result at deploy time.
      - metrics_json stores unstructured additional metrics that don't fit the
        dedicated columns (e.g., precision@k, recall@k, lift charts).
    """

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_tag: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(64))
    calibration_method: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[str | None] = mapped_column(String(64), index=True)
    bundle_schema_version: Mapped[str | None] = mapped_column(String(64), index=True)
    feature_contract_version: Mapped[str | None] = mapped_column(String(64), index=True)
    recommendation_schema_version: Mapped[str | None] = mapped_column(String(64))
    shap_schema_version: Mapped[str | None] = mapped_column(String(64))
    compatibility_status: Mapped[str | None] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    test_pr_auc: Mapped[float | None] = mapped_column(Float)
    test_brier: Mapped[float | None] = mapped_column(Float)
    test_ece: Mapped[float | None] = mapped_column(Float)
    operating_threshold: Mapped[float | None] = mapped_column(Float)
    metrics_json: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(String(512))
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
