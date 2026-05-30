#!/usr/bin/env python3
"""Feature engineering layer: engineer features from canonical cleaned data."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feature_engineering.builders import (
    build_features,
    fit_lifetime_arpu_q75,
    fit_monthly_spend_q75,
    get_feature_metadata,
    get_model_feature_columns,
)
from feature_engineering.constants import CLEANED_PATH, FEATURES_DIR, SCHEMA_VERSION
from feature_engineering.qc import FeatureQCReporter
from feature_engineering.registry import MODEL_FEATURE_GROUPS
from feature_engineering.validators import validate_featured_frame

RANDOM_STATE = 42


def main() -> None:
    cleaned = pd.read_parquet(CLEANED_PATH)
    idx_train, _ = train_test_split(
        cleaned.index,
        test_size=0.3,
        stratify=cleaned["churn_binary"],
        random_state=RANDOM_STATE,
    )
    train = cleaned.loc[idx_train]
    q75_monthly = fit_monthly_spend_q75(train)
    q75_arpu = fit_lifetime_arpu_q75(train)

    featured = build_features(
        cleaned,
        monthly_spend_q75=q75_monthly,
        lifetime_arpu_q75=q75_arpu,
    )
    report = validate_featured_frame(featured, expected_rows=len(cleaned))
    report.raise_if_failed()

    model_cols = get_model_feature_columns()
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_DIR / "subscribers_featured.parquet"
    featured.to_parquet(out_path, index=False)

    qc = FeatureQCReporter()
    qc.save_feature_summary(featured)
    qc.save_group_registry()
    flag_cols = [
        "rubika_user_flag",
        "ewano_user_flag",
        "digital_engagement_score",
        "revenue_risk_segment",
        "prepaid_5g_risk_flag",
        "is_prepaid",
        "mobile_gen_ordinal",
    ]
    qc.save_value_counts(featured, flag_cols)
    for feat in ("sim_card_type", "mobile_data_generation", "revenue_risk_segment"):
        qc.save_churn_by_feature(featured, feat)
    for feat in ("digital_engagement_score", "is_prepaid"):
        qc.maybe_plot_feature(featured, feat)
    qc_meta = qc.finalize()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_cleaned": str(CLEANED_PATH),
        "output": str(out_path),
        "n_rows": int(len(featured)),
        "thresholds_fit_on": "train_split_70pct_stratified",
        "monthly_spend_q75": q75_monthly,
        "lifetime_arpu_q75": q75_arpu,
        "random_state": RANDOM_STATE,
        "model_feature_columns_ordered": model_cols,
        "model_feature_groups": MODEL_FEATURE_GROUPS,
        "n_model_features": len(model_cols),
        "feature_registry": get_feature_metadata(),
        "validation": report.metrics,
        "qc": qc_meta,
        "notes": [
            "Three-layer FE: predictive, business_semantic, interaction.",
            "Tri-state service flags use -1 for 2G structural N/A.",
            "Train-fitted Q75 thresholds for spend tier flags only.",
            "Canonical cleaned columns preserved unchanged.",
        ],
    }
    (FEATURES_DIR / "feature_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {out_path} ({len(featured)} rows, {len(model_cols)} model features)")
    print(f"QC: {qc_meta.get('feature_qc_index')}")


if __name__ == "__main__":
    main()
