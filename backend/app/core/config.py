"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Retnza"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://retnza:retnza@localhost:5432/retnza"
    DATABASE_URL_SYNC: str = "postgresql://retnza:retnza@localhost:5432/retnza"

    JWT_SECRET_KEY: str = "change-me-in-production-use-openssl-rand"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300

    ML_ARTIFACTS_DIR: Path = REPO_ROOT / "outputs" / "champion"
    CHAMPION_MODEL_PATH: Path = REPO_ROOT / "outputs" / "champion" / "champion_model.joblib"
    CLEANED_DATA_PATH: Path = REPO_ROOT / "data" / "cleaned" / "subscribers_cleaned.parquet"
    RECOMMENDATIONS_PATH: Path = REPO_ROOT / "outputs" / "recommendations" / "subscriber_recommendations.parquet"
    RECOMMENDATION_MANIFEST_PATH: Path = REPO_ROOT / "outputs" / "recommendations" / "recommendation_manifest.json"
    SHAP_PATH: Path = REPO_ROOT / "outputs" / "explainability" / "subscriber_shap_values.parquet"
    EXPLAINABILITY_MANIFEST_PATH: Path = REPO_ROOT / "outputs" / "explainability" / "explainability_manifest.json"
    CHAMPION_MANIFEST_PATH: Path = REPO_ROOT / "outputs" / "champion" / "champion_manifest.json"
    MODEL_STABILITY_SUMMARY_PATH: Path = REPO_ROOT / "outputs" / "champion" / "model_stability_summary.json"
    CALIBRATION_SUMMARY_PATH: Path = REPO_ROOT / "outputs" / "champion" / "calibration_summary.json"
    DRIFT_REFERENCE_SNAPSHOT_PATH: Path = REPO_ROOT / "outputs" / "champion" / "drift_reference_snapshot.json"
    MODEL_COMPATIBILITY_PATH: Path = REPO_ROOT / "outputs" / "governance" / "model_compatibility.json"
    DRIFT_REFERENCE_SUMMARY_PATH: Path = REPO_ROOT / "outputs" / "governance" / "drift_reference_summary.json"

    RATE_LIMIT: str = "120/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
