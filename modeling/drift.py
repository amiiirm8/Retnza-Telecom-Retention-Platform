"""Drift-monitoring reference snapshots (training-time baselines for PSI / score monitoring).

Builds reference distributions for feature values, score histograms, and PSI-ready
bin tables at training time. These are consumed post-deployment by the monitoring
pipeline to detect data drift (feature distribution shift) and score drift
(model score distribution shift).

Pipeline position: called by train_champion() in champion.py after model selection
and calibration are complete.
Workflow stage: training (reference capture) + reporting (stored for monitoring).
Key invariants:
  - The snapshot captures train/val/test distributions separately so monitoring
    can compare production scores against the appropriate reference.
  - PSI tables are pre-computed bin counts (not actual PSI values) — the monitoring
    pipeline computes PSI at inference time using the same bin edges.
  - Feature quantiles are limited to the first 20 numeric features to keep the
    snapshot file size manageable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modeling.config import OUTPUT_CHAMPION, OUTPUT_GOVERNANCE


def _histogram_bins(values: np.ndarray, n_bins: int = 10) -> dict[str, Any]:
    """Compute histogram bin edges and counts for a probability array.

    Args:
        values: Probability values (expected in [0, 1]).
        n_bins: Number of equal-width bins in [0, 1].

    Returns:
        dict with 'bin_edges', 'counts', and 'n'. Returns zero-entry result
        if input is empty or all-non-finite.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {"bins": [], "counts": [], "n": 0}
    counts, edges = np.histogram(values, bins=n_bins, range=(0.0, 1.0))
    return {
        "bin_edges": edges.tolist(),
        "counts": counts.astype(int).tolist(),
        "n": int(len(values)),
    }


def _feature_quantile_snapshot(df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    """Compute univariate quantile stats for numeric feature columns.

    Args:
        df: DataFrame (train, val, or test split).
        columns: Candidate feature names (filtered to first 20 numeric in caller).

    Returns:
        dict mapping column name -> {mean, std, p25, p50, p75, min, max, n}.
        Non-numeric or missing columns are silently skipped.
    """
    snap: dict[str, Any] = {}
    for col in columns:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        snap[col] = {
            "mean": float(s.mean()),
            "std": float(s.std()),
            "p25": float(s.quantile(0.25)),
            "p50": float(s.quantile(0.50)),
            "p75": float(s.quantile(0.75)),
            "min": float(s.min()),
            "max": float(s.max()),
            "n": int(len(s)),
        }
    return snap


def _psi_ready_table(
    reference: np.ndarray,
    current: np.ndarray,
    n_bins: int = 10,
) -> list[dict[str, Any]]:
    """Compute bin proportions for manual PSI calculation.

    Returns bin-wise reference_pct and current_pct. The monitoring pipeline uses
    these to compute: PSI = sum (p_cur - p_ref) * ln(p_cur / p_ref).

    Args:
        reference: Reference probability array (e.g. train scores).
        current: Current probability array (e.g. val or test scores).
        n_bins: Number of equal-width bins in [0, 1].

    Returns:
        List of dicts, one per bin, with 'bin', 'lo', 'hi', 'reference_pct', 'current_pct'.
        Each bin has at least 1 count to avoid division-by-zero in PSI.
    """
    ref = np.clip(np.asarray(reference, dtype=float), 0, None)
    cur = np.clip(np.asarray(current, dtype=float), 0, None)
    edges = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        r_mask = (ref >= lo) & (ref < hi if i < n_bins - 1 else ref <= hi)
        c_mask = (cur >= lo) & (cur < hi if i < n_bins - 1 else cur <= hi)
        r_cnt = max(int(r_mask.sum()), 1)
        c_cnt = max(int(c_mask.sum()), 1)
        rows.append(
            {
                "bin": i + 1,
                "lo": float(lo),
                "hi": float(hi),
                "reference_pct": r_cnt / len(ref),
                "current_pct": c_cnt / len(cur),
            }
        )
    return rows


def build_drift_snapshot(
    *,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_columns: list[str],
    p_train_raw: np.ndarray,
    p_val_raw: np.ndarray,
    p_test_raw: np.ndarray,
    p_val_cal: np.ndarray,
    p_test_cal: np.ndarray,
    calibration_method: str,
    model_family: str,
    baseline_metrics: dict[str, Any],
    schema_version: str,
) -> dict[str, Any]:
    """Build a comprehensive drift reference snapshot for post-deployment monitoring.

    Captures:
      - Feature distribution quantiles (first 20 numeric features).
      - Score distribution histograms (raw and calibrated) for train/val/test.
      - PSI-ready bin tables (validation_vs_train, test_vs_train).
      - Baseline holdout metrics (ranking + operating point).
      - Churn rate by split.
      - Monitoring notes with recommended actions.

    Args:
        train_df: Training split DataFrame (for feature quantiles and churn rate).
        val_df: Validation split DataFrame.
        test_df: Test split DataFrame.
        feature_columns: List of all feature column names.
        p_train_raw: Raw base-model probabilities on training split.
        p_val_raw: Raw base-model probabilities on validation split.
        p_test_raw: Raw base-model probabilities on test split.
        p_val_cal: Calibrated probabilities on validation split.
        p_test_cal: Calibrated probabilities on test split.
        calibration_method: Name of the selected calibration method ('none', 'sigmoid', 'isotonic').
        model_family: Name of the selected champion model family.
        baseline_metrics: dict with 'test_ranking_raw' and 'test_at_operating' metrics.
        schema_version: Modeling schema version string.

    Returns:
        A dict suitable for JSON serialization, structured as a monitoring reference.
    """
    numeric_feats = [
        c
        for c in feature_columns
        if c in train_df.columns and pd.api.types.is_numeric_dtype(train_df[c])
    ][:20]

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        "model_family": model_family,
        "calibration_method": calibration_method,
        "n_features": len(feature_columns),
        "feature_columns_hash": hash(tuple(feature_columns)),
        "feature_column_version": feature_columns,
        "feature_distribution_train": _feature_quantile_snapshot(train_df, numeric_feats),
        "score_distribution": {
            "raw_train": _histogram_bins(p_train_raw),
            "raw_validation": _histogram_bins(p_val_raw),
            "raw_test": _histogram_bins(p_test_raw),
            "calibrated_validation": _histogram_bins(p_val_cal),
            "calibrated_test": _histogram_bins(p_test_cal),
        },
        "psi_ready_score_raw": {
            "validation_vs_train": _psi_ready_table(p_train_raw, p_val_raw),
            "test_vs_train": _psi_ready_table(p_train_raw, p_test_raw),
        },
        "baseline_metrics_holdout": baseline_metrics,
        "churn_rate_reference": {
            "train": float(train_df["churn_binary"].mean()) if "churn_binary" in train_df else None,
            "validation": float(val_df["churn_binary"].mean()) if "churn_binary" in val_df else None,
            "test": float(test_df["churn_binary"].mean()) if "churn_binary" in test_df else None,
        },
        "monitoring_notes": [
            "Compare production score histograms to score_distribution.raw_*",
            "PSI on raw ranking scores recommended monthly",
            "Feature drift: compare production quantiles to feature_distribution_train",
            "Recalibrate if ECE degrades >2x vs baseline_metrics_holdout",
        ],
    }


def save_drift_snapshot(snapshot: dict[str, Any], path: Path | None = None) -> Path:
    """Persist the full drift snapshot to OUTPUT_CHAMPION / drift_reference_snapshot.json.

    Args:
        snapshot: The dict returned by build_drift_snapshot().
        path: Output path. Defaults to OUTPUT_CHAMPION / 'drift_reference_snapshot.json'.

    Returns:
        Path to the written JSON file.

    Side effects: Creates parent directory if needed and writes JSON.
    """
    path = path or OUTPUT_CHAMPION / "drift_reference_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    return path


def save_drift_summary_governance(snapshot: dict[str, Any]) -> Path:
    """Write a slimmed-down drift reference summary to the governance output directory.

    Extracts only the metadata fields (schema, family, churn rates, baseline metrics,
    monitoring notes) for quick review without the full feature quantiles.

    Args:
        snapshot: The full drift snapshot dict.

    Returns:
        Path to the written JSON file.

    Side effects: Creates OUTPUT_GOVERNANCE directory and writes JSON.
    """
    OUTPUT_GOVERNANCE.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_GOVERNANCE / "drift_reference_summary.json"
    slim = {
        k: snapshot[k]
        for k in (
            "generated_at_utc",
            "schema_version",
            "model_family",
            "calibration_method",
            "n_features",
            "churn_rate_reference",
            "baseline_metrics_holdout",
            "monitoring_notes",
        )
        if k in snapshot
    }
    path.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    return path
