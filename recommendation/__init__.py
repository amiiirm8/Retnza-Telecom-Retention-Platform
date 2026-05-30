"""Rule-based retention recommendation engine (Rule-based retention recommendation engine).

This package generates per-subscriber retention recommendations using
deterministic business rules (not ML-driven recommendations). The pipeline is:

  1. Score subscribers with champion model → calibrated churn probability
  2. Assign risk tier via thresholds from modeling
  3. Match business rules in priority order (rules.py) → rule_id, action
  4. Resolve operational metadata (channels, cost, urgency) via operational.py
  5. Enrich with ecosystem segmentation (ecosystem.py)
  6. Optionally overlay SHAP narrative for Very High / High tiers (shap_merge.py)

Key invariants:
  - All actions are rule-driven, never ML-selected. SHAP is narrative-only.
  - Ecosystem metrics are associative, not causal.
  - Pipeline stage: inference/reporting-time (not training).
  - R99 fallback catches high-risk subscribers with no rule match.
"""

from recommendation.engine import (
    CAMPAIGN_PRIORITY_BY_TIER,
    RecommendationRule,
    apply_recommendations,
    assign_risk_tier,
    generate_recommendations,
)

__all__ = [
    "CAMPAIGN_PRIORITY_BY_TIER",
    "RecommendationRule",
    "apply_recommendations",
    "assign_risk_tier",
    "generate_recommendations",
]
