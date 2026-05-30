"""Production scoring contract — raw ranking + calibrated risk communication.

This module is the sole entry point for production inference. It provides four
levels of scoring:

  1. predict_raw_proba(bundle, X) — base model raw probability (ranking layer).
     Use for PR-AUC monitoring, prioritisation, top-k contact lists.
  2. calibrate_raw_proba(bundle, p_raw) — calibrator applied to raw probabilities.
     Never accepts feature matrix X — calibration is a 1-D transform on p_raw.
  3. predict_calibrated_proba(bundle, X) — full pipeline: features → raw → calibrated.
     Use for CRM risk bands and executive reporting.
  4. score_subscriber_row(bundle, X_row) — single-row scoring for API / CRM microservice.
     Returns raw prob, calibrated prob, and risk tier.

Pipeline position: consumed by production scoring service, champion.py (for
  training-time evaluations), and explainability.py (for SHAP population export).
Workflow stage: inference (primarily) + training (secondarily for post-hoc evaluation).
Key invariants:
  - calibrate_raw_proba NEVER receives the feature matrix X — only p_raw.
  - All functions validate the bundle against the current feature schema via
    validate_champion_bundle(strict=False) for safety.
  - Risk tier assignment uses the calibrated probability, not raw.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from modeling.config import RISK_TIER_THRESHOLDS
from modeling.governance import validate_champion_bundle


def predict_raw_proba(bundle: dict[str, Any], X: np.ndarray) -> np.ndarray:
    """Base model positive-class probability for ranking and prioritisation.

    This is the "ranking layer" — use raw probabilities for:
      - PR-AUC / ROC-AUC monitoring (threshold-independent ranking power).
      - Top-k contact list construction (CRM capacity).
      - Any scenario where relative ordering matters more than absolute values.

    Why raw scores for ranking:
        Calibration adjusts absolute probability values to be truthful (Brier-optimal)
        but may slightly distort ranking. For prioritisation, raw scores from the
        base model preserve the ranking that the model was directly optimised for.

    Args:
        bundle: Loaded champion bundle dict (must contain 'base_model').
        X: Feature matrix.

    Returns:
        1-D array of raw positive-class probabilities (float64).

    Side effects: Validates the bundle (non-strict) on every call.
    """
    validate_champion_bundle(bundle, strict=False)
    return np.asarray(bundle["base_model"].predict_proba(X)[:, 1], dtype=np.float64)


def calibrate_raw_proba(bundle: dict[str, Any], p_raw: np.ndarray) -> np.ndarray:
    """Transform raw probabilities through the validation-fit calibrator.

    Never pass feature matrix X to this function — the calibrator is a univariate
    mapping f(p_raw) that should not re-learn feature interactions. Validates that
    the bundle has a calibrator with a calibrate_probabilities method.

    Args:
        bundle: Loaded champion bundle dict (must contain 'calibrator').
        p_raw: Raw positive-class probabilities from the base model.

    Returns:
        1-D array of calibrated probabilities (float64, clipped to [1e-6, 1-1e-6]).

    Raises:
        TypeError: If the bundle's calibrator does not expose calibrate_probabilities.

    Side effects: None (pure computation).
    """
    p_raw = np.clip(np.asarray(p_raw, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    wrap = bundle["calibrator"]
    if hasattr(wrap, "calibrate_probabilities"):
        return wrap.calibrate_probabilities(p_raw)
    raise TypeError(
        "Bundle calibrator must expose calibrate_probabilities(p_raw). "
        "Retrain champion on task4-v2 feature schema."
    )


def predict_calibrated_proba(bundle: dict[str, Any], X: np.ndarray) -> np.ndarray:
    """Full pipeline: feature matrix → base model → calibrator(p_raw).

    Convenience wrapper for the common case where you need calibrated probabilities
    directly from features.

    Args:
        bundle: Loaded champion bundle dict.
        X: Feature matrix.

    Returns:
        1-D array of calibrated probabilities.
    """
    return calibrate_raw_proba(bundle, predict_raw_proba(bundle, X))


def assign_risk_tier(p_cal: float, thresholds: dict[str, float] | None = None) -> str:
    """Map a calibrated probability to a telecom risk band.

    Tiers are defined from highest to lowest threshold:
      - Very High: >= 0.65
      - High:     >= 0.30
      - Medium:   >= 0.15
      - Low:      < 0.15

    These thresholds are applied to CALIBRATED probabilities only. Raw scores may
    have a very different distribution and should not be tiered with these bands.

    Args:
        p_cal: Calibrated churn probability (should be in [0, 1]).
        thresholds: dict mapping tier name -> lower bound. Defaults to RISK_TIER_THRESHOLDS.

    Returns:
        Risk tier string: 'Very High', 'High', 'Medium', or 'Low'.
    """
    thresholds = thresholds or RISK_TIER_THRESHOLDS
    for tier, bound in sorted(thresholds.items(), key=lambda x: -x[1]):
        if p_cal >= bound:
            return tier
    return "Low"


def score_subscriber_row(
    bundle: dict[str, Any],
    X_row: np.ndarray,
) -> dict[str, float]:
    """Single-row scoring for API / CRM microservice consumption.

    Convenience wrapper that handles the 1-D → 2-D reshape and returns both
    raw and calibrated probabilities plus the risk tier in a single dict.

    Args:
        bundle: Loaded champion bundle dict.
        X_row: Single subscriber feature vector (1-D array).

    Returns:
        dict with keys:
          - 'churn_probability_raw': float
          - 'churn_probability_calibrated': float
          - 'risk_tier': str
    """
    x = np.asarray(X_row, dtype=np.float64).reshape(1, -1)
    p_raw = float(predict_raw_proba(bundle, x)[0])
    p_cal = float(calibrate_raw_proba(bundle, np.array([p_raw]))[0])
    return {
        "churn_probability_raw": p_raw,
        "churn_probability_calibrated": p_cal,
        "risk_tier": assign_risk_tier(
            p_cal,
            bundle.get("risk_band_thresholds"),
        ),
    }
