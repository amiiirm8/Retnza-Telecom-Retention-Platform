"""Telecom operating threshold policies (retention / contact budget).

Defines the threshold policies used for CRM campaign decisions. The core business
policy (business_min_recall_validation) is designed for the telecom retention
context where FN cost (missed churner) >> FP cost (false alarm):
  - A missed churner churns permanently, resulting in lost recurring revenue.
  - A false alarm receives a save offer (cost of the offer) but remains a subscriber.

Policy types:
  - default_0.5: Standard probabilistic cutoff. Reference only — not tuned for FN cost.
  - business_min_recall_validation: Lowest threshold achieving MIN_RECALL_CONTACT
    recall with MIN_PRECISION_CONTACT precision (when feasible). Primary operating policy.
  - max_f1_validation: Balanced F1 threshold. Reference only.
  - top_decile_validation_score: Top 10% by calibrated score. CRM capacity view.

Why thresholds are chosen the way they are:
  The business_min_recall_validation policy explicitly targets high recall (catch
  >=75% of churners) at the lowest possible threshold while maintaining a precision
  floor (>=50% when feasible). This is a deliberate trade-off: we accept more false
  alarms to catch more true churners because the cost of a missed churner is much
  higher than a false alarm in the telecom retention domain.

Pipeline position: consumed by baselines.py (for baseline threshold resolution) and
  champion.py (for champion manifest threshold reporting).
Workflow stage: training (threshold resolution on validation) + reporting.
Key invariants:
  - All thresholds are resolved on VALIDATION probabilities only. Test is purely evaluative.
  - Threshold sweep range: 0.10 to 0.89 in 0.01 steps.
  - business_min_recall_validation includes a tolerance band (RECALL_TOLERANCE,
    PRECISION_TOLERANCE) to avoid empty candidate sets.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

from modeling.config import (
    DEFAULT_THRESHOLD,
    MIN_PRECISION_CONTACT,
    MIN_RECALL_CONTACT,
    PRECISION_TOLERANCE,
    RECALL_TOLERANCE,
)
from modeling.evaluation import evaluate_probs, top_k_contact_metrics


def best_f1_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Find the threshold that maximises F1 score.

    This is a reference threshold only — it provides balanced precision and recall
    but is NOT the primary business policy. In telecom retention, we deliberately
    trade F1 for higher recall because FN cost >> FP cost.

    Args:
        y_true: Ground-truth labels.
        y_prob: Predicted probabilities.

    Returns:
        Threshold value in [0.10, 0.89] that maximises F1.
    """
    best_t, best_f1 = 0.5, -1.0
    for t in np.arange(0.10, 0.90, 0.01):
        f1 = f1_score(y_true, (y_prob >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return best_t


def threshold_at_min_recall(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    min_recall: float = MIN_RECALL_CONTACT,
) -> float:
    """Find the lowest threshold that achieves at least min_recall recall.

    This is the fallback called by select_threshold_business_policy when the
    combined recall+precision floor cannot be met. It sacrifices precision to
    guarantee the recall target.

    Args:
        y_true: Ground-truth labels.
        y_prob: Predicted probabilities.
        min_recall: Minimum recall target (default MIN_RECALL_CONTACT = 0.75).

    Returns:
        Lowest threshold in [0.10, 0.89] achieving min_recall, or 0.10 if none.
    """
    for t in np.arange(0.10, 0.90, 0.01):
        if recall_score(y_true, (y_prob >= t).astype(int), zero_division=0) >= min_recall:
            return float(t)
    return 0.10


def select_threshold_business_policy(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    min_recall: float = MIN_RECALL_CONTACT,
    min_precision: float | None = MIN_PRECISION_CONTACT,
    *,
    recall_tolerance: float = RECALL_TOLERANCE,
    precision_tolerance: float = PRECISION_TOLERANCE,
) -> dict[str, float]:
    """Select the best operating threshold for telecom retention.

    Business logic (why FN cost > FP cost):
      - A missed churner (FN) churns permanently, losing all future revenue.
      - A false alarm (FP) receives a save offer — the cost is the offer itself,
        but the subscriber stays and continues generating revenue.
      Therefore, we prioritise recall over precision: we want the lowest threshold
      that catches at least MIN_RECALL_CONTACT of churners, while maintaining a
      precision floor of MIN_PRECISION_CONTACT when feasible.

    Selection logic:
      1. Sweep thresholds from 0.10 to 0.89 in 0.01 steps.
      2. Keep candidates meeting recall >= (min_recall - recall_tolerance) AND
         precision >= (min_precision - precision_tolerance) [if precision target set].
      3. Pick the lowest threshold among candidates (highest sensitivity).
      4. If no candidate meets both targets, fall back to threshold_at_min_recall
         (precision floor is sacrificed).

    Args:
        y_true: Ground-truth labels.
        y_prob: Predicted probabilities.
        min_recall: Recall floor (default MIN_RECALL_CONTACT = 0.75).
        min_precision: Precision floor (default MIN_PRECISION_CONTACT = 0.50).
            Pass None to disable precision constraint.
        recall_tolerance: Relaxation on recall floor (default 0.02).
        precision_tolerance: Relaxation on precision floor (default 0.05).

    Returns:
        dict with 'threshold', 'precision', 'recall', and 'policy' describing
        which constraint drove the selection.
    """
    rec_floor = max(0.0, min_recall - recall_tolerance)
    prec_floor = (
        max(0.0, (min_precision or 0) - precision_tolerance) if min_precision is not None else None
    )

    candidates: list[tuple[float, float, float]] = []
    for t in np.arange(0.10, 0.90, 0.01):
        pred = (y_prob >= t).astype(int)
        rec = recall_score(y_true, pred, zero_division=0)
        prec = precision_score(y_true, pred, zero_division=0)
        if rec >= rec_floor and (prec_floor is None or prec >= prec_floor):
            candidates.append((t, prec, rec))

    if not candidates:
        t = threshold_at_min_recall(y_true, y_prob, min_recall)
        pred = (y_prob >= t).astype(int)
        return {
            "threshold": t,
            "precision": float(precision_score(y_true, pred, zero_division=0)),
            "recall": float(recall_score(y_true, pred, zero_division=0)),
            "policy": "min_recall_only_precision_floor_not_met",
        }

    t, prec, rec = min(candidates, key=lambda x: x[0])
    return {
        "threshold": float(t),
        "precision": float(prec),
        "recall": float(rec),
        "policy": "min_recall_with_precision_floor" if min_precision else "min_recall",
    }


def build_threshold_policy_report(
    y_val: np.ndarray,
    y_test: np.ndarray,
    p_val: np.ndarray,
    p_test: np.ndarray,
    *,
    contact_fractions: tuple[float, ...] = (0.10, 0.20, 0.30),
) -> dict[str, Any]:
    """Build a comprehensive threshold policy report for the champion manifest.

    Evaluates all four documented policies (default_0.5, business_min_recall_validation,
    max_f1_validation, top_decile_validation_score) on both validation and test splits.

    Also computes top-k contact metrics for CRM capacity planning.

    Args:
        y_val: Validation ground-truth labels.
        y_test: Test ground-truth labels.
        p_val: Validation probabilities (calibrated).
        p_test: Test probabilities (calibrated).
        contact_fractions: Fractions of population for top-k contact metrics (default 10%, 20%, 30%).

    Returns:
        dict with:
          - policies: per-policy results (validation + test metrics).
          - recommended_operating_policy: always 'business_min_recall_validation'.
          - operating_threshold: threshold from the business policy.
          - policy_config: the recall/precision targets used.
          - ranking_vs_operating: explanation of dual-score usage.
          - top_k_validation / top_k_test: CRM capacity metrics.
          - why_fn_costly: business rationale for FN-costly design.
          - retention_rationale: summary of the contact policy strategy.
    """
    thr_default = DEFAULT_THRESHOLD
    thr_f1 = best_f1_threshold(y_val, p_val)
    biz = select_threshold_business_policy(y_val, p_val)
    thr_business = biz["threshold"]
    thr_top_decile = float(np.quantile(p_val, 0.90))

    policies: dict[str, Any] = {
        "default_0.5": {
            "threshold": thr_default,
            "role": "reference_baseline",
            "rationale": "Standard probabilistic cutoff; not tuned for telecom FN cost.",
            "validation": evaluate_probs(y_val, p_val, thr_default),
            "test": evaluate_probs(y_test, p_test, thr_default),
        },
        "business_min_recall_validation": {
            "threshold": thr_business,
            "role": "primary_operating_policy",
            "rationale": (
                f"Lowest validation threshold with recall>={MIN_RECALL_CONTACT} "
                f"and precision>={MIN_PRECISION_CONTACT} when feasible. "
                "Missing churners cost more than false alarms in retention."
            ),
            "validation_at_selection": biz,
            "validation": evaluate_probs(y_val, p_val, thr_business),
            "test": evaluate_probs(y_test, p_test, thr_business),
        },
        "max_f1_validation": {
            "threshold": thr_f1,
            "role": "reference_only",
            "rationale": "Balanced F1 on validation — not primary for campaign ops.",
            "validation": evaluate_probs(y_val, p_val, thr_f1),
            "test": evaluate_probs(y_test, p_test, thr_f1),
        },
        "top_decile_validation_score": {
            "threshold": thr_top_decile,
            "role": "contact_budget_proxy",
            "rationale": "Flag top 10% by calibrated score on validation (CRM capacity view).",
            "validation": evaluate_probs(y_val, p_val, thr_top_decile),
            "test": evaluate_probs(y_test, p_test, thr_top_decile),
        },
    }

    return {
        "policies": policies,
        "recommended_operating_policy": "business_min_recall_validation",
        "operating_threshold": thr_business,
        "policy_config": {
            "min_recall": MIN_RECALL_CONTACT,
            "min_precision": MIN_PRECISION_CONTACT,
            "recall_tolerance": RECALL_TOLERANCE,
            "precision_tolerance": PRECISION_TOLERANCE,
        },
        "ranking_vs_operating": {
            "ranking_score": "churn_probability_raw — prioritization and top-k lists",
            "operating_score": "churn_probability_calibrated — CRM thresholds and risk bands",
        },
        "top_k_validation": top_k_contact_metrics(y_val, p_val, contact_fractions),
        "top_k_test": top_k_contact_metrics(y_test, p_test, contact_fractions),
        "why_fn_costly": (
            "In telecom retention, a missed churner exits revenue; "
            "a false alarm wastes a save offer but keeps the subscriber."
        ),
        "retention_rationale": (
            "Contact policy optimizes churn capture (recall) under CRM capacity (top-k / top-decile). "
            "Use raw scores to rank who to contact first; use calibrated scores for tier labels."
        ),
    }
