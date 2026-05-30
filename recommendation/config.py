"""Runtime configuration — version-aware thresholds from champion / modeling.

Loads risk-tier thresholds from the champion model bundle or manifest,
with fallback to modeling.config defaults. Provides governance-safe
version compatibility checks between recommendation, champion, feature,
and SHAP schemas.

Pipeline stage: inference/reporting-time — called at engine startup.

Key invariants:
  - Thresholds come from champion artifacts (modeling output), not hardcoded here.
  - Schema version constants act as compatibility gates.
  - RuntimeConfig carries warnings for schema drift but does not block execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modeling.config import (
    CHAMPION_BUNDLE_SCHEMA,
    FEATURE_SCHEMA_EXPECTED,
    MODELING_SCHEMA_VERSION,
    RISK_TIER_THRESHOLDS as DEFAULT_RISK_TIER_THRESHOLDS,
)
from modeling.governance import validate_champion_bundle

RECOMMENDATION_SCHEMA_VERSION = "task8-recommendations-v4"
RECOMMENDATION_ENGINE_VERSION = "1.0.0"
COMPATIBLE_CHAMPION_SCHEMA = CHAMPION_BUNDLE_SCHEMA
COMPATIBLE_FEATURE_SCHEMA = FEATURE_SCHEMA_EXPECTED
COMPATIBLE_MODELING_SCHEMA = MODELING_SCHEMA_VERSION
COMPATIBLE_SHAP_SCHEMA = "task7-shap-v4"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "subscribers_cleaned.parquet"
CHAMPION_PATH = PROJECT_ROOT / "outputs" / "champion" / "champion_model.joblib"
CHAMPION_MANIFEST_PATH = PROJECT_ROOT / "outputs" / "champion" / "champion_manifest.json"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "recommendations"


@dataclass
class RuntimeConfig:
    """Governance-safe runtime settings for the recommendation layer.

    Encapsulates all configurable parameters that flow from champion artifacts
    into the recommendation engine. Instantiated once at pipeline start via
    from_champion_artifacts().

    Attributes:
        risk_tier_thresholds: Probability cutoffs for risk tiers
            (e.g. {"Very High": 0.6, "High": 0.3, "Medium": 0.15}).
        threshold_source: Human-readable provenance string for audit.
        threshold_warnings: Non-blocking schema-drift or version-mismatch
            messages collected during loading.
        operating_threshold: Optional override threshold from champion manifest.
        operating_policy: Optional recommended operating policy string.
        champion_schema: Schema version of the loaded champion bundle.
        modeling_schema: Schema version of the loaded modeling manifest.
    """

    risk_tier_thresholds: dict[str, float]
    threshold_source: str
    threshold_warnings: list[str] = field(default_factory=list)
    operating_threshold: float | None = None
    operating_policy: str | None = None
    champion_schema: str | None = None
    modeling_schema: str | None = None

    @classmethod
    def from_champion_artifacts(
        cls,
        bundle: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
        *,
        champion_path: Path = CHAMPION_PATH,
        manifest_path: Path = CHAMPION_MANIFEST_PATH,
    ) -> "RuntimeConfig":
        """Construct RuntimeConfig from champion model bundle or manifest.

        Resolution order (first wins):
          1. champion_model.joblib risk_band_thresholds
          2. champion_manifest.json risk_band_thresholds
          3. champion_manifest.json risk_tier_thresholds (legacy key)
          4. modeling.config.RISK_TIER_THRESHOLDS (hardcoded fallback)

        Args:
            bundle: Pre-loaded champion dict (avoids re-read).
            manifest: Pre-loaded manifest dict (avoids re-read).
            champion_path: Path to .joblib champion file.
            manifest_path: Path to champion_manifest.json.

        Returns:
            Fully populated RuntimeConfig instance.

        Side effects:
            Reads files from disk if bundle/manifest not provided.
            Validates champion bundle schema (non-blocking warnings).

        Failure modes:
            Missing files → uses defaults (silent fallback).
            Schema mismatch → warning appended, execution continues.
        """
        warnings: list[str] = []
        thresholds = dict(DEFAULT_RISK_TIER_THRESHOLDS)
        source = "modeling.config.RISK_TIER_THRESHOLDS (fallback)"

        # Try manifest first — it is faster to read than the full .joblib.
        if manifest_path.is_file():
            manifest = manifest or json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("risk_band_thresholds"):
                thresholds = dict(manifest["risk_band_thresholds"])
                source = f"champion_manifest.json ({manifest_path.name})"
            elif manifest.get("risk_tier_thresholds"):
                thresholds = dict(manifest["risk_tier_thresholds"])
                source = "champion_manifest.json (legacy key)"

        # Champion bundle thresholds take precedence over manifest.
        if bundle is None and champion_path.is_file():
            import joblib

            bundle = joblib.load(champion_path)

        if bundle:
            if bundle.get("risk_band_thresholds"):
                thresholds = dict(bundle["risk_band_thresholds"])
                source = "champion_model.joblib risk_band_thresholds"
            validate_champion_bundle(bundle, strict=False)
            if bundle.get("schema_version") != COMPATIBLE_CHAMPION_SCHEMA:
                warnings.append(
                    f"Champion bundle schema {bundle.get('schema_version')!r} "
                    f"!= expected {COMPATIBLE_CHAMPION_SCHEMA!r}"
                )

        op_thr = None
        op_pol = None
        if manifest:
            op_thr = manifest.get("operating_threshold")
            op_pol = manifest.get("recommended_operating_policy")

        return cls(
            risk_tier_thresholds=thresholds,
            threshold_source=source,
            threshold_warnings=warnings,
            operating_threshold=float(op_thr) if op_thr is not None else None,
            operating_policy=op_pol,
            champion_schema=bundle.get("schema_version") if bundle else None,
            modeling_schema=manifest.get("schema_version") if manifest else None,
        )


def load_runtime_config() -> RuntimeConfig:
    """Convenience loader: reads champion artifacts from default paths.

    Returns:
        RuntimeConfig assembled from champion_model.joblib and
        champion_manifest.json on disk.
    """
    return RuntimeConfig.from_champion_artifacts()
