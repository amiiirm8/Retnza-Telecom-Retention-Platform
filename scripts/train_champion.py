#!/usr/bin/env python3
"""Train champion model (multi-candidate selection + calibration)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modeling.champion import train_champion


def main() -> None:
    report = train_champion()
    m = report.manifest
    sel = m["selection"]
    print(f"Saved: {report.model_path}")
    print(f"Champion family: {m['champion_family']}")
    print(f"Selection rule: {sel['selection_rule']}")
    print(f"Tolerance: abs={sel['tolerance_abs']} rel={sel['tolerance_rel']}")
    print(f"Winner rationale: {sel['selection_rationale']['winner_family']}")
    print(f"Calibration: {m['selected_calibration']}")
    print(f"Stability ref: {m.get('stability_summary_ref')}")
    print(f"Operating threshold: {m['operating_threshold']:.3f} ({m['recommended_operating_policy']})")
    u = m["uncalibrated_vs_selected_test"]
    print(
        f"Test PR-AUC raw={u['pr_auc_raw']:.4f} cal={u['pr_auc_calibrated']:.4f} | "
        f"Brier raw={u['brier_raw']:.4f} cal={u['brier_calibrated']:.4f}"
    )
    for w in m.get("warnings", [])[:2]:
        print("WARN:", w)


if __name__ == "__main__":
    main()
