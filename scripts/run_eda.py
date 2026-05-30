#!/usr/bin/env python3
"""Task 3: EDA tables and segment stats from canonical cleaned data."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLEANED = ROOT / "data" / "cleaned" / "subscribers_cleaned.parquet"
OUT = ROOT / "outputs" / "eda"


def cramers_v(table: pd.DataFrame) -> float:
    chi2, _, _, _ = stats.chi2_contingency(table)
    n = table.sum().sum()
    k = min(table.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 and n > 0 else 0.0


def segment_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    overall = df["churn_binary"].mean()
    g = df.groupby(col, observed=True).agg(
        n=("churn_binary", "count"),
        churn_rate=("churn_binary", "mean"),
    )
    g["lift"] = g["churn_rate"] / overall
    return g.reset_index()


def main() -> None:
    df = pd.read_parquet(CLEANED)
    OUT.mkdir(parents=True, exist_ok=True)
    overall = float(df["churn_binary"].mean())

    # Core segment tables
    segment_table(df, "sim_card_type").to_csv(OUT / "churn_by_sim_type.csv", index=False)
    segment_table(df, "mobile_data_generation").to_csv(OUT / "churn_by_generation.csv", index=False)

    df["tenure_band"] = pd.cut(
        df["sim_tenure_months"],
        bins=[-1, 6, 12, 24, 60, 72],
        labels=["0-6", "7-12", "13-24", "25-60", "61+"],
    )
    segment_table(df, "tenure_band").to_csv(OUT / "churn_by_tenure_band.csv", index=False)

    # Facet: gen x sim
    facet = (
        df.groupby(["sim_card_type", "mobile_data_generation"], observed=True)["churn_binary"]
        .agg(n="count", churn_rate="mean")
        .reset_index()
    )
    facet["lift"] = facet["churn_rate"] / overall
    facet.to_csv(OUT / "churn_by_sim_and_generation.csv", index=False)

    # Data-capable VoLTE
    cap = df[df["is_data_capable"] == 1]
    segment_table(cap, "volte_service").to_csv(OUT / "churn_volte_data_capable.csv", index=False)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(CLEANED),
        "n_rows": int(len(df)),
        "overall_churn_rate": overall,
        "ambiguous_billing_rows": int(df["billing_definition_ambiguous_flag"].sum()),
        "outputs": [
            "churn_by_sim_type.csv",
            "churn_by_generation.csv",
            "churn_by_tenure_band.csv",
            "churn_by_sim_and_generation.csv",
            "churn_volte_data_capable.csv",
        ],
        "docs": "docs/EXPLORATORY_ANALYSIS.md",
    }
    (OUT / "eda_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"EDA outputs written to {OUT}")


if __name__ == "__main__":
    main()
