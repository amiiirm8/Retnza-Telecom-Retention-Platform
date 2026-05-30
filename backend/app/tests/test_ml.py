import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.ml_service import get_ml_service
from feature_engineering.builders import get_model_feature_columns
from recommendation.engine import assign_risk_tier, CAMPAIGN_PRIORITY_BY_TIER


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        self.ml_service = get_ml_service()
        self.feature_cols = get_model_feature_columns()

    def test_feature_columns(self):
        self.assertTrue(len(self.feature_cols) > 0)
        self.assertIn("age", self.feature_cols)
        self.assertIn("sim_tenure_months", self.feature_cols)
        self.assertIn("lifetime_arpu_toman", self.feature_cols)

    def test_risk_tier_assignment(self):
        self.assertEqual(assign_risk_tier(0.8), "Very High")
        self.assertEqual(assign_risk_tier(0.4), "High")
        self.assertEqual(assign_risk_tier(0.2), "Medium")
        self.assertEqual(assign_risk_tier(0.05), "Low")

    def test_campaign_priority_assignment(self):
        self.assertEqual(CAMPAIGN_PRIORITY_BY_TIER["Very High"], "P1")
        self.assertEqual(CAMPAIGN_PRIORITY_BY_TIER["High"], "P1")
        self.assertEqual(CAMPAIGN_PRIORITY_BY_TIER["Medium"], "P2")
        self.assertEqual(CAMPAIGN_PRIORITY_BY_TIER["Low"], "P4")

    def test_live_scoring_dict(self):
        features = {
            "age": 35.0,
            "gender": "male",
            "sim_card_type": "prepaid",
            "sim_tenure_months": 15.0,
            "mobile_data_generation": "4G",
            "monthly_spend_toman": 45000.0,
            "cumulative_spend_toman": 675000.0,
            "intl_roaming_package": "no",
            "operator_cloud_storage": "yes",
            "night_data_package": "no",
            "volte_service": "yes",
            "superapp_social": "no",
            "superapp_financial": "yes",
            "operator_app_usage": "yes",
            "subscriber_id": 999999
        }
        res = self.ml_service.score_feature_dict(features)
        
        self.assertIn("churn_probability", res)
        self.assertIn("churn_probability_raw", res)
        self.assertIn("risk_tier", res)
        self.assertIn("recommended_action", res)
        self.assertIn("top_driver", res)
        self.assertIn("rule_id", res)
        self.assertIn("campaign_priority", res)
        
        self.assertTrue(0.0 <= res["churn_probability"] <= 1.0)
        self.assertTrue(0.0 <= res["churn_probability_raw"] <= 1.0)
        self.assertIn(res["risk_tier"], ["Very High", "High", "Medium", "Low"])


if __name__ == "__main__":
    unittest.main()
