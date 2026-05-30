import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.core.deps import get_current_user
from app.services.ml_service import get_ml_service


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "retnza"})

    def test_predict_live_mocked(self):
        # Mock get_current_user dependency
        async def override_get_current_user():
            return {"email": "test@example.com", "role": "admin"}
        
        # Mock get_ml_service dependency
        mock_ml_service = MagicMock()
        mock_ml_service.score_feature_dict.return_value = {
            "churn_probability": 0.825,
            "churn_probability_raw": 0.79,
            "risk_tier": "Very High",
            "recommended_action": "Retention Desk Save Call",
            "top_driver": "Prepaid SIM + very short tenure",
            "rule_id": "R01_PREPAID_INFANT",
            "campaign_priority": "P1"
        }
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_ml_service] = lambda: mock_ml_service

        try:
            payload = {
                "features": {
                    "age": 35.0,
                    "sim_tenure_months": 3.0,
                    "cumulative_spend_toman": 10000.0,
                    "monthly_spend_toman": 5000.0
                }
            }
            response = self.client.post("/api/v1/predict", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["churn_probability"], 0.825)
            self.assertEqual(data["risk_tier"], "Very High")
            self.assertEqual(data["rule_id"], "R01_PREPAID_INFANT")
            
            mock_ml_service.score_feature_dict.assert_called_once_with(payload["features"])
        finally:
            app.dependency_overrides.clear()

    def test_login_invalid_credentials(self):
        payload = {
            "email": "wrong@example.com",
            "password": "wrongpassword"
        }
        response = self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid credentials")


if __name__ == "__main__":
    unittest.main()
