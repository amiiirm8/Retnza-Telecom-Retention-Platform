#!/usr/bin/env python3
"""Generate SHAP artifacts for Task 7."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modeling.explainability import run_shap_analysis


def main() -> None:
    manifest = run_shap_analysis()
    print("Top global drivers:")
    for row in manifest["top_global_drivers"][:5]:
        print(
            f"  {row['business_label']:40} |SHAP|={row['mean_abs_shap']:.4f} "
            f"direction={row['direction_overall']}"
        )
    print(f"Population SHAP: {manifest['outputs'].get('population_shap', 'n/a')}")
    print("\nWrote outputs to outputs/explainability/")


if __name__ == "__main__":
    main()
