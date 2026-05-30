#!/usr/bin/env python3
"""Task 2: build data/raw snapshot and canonical data/cleaned only."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.pipeline import PreprocessingConfig, run_preprocessing


def main() -> None:
    arts = run_preprocessing(PreprocessingConfig(verbose=True, write_qc_artifacts=True))
    m = arts.manifest
    print("Task 2 complete (canonical cleaned only).")
    print("Schema:", m["schema_version"])
    print("Rows:", m["row_counts"])
    print("Paths:", m["paths"])
    print(
        "QC:",
        f"tenure_zero={m['spend_policy']['tenure_zero_rows']}",
        f"ambiguous_billing={m['spend_policy']['ambiguous_billing_rows']}",
        f"2G={m['segment_counts']['n_2g']}",
    )


if __name__ == "__main__":
    main()
