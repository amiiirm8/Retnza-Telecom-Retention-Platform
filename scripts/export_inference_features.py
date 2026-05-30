#!/usr/bin/env python3
"""
Export full-population featured matrix for BI / batch scoring.

Uses feature-schema feature engineering (NOT legacy ColumnTransformer).
NOT for held-out evaluation metrics.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feature_engineering.builders import build_features, fit_lifetime_arpu_q75, fit_monthly_spend_q75
from modeling.config import CLEANED_PATH
from preprocessing.config import INFERENCE_DIR


def main() -> None:
    cleaned = pd.read_parquet(CLEANED_PATH)
    # Fit thresholds on full data — inference/BI only (documented leakage for metrics).
    q_m = fit_monthly_spend_q75(cleaned)
    q_a = fit_lifetime_arpu_q75(cleaned)
    featured = build_features(cleaned, monthly_spend_q75=q_m, lifetime_arpu_q75=q_a)

    INFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = INFERENCE_DIR / "subscribers_inference_features.parquet"
    featured.to_parquet(out, index=False)

    manifest = {
        "schema_version": "inference-featured-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "INFERENCE_AND_BI_EXPORT_ONLY",
        "not_for": ["held_out_evaluation", "test_metrics"],
        "fitted_on": "full_population",
        "n_rows": len(featured),
        "feature_contract": "feature_engineering.MODEL_FEATURE_COLUMNS + cleaned cols",
    }
    (INFERENCE_DIR / "inference_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Wrote {out} ({len(featured)} rows)")


if __name__ == "__main__":
    main()
