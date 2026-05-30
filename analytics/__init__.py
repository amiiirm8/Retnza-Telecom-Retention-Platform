"""Analytics intelligence layer for telecom churn and retention platform.

Workflow stage: reporting-time — all analytics run after recommendations have
been generated. No uplift modeling, no causal inference, no treatment effect
estimation.

This package extends the production pipeline with:
  - Customer/demographic intelligence
  - SHAP interaction analysis (associative, not causal)
  - Rule precision diagnostics (Jaccard overlap, precision labels)
  - Retention KPI/ROI simulation (illustrative scenarios, not causal)
  - Campaign saturation analytics (channel overload risk indicators)
  - Executive storytelling (associative wording throughout)
  - Governance validations (artifact compatibility, schema safety)

Pipeline position: final layer. Reads from recommendation, production-champion-bundle,
shap-explainability, and feature-schema artifacts. Produces analytics artifacts under
outputs/analytics/ and outputs/dashboard/.

Key invariants:
  - All narratives use associative wording only (no causal claims).
  - Scenario projections are illustrative, not guaranteed.
  - SHAP describes model predictions, not real-world effects.
  - Governance checks validate schema compatibility, not model performance.
"""

from __future__ import annotations

ANALYTICS_SCHEMA_VERSION = "analytics-v1"
ANALYTICS_COMPATIBLE_RECOMMENDATIONS = "task8-recommendations-v4"
ANALYTICS_COMPATIBLE_CHAMPION = "champion-bundle-v4"
ANALYTICS_COMPATIBLE_SHAP = "task7-shap-v4"
ANALYTICS_COMPATIBLE_FEATURES = "task4-v2"

__all__: list[str] = []
