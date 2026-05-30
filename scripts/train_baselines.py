#!/usr/bin/env python3
"""Run Task 5 baseline experiments."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modeling.baseline import run_baselines, save_baseline_report


def main() -> None:
    report = run_baselines()
    path = save_baseline_report(report)
    print(f"Wrote {path}")
    dec = report.get("baseline_decisions", {})
    if dec:
        print("Ranking:", dec.get("ranking_propensity"))
        print("Contact:", dec.get("campaign_contact"))
    rows = sorted(report["results"], key=lambda r: r["test"]["pr_auc"], reverse=True)
    print("\nTop 5 test PR-AUC:")
    for r in rows[:5]:
        print(
            f"  {r['model']:22} {r['imbalance_strategy']:14} "
            f"PR-AUC={r['test']['pr_auc']:.4f} R={r['test']['recall']:.2f} P={r['test']['precision']:.2f}"
        )


if __name__ == "__main__":
    main()
