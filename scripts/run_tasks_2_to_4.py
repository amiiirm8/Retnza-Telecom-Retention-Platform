#!/usr/bin/env python3
"""Run Task 2 (v2) → Task 3 EDA → Feature engineering layer feature engineering."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "build_datasets.py",
    "run_eda.py",
    "build_features.py",
]


def main() -> None:
    py = sys.executable
    for name in SCRIPTS:
        path = ROOT / "scripts" / name
        print(f"\n=== {name} ===")
        subprocess.run([py, str(path)], cwd=ROOT, check=True)
    print("\nPipeline Tasks 2–4 complete.")


if __name__ == "__main__":
    main()
