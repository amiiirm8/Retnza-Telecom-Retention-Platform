#!/usr/bin/env python3
"""Export flat CRM / Power BI table per Task 9 export contract."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REC_PATH = ROOT / "outputs" / "recommendations" / "subscriber_recommendations.csv"
OUT_DIR = ROOT / "outputs" / "powerbi"

# Task 9 CRM export contract (required + optional columns)
EXPORT_COLUMNS = [
    "subscriber_id",
    "churn_probability",
    "churn_probability_raw",
    "risk_tier",
    "top_driver",
    "recommended_action",
    "rule_id",
    "campaign_priority",
    "campaign_queue_rank",
    "primary_channel",
    "intervention_type",
    "human_touch_flag",
    "campaign_cost_tier",
    "secondary_channel",
    "shap_explanation_summary",
]

COLUMN_LABELS = {
    "churn_probability": "predicted_churn_probability_calibrated",
    "churn_probability_raw": "model_score_ranking_raw",
}


def main() -> None:
    if not REC_PATH.is_file():
        raise FileNotFoundError(f"Run generate_recommendations first: {REC_PATH}")

    rec = pd.read_csv(REC_PATH)
    missing = [c for c in EXPORT_COLUMNS if c not in rec.columns]
    if missing:
        raise ValueError(f"Recommendations missing columns: {missing}")

    out = rec[EXPORT_COLUMNS].copy()
    out = out.rename(columns=COLUMN_LABELS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "crm_action_queue.csv"
    out.to_csv(csv_path, index=False)

    manifest = {
        "schema_version": "powerbi-crm-export-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(REC_PATH),
        "n_rows": int(len(out)),
        "export_contract_columns": list(out.columns),
        "label_policy": {
            "predicted_churn_probability_calibrated": "Model output (calibrated); not historical churn",
            "model_score_ranking_raw": "RF ranking score; use for sort/top-decile",
        },
        "output_path": str(csv_path),
    }
    (OUT_DIR / "powerbi_export_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Wrote {csv_path} ({len(out)} rows, {len(out.columns)} columns)")


if __name__ == "__main__":
    main()
