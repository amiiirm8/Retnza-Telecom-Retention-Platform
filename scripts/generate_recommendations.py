#!/usr/bin/env python3
"""Generate Task 7/8 subscriber recommendations for all customers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from recommendation.engine import generate_recommendations

SHAP_PATH = ROOT / "outputs" / "explainability" / "subscriber_shap_values.parquet"


def main() -> None:
    shap_path = SHAP_PATH if SHAP_PATH.is_file() else None
    rec, manifest = generate_recommendations(merge_shap_path=shap_path)
    print(f"Wrote {manifest['output_path']} ({manifest['n_subscribers']} rows)")
    print("Schema:", manifest["schema_version"])
    print("Risk tiers:", manifest["risk_tier_counts"])
    print("Top rules:", dict(list(manifest["rule_id_counts"].items())[:8]))
    eco = manifest.get("ecosystem_analytics", {})
    print("Ecosystem segments (top):", dict(list(manifest.get("ecosystem_segment_counts", {}).items())[:5]))
    print("High-risk non-ecosystem:", eco.get("high_risk_non_ecosystem_subscribers"))
    print("SHAP merge:", manifest.get("shap_merge_validation", {}).get("merged"))


if __name__ == "__main__":
    main()
