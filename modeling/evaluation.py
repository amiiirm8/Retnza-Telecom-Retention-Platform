"""Telecom churn evaluation metrics and diagnostics.

Provides all metric computation functions used across the modeling pipeline:
  - expected_calibration_error (ECE)
  - evaluate_probs (full metric block: ranking + calibration + ops at threshold)
  - ranking_metrics (threshold-independent: ROC-AUC, PR-AUC, Brier, ECE)
  - pr_curve_points (precision-recall curve at discrete steps)
  - top_k_contact_metrics (CRM capacity: precision/recall/lift at top-k%)
  - decile_gain_table (cumulative gains by score decile for executive reporting)

Pipeline position: consumed by baselines.py, calibration.py, champion.py,
  stability.py, thresholds.py, and explainability.py.
Workflow stage: training + reporting.
Key invariants:
  - All functions operate on numpy arrays (y_true, y_prob) — no DataFrame coupling.
  - evaluate_probs returns a comprehensive block including confusion matrix,
    calibration curve, and lift vs base rate.
  - threshold-dependent metrics are always computed at a caller-provided threshold.
  - ranking_metrics deliberately excludes threshold-dependent metrics.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE) over equal-width bins.

    ECE measures the absolute difference between predicted probability and
    observed frequency, weighted by bin population. Lower is better; 0 is perfect.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities.
        n_bins: Number of equal-width bins in [0, 1] (default 10).

    Returns:
        ECE as a float in [0, 1].
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y_true[mask].mean() - y_prob[mask].mean())
    return float(ece)


def evaluate_probs(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
    n_calibration_bins: int = 10,
) -> dict[str, Any]:
    """Full metric block: ranking metrics + calibration metrics + operating point.

    This is the workhorse evaluation function used throughout the pipeline. It returns
    a comprehensive dict that can be used for both reporting and champion comparison.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities (raw or calibrated).
        threshold: Decision threshold for binary metrics (precision, recall, F1, FNR).
        n_calibration_bins: Number of bins for calibration curve and ECE computation.

    Returns:
        dict with keys:
          - threshold, roc_auc, pr_auc, brier_score, ece
          - precision, recall, f1, false_negative_rate, base_rate, lift_at_threshold
          - confusion_matrix: {tn, fp, fn, tp}
          - calibration_curve: {mean_predicted, fraction_positive}
    """
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    base_rate = float(y_true.mean())

    prob_true, prob_pred = calibration_curve(
        y_true, y_prob, n_bins=n_calibration_bins, strategy="uniform"
    )

    precision_at_threshold = float(precision_score(y_true, y_pred, zero_division=0))
    recall_at_threshold = float(recall_score(y_true, y_pred, zero_division=0))

    return {
        "threshold": threshold,
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "ece": expected_calibration_error(y_true, y_prob, n_bins=n_calibration_bins),
        "precision": precision_at_threshold,
        "recall": recall_at_threshold,
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_negative_rate": fnr,
        "base_rate": base_rate,
        "lift_at_threshold": (
            (precision_at_threshold / base_rate) if base_rate > 0 else 0.0
        ),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration_curve": {
            "mean_predicted": prob_pred.tolist(),
            "fraction_positive": prob_true.tolist(),
        },
    }


def pr_curve_points(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    step: float = 0.05,
) -> list[dict[str, float]]:
    """Compute precision-recall curve at discrete threshold steps.

    Used for PR curve plotting and threshold analysis in reports.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities.
        step: Threshold step size (default 0.05).

    Returns:
        List of dicts with 'threshold', 'precision', 'recall' at each step.
    """
    points = []
    for t in np.arange(0.05, 0.96, step):
        pred = (y_prob >= t).astype(int)
        points.append(
            {
                "threshold": float(t),
                "precision": float(precision_score(y_true, pred, zero_division=0)),
                "recall": float(recall_score(y_true, pred, zero_division=0)),
            }
        )
    return points


def top_k_contact_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    fractions: tuple[float, ...] = (0.10, 0.20, 0.30),
) -> list[dict[str, float]]:
    """Compute CRM contact capacity metrics (precision, recall, lift) at top-k%.

    Models CRM capacity: if we contact the top k% of subscribers by churn score,
    what precision (fraction of actual churners caught) and recall (fraction of
    all churners caught) do we achieve? Lift vs base rate quantifies the enrichment.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities (raw scores — this is the ranking layer).
        fractions: Fractions of the population to contact (default: 10%, 20%, 30%).

    Returns:
        List of dicts, one per fraction, with keys: 'top_fraction', 'n_contacted',
        'precision', 'recall', 'lift_vs_base_rate'.
    """
    n = len(y_true)
    order = np.argsort(-y_prob)
    base = float(y_true.mean())
    out = []
    for frac in fractions:
        k = max(1, int(np.ceil(n * frac)))
        idx = order[:k]
        tp = int(((y_true[idx] == 1)).sum())
        fn = int(((y_true == 1) & ~np.isin(np.arange(n), idx)).sum())
        prec = tp / k if k else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        out.append(
            {
                "top_fraction": frac,
                "n_contacted": k,
                "precision": prec,
                "recall": rec,
                "lift_vs_base_rate": (prec / base) if base > 0 else 0.0,
            }
        )
    return out


def decile_gain_table(y_true: np.ndarray, y_prob: np.ndarray) -> list[dict[str, Any]]:
    """Compute cumulative gains by score decile for executive reporting.

    Sorts by predicted probability descending, then divides into 10 equal-sized
    deciles. Reports churn_rate and lift vs base rate for each decile.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities.

    Returns:
        List of dicts, one per decile, with keys: 'decile', 'n', 'churn_rate', 'lift'.
    """
    n = len(y_true)
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]
    base = float(y_true.mean())
    rows = []
    for d in range(10):
        lo = int(d * n / 10)
        hi = int((d + 1) * n / 10)
        if hi <= lo:
            continue
        chunk = y_sorted[lo:hi]
        rows.append(
            {
                "decile": d + 1,
                "n": int(hi - lo),
                "churn_rate": float(chunk.mean()),
                "lift": float(chunk.mean() / base) if base > 0 else 0.0,
            }
        )
    return rows


def ranking_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    """Compute threshold-independent ranking metrics for model selection.

    Unlike evaluate_probs(), this function intentionally excludes all
    threshold-dependent metrics (precision, recall, F1, FNR). This is used
    for model comparison where we want to evaluate pure ranking power
    before choosing an operating point.

    Args:
        y_true: Ground-truth binary labels.
        y_prob: Predicted probabilities.

    Returns:
        dict with keys: 'roc_auc', 'pr_auc', 'brier_score', 'ece'.
    """
    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "ece": expected_calibration_error(y_true, y_prob),
    }
