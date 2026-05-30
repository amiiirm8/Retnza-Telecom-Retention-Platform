"""Schema contract integrity tests — ensure API schemas are internally consistent."""

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.dashboard import KPIResponse, ChartsResponse
from app.schemas.recommendation import RecommendationItem, RecommendationListResponse, ActionQueueResponse


class TestDashboardSchema(unittest.TestCase):
    """KPI and chart response schemas must not regress in field count or type."""

    def test_kpi_response_fields(self):
        fields = KPIResponse.model_fields
        expected = {
            "total_subscribers", "actual_churn_rate", "avg_predicted_churn",
            "avg_raw_churn_score", "p1_action_count", "p2_action_count",
            "p3_action_count", "high_risk_count", "digital_only_count",
            "escalation_required_count", "human_touch_count",
            "fallback_rule_count", "compatibility_status", "executive_summary",
        }
        self.assertEqual(set(fields.keys()), expected)

    def test_charts_response_fields(self):
        fields = ChartsResponse.model_fields
        expected = {
            "risk_distribution", "campaign_priority_distribution",
            "rule_distribution", "churn_by_sim_type",
            "ecosystem_segment_distribution", "crm_queue_distribution",
        }
        self.assertEqual(set(fields.keys()), expected)

    def test_chart_series_type(self):
        from app.schemas.dashboard import ChartSeries
        cs = ChartSeries(name="test", value=42.0)
        self.assertEqual(cs.name, "test")
        self.assertEqual(cs.value, 42.0)


class TestRecommendationSchema(unittest.TestCase):
    """Recommendation item schema must include all critical routing fields."""

    REQUIRED_FIELDS = {
        "subscriber_id", "churn_probability", "churn_probability_raw",
        "risk_tier", "rule_id", "recommended_action", "campaign_priority",
        "campaign_cost_tier", "campaign_queue_rank", "crm_queue",
        "digital_only_flag", "escalation_required", "human_touch_flag",
        "primary_channel", "secondary_channel", "intervention_type",
        "ecosystem_segment", "final_top_driver", "final_top_driver_source",
        "rule_top_driver", "shap_top_driver",
    }

    def test_recommendation_item_fields(self):
        fields = RecommendationItem.model_fields
        for f in self.REQUIRED_FIELDS:
            self.assertIn(f, fields, f"Missing field: {f}")

    def test_recommendation_list_response(self):
        resp = RecommendationListResponse(total=0, page=1, page_size=50, items=[])
        self.assertEqual(resp.total, 0)
        self.assertEqual(resp.page, 1)

    def test_action_queue_response_inheritance(self):
        resp = ActionQueueResponse(
            total=0, page=1, page_size=50, items=[],
            queue_type="test", filters={},
        )
        self.assertEqual(resp.queue_type, "test")
        self.assertEqual(resp.filters, {})


if __name__ == "__main__":
    unittest.main()
