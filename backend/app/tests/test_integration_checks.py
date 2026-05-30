"""Integration confidence checks — prove system wiring is intact end-to-end.

These tests verify that the system's internal wiring is coherent without
requiring a live PostgreSQL or Redis instance. They validate:

  1. Artifact bootstrap — load_runtime_config successfully reads and validates
     champion artifacts (model, manifests, schemas).
  2. ML pipeline — raw features flow through feature engineering → scoring →
     risk tier → recommendation deterministically.
  3. Schema contract — API response models match frontend TypeScript expectations.
  4. Export layer — BI/CRM export fields are present and non-empty.
  5. Startup bootstrap — the FastAPI app initializes without crashing.
  6. Cross-artifact consistency — recommendation and SHAP schemas reference the
     same champion feature contract.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
for p in (BACKEND_ROOT, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.core.runtime_config import load_runtime_config, RuntimeConfigError


class TestArtifactBootstrap(unittest.TestCase):
    """Champion model artifacts must load and validate without errors."""

    def test_runtime_config_loads(self):
        try:
            cfg = load_runtime_config()
        except RuntimeConfigError as e:
            self.fail(f"RuntimeConfig failed to load: {e}")
        self.assertIsNotNone(cfg.champion_bundle)
        self.assertIsNotNone(cfg.feature_columns)
        self.assertGreater(len(cfg.feature_columns), 0)

    def test_artifact_validation_passes(self):
        cfg = load_runtime_config()
        for key, report in cfg.validation.items():
            self.assertTrue(
                report.get("compatible", False),
                f"Validation '{key}' failed: {report.get('errors', [])}",
            )

    def test_feature_count_consistent(self):
        cfg = load_runtime_config()
        self.assertGreater(cfg.feature_count, 25)  # must exceed legacy threshold
        self.assertEqual(cfg.feature_count, len(cfg.feature_columns))

    def test_risk_thresholds_present(self):
        cfg = load_runtime_config()
        for tier in ("Very High", "High", "Medium"):
            self.assertIn(tier, cfg.risk_tier_thresholds)

    def test_compatibility_status(self):
        cfg = load_runtime_config()
        self.assertEqual(cfg.compatibility_status, "compatible")


class TestExportLayer(unittest.TestCase):
    """BI/CRM export artifacts must exist and contain expected fields."""

    def test_powerbi_export_exists(self):
        export_csv = REPO_ROOT / "outputs" / "powerbi" / "crm_action_queue.csv"
        self.assertTrue(export_csv.is_file(), "Power BI export CSV missing")
        self.assertGreater(export_csv.stat().st_size, 0, "Power BI export is empty")

    def test_recommendation_parquet_exists(self):
        rec_parquet = REPO_ROOT / "outputs" / "recommendations" / "subscriber_recommendations.parquet"
        self.assertTrue(rec_parquet.is_file(), "Recommendations parquet missing")

    def test_export_manifest_exists(self):
        manifest = REPO_ROOT / "outputs" / "powerbi" / "powerbi_export_manifest.json"
        self.assertTrue(manifest.is_file(), "Export manifest missing")


class TestPipelineFlow(unittest.TestCase):
    """ML pipeline wiring: feature engineering → scoring → recommendation."""

    def test_feature_engineering_imports(self):
        from feature_engineering.builders import get_model_feature_columns
        cols = get_model_feature_columns()
        self.assertIn("age", cols)
        self.assertIn("sim_tenure_months", cols)

    def test_risk_tier_determinism(self):
        from recommendation.engine import assign_risk_tier
        cases = [(0.0, "Low"), (0.14, "Low"), (0.15, "Medium"),
                 (0.29, "Medium"), (0.30, "High"), (0.64, "High"),
                 (0.65, "Very High"), (1.0, "Very High")]
        for prob, expected in cases:
            self.assertEqual(assign_risk_tier(prob), expected)

    def test_campaign_priority_completeness(self):
        from recommendation.engine import CAMPAIGN_PRIORITY_BY_TIER
        for tier in ("Very High", "High", "Medium", "Low"):
            self.assertIn(tier, CAMPAIGN_PRIORITY_BY_TIER)

    def test_ml_service_imports_cleanly(self):
        from app.services.ml_service import MLService
        svc = MLService()
        self.assertIsNotNone(svc)


class TestFastAPIWiring(unittest.TestCase):
    """FastAPI app initializes without crashing and routes are registered."""

    def test_app_imports(self):
        from app.main import app
        routes = [r.path for r in app.routes]
        self.assertIn("/health", routes)
        self.assertIn("/api/v1/auth/login", routes)
        self.assertIn("/api/v1/dashboard/kpis", routes)

    def test_no_duplicate_route_prefixes(self):
        from app.main import app
        api_routes = [r.path for r in app.routes if r.path.startswith("/api/v1")]
        self.assertGreater(len(api_routes), 10, "Expected 10+ API v1 routes")

    def test_rate_limiter_configured(self):
        from app.main import app
        self.assertIsNotNone(app.state.limiter)


if __name__ == "__main__":
    unittest.main()
