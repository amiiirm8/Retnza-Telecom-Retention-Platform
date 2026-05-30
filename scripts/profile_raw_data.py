#!/usr/bin/env python3
"""Regenerate Task 1 profiling artifacts (data/schema/task1_column_profile.json)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RAW = ROOT / "MCI_Challenge_FinalDataset.csv"
OUT = ROOT / "data" / "schema" / "task1_column_profile.json"

PLACEHOLDER_STRINGS = {"", " ", "NA", "N/A", "null", "None", "ندارد", "-", "—", "nan", "NaN"}


def norm_col(c: str) -> str:
    return str(c).strip().replace("\u200c", "").replace("\u200d", "")


def check_string_quality(series: pd.Series) -> list[dict]:
    issues = []
    s = series.astype(str)
    stripped = s.str.strip()
    if (stripped == "").sum():
        issues.append({"type": "blank_string", "count": int((stripped == "").sum())})
    ph = stripped.isin(PLACEHOLDER_STRINGS)
    if ph.sum():
        issues.append({"type": "placeholder_string", "count": int(ph.sum())})
    return issues


def main() -> None:
    df = pd.read_csv(RAW, encoding="utf-8")
    df.columns = [norm_col(c) for c in df.columns]
    profile: dict = {"n_rows": len(df), "n_cols": len(df.columns), "columns": {}}

    for col in df.columns:
        s = df[col]
        entry: dict = {
            "pandas_dtype": str(s.dtype),
            "missing_nan": int(s.isna().sum()),
            "missing_nan_pct": round(100 * float(s.isna().mean()), 4),
            "string_quality_issues": check_string_quality(s) if s.dtype == object else [],
            "n_unique": int(s.nunique(dropna=False)),
        }
        if pd.api.types.is_numeric_dtype(s):
            entry.update(
                {
                    "min": float(s.min()),
                    "max": float(s.max()),
                    "mean": round(float(s.mean()), 4),
                    "median": float(s.median()),
                }
            )
        else:
            vc = s.value_counts()
            entry["value_counts"] = {str(k): int(v) for k, v in vc.items()}
        profile["columns"][col] = entry

    tenure = [c for c in df.columns if "سابقه" in c][0]
    monthly, cum = "هزینه_ماهیانه_تومان", "هزینه_کل_تومان"
    t0 = df[tenure] == 0
    profile["tenure_zero_analysis"] = {
        "count": int(t0.sum()),
        "monthly_gt0_cum_eq0": int((t0 & (df[cum] == 0) & (df[monthly] > 0)).sum()),
        "sample": df.loc[t0, [df.columns[0], tenure, monthly, cum, "ریزش"]].head(11).to_dict(
            orient="records"
        ),
    }
    profile["spend_identity_check"] = {
        "rows_exact_monthly_x_tenure": int((df[cum] == df[monthly] * df[tenure]).sum()),
        "pct": round(100 * (df[cum] == df[monthly] * df[tenure]).mean(), 2),
    }
    profile["duplicates"] = {
        "full_row": int(df.duplicated().sum()),
        "id_column": int(df.iloc[:, 0].duplicated().sum()),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
