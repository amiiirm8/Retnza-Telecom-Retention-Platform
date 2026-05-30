"""Tests for recommendation rule determinism, risk tier boundaries, and governance compatibility."""

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from recommendation.engine import assign_risk_tier
from recommendation.rules import RULE_PRECEDENCE_ORDER
from recommendation.config import load_runtime_config


class TestRiskTierBoundaries(unittest.TestCase):
    """Risk tier assignment must be deterministic and cover all valid probability ranges."""

    def test_critical_boundary(self):
        self.assertEqual(assign_risk_tier(0.65), "Very High")
        self.assertEqual(assign_risk_tier(0.99), "Very High")

    def test_high_boundary(self):
        self.assertEqual(assign_risk_tier(0.30), "High")
        self.assertEqual(assign_risk_tier(0.64), "High")

    def test_medium_boundary(self):
        self.assertEqual(assign_risk_tier(0.15), "Medium")
        self.assertEqual(assign_risk_tier(0.29), "Medium")

    def test_low_boundary(self):
        self.assertEqual(assign_risk_tier(0.0), "Low")
        self.assertEqual(assign_risk_tier(0.14), "Low")

    def test_edge_cases(self):
        self.assertEqual(assign_risk_tier(0.0), "Low")
        self.assertEqual(assign_risk_tier(1.0), "Very High")

    def test_no_valid_risk_tiers_missed(self):
        all_tiers = {"Very High", "High", "Medium", "Low"}
        for pct in [x / 100.0 for x in range(0, 100, 5)]:
            tier = assign_risk_tier(pct)
            self.assertIn(tier, all_tiers, f"Probability {pct} produced unexpected tier {tier}")


class TestRuleDeterminism(unittest.TestCase):
    """Precedence order must be internally consistent."""

    def test_precedence_order_is_non_empty(self):
        self.assertTrue(len(RULE_PRECEDENCE_ORDER) > 0)

    def test_precedence_contains_expected_rules(self):
        self.assertTrue(len(RULE_PRECEDENCE_ORDER) >= 12, "Expected at least 12 product rules in precedence")

    def test_precedence_values_are_unique(self):
        self.assertEqual(len(RULE_PRECEDENCE_ORDER), len(set(RULE_PRECEDENCE_ORDER)))


class TestGovernanceConfig(unittest.TestCase):
    """Runtime configuration and governance metadata must be internally consistent."""

    def test_config_loads(self):
        config = load_runtime_config()
        self.assertIsNotNone(config.risk_tier_thresholds)

    def test_config_has_risk_thresholds(self):
        config = load_runtime_config()
        thresholds = config.risk_tier_thresholds
        expected = {"Very High": 0.65, "High": 0.30, "Medium": 0.15}
        for tier, expected_threshold in expected.items():
            self.assertIn(tier, thresholds)
            self.assertAlmostEqual(thresholds[tier], expected_threshold, places=2)


if __name__ == "__main__":
    unittest.main()
