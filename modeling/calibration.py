"""Post-hoc probability calibration (validation-only fit on p_raw).

Calibration is fit exclusively on the raw positive-class probabilities from the
base model on the validation split. The feature matrix X is never passed to any
calibrator — this ensures calibration corrects only the score distribution shape
without re-learning feature interactions.

Three methods are supported:
  - **none**: Identity (no calibration). Suitable when the base model is already
    well-calibrated (e.g. logistic regression).
  - **sigmoid** (Platt scaling): LogisticRegression on the single raw probability p_raw.
    Low overfit risk; works well for moderately mis-calibrated scores.
  - **isotonic**: IsotonicRegression on p_raw. Higher overfit risk, especially
    with few validation positives (<200). Can model arbitrary monotonic distortions.

Pipeline position: called after champion selection in train_champion() (champion.py).
Workflow stage: training.
Key invariants:
  - Calibrator is fit on validation P_RAW only — never on feature matrix X.
  - Selection prefers sigmoid over isotonic when n_val_positives < 200.
  - Calibration may slightly reduce PR-AUC (ranking power) while improving Brier/ECE
    (truthfulness). This is an explicit documented trade-off.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

CalibrationMethod = Literal["none", "sigmoid", "isotonic"]


class ProbabilityCalibrator(BaseEstimator, ClassifierMixin):
    """Sklearn-compatible wrapper that calibrates raw positive-class probabilities.

    The calibrator is fit via .fit_calibrator(y_val, p_val_raw) and never receives
    the feature matrix X. This is intentional: calibration should correct only the
    score distribution shape, not re-learn feature interactions.

    The class conforms to sklearn's BaseEstimator / ClassifierMixin interface so it
    can be dropped into pipelines or joblib bundles. The standard .fit(X, y) method
    is a no-op; use .fit_calibrator() instead.

    Used in champion.py:train_champion() to wrap the selected base model with the
    best calibration method. The bundled calibrator is then used in scoring.py for
    production inference.

    Args:
        base_estimator: The underlying trained model (must have .predict_proba).
        method: One of 'none', 'sigmoid', 'isotonic'. Controls the calibration
            function family.

    Attributes:
        base_estimator: The underlying model.
        method: The calibration method.
        calibrator_: The fitted calibrator object (None for 'none' method).
    """

    def __init__(
        self,
        base_estimator: Any,
        method: CalibrationMethod = "none",
    ) -> None:
        self.base_estimator = base_estimator
        self.method = method
        self.calibrator_: Any = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ProbabilityCalibrator":
        """No-op: calibration is never fit on the feature matrix.

        This method exists for sklearn classifier interface compatibility only.
        Use fit_calibrator() instead.
        """
        return self

    def fit_calibrator(self, y_val: np.ndarray, p_val_raw: np.ndarray) -> "ProbabilityCalibrator":
        """Fit the calibration mapping on validation probabilities only.

        Args:
            y_val: Ground-truth labels for the validation split.
            p_val_raw: Raw positive-class probabilities from base_model on validation.

        Returns:
            self, with self.calibrator_ set.

        Raises:
            ValueError: If self.method is not one of 'none', 'sigmoid', 'isotonic'.

        Side effects: Only modifies self.calibrator_.
        """
        p_val_raw = np.clip(np.asarray(p_val_raw, dtype=np.float64), 1e-6, 1 - 1e-6)
        y_val = np.asarray(y_val)
        if self.method == "none":
            self.calibrator_ = None
        elif self.method == "sigmoid":
            lr = LogisticRegression(max_iter=1000)
            lr.fit(p_val_raw.reshape(-1, 1), y_val)
            self.calibrator_ = lr
        elif self.method == "isotonic":
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            # Clip to [0, 1] guarantees probability domain compliance
            iso.fit(p_val_raw, y_val)
            self.calibrator_ = iso
        else:
            raise ValueError(self.method)
        return self

    def calibrate_probabilities(self, p_raw: np.ndarray) -> np.ndarray:
        """Transform raw probabilities to calibrated probabilities.

        Args:
            p_raw: Raw positive-class probabilities.

        Returns:
            Calibrated probabilities in [0, 1].

        Side effects: None.
        """
        return self._apply(np.asarray(p_raw, dtype=np.float64))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Full pipeline: base_model → calibrator.

        Args:
            X: Feature matrix.

        Returns:
            Array of shape (n_samples, 2) with calibrated probabilities for both classes.
        """
        p_raw = self.base_estimator.predict_proba(X)[:, 1]
        p_cal = self.calibrate_probabilities(p_raw)
        return np.column_stack([1 - p_cal, p_cal])

    def _apply(self, p: np.ndarray) -> np.ndarray:
        """Internal: apply the fitted calibrator to a probability array.

        Args:
            p: Positive-class probability values in [0, 1].

        Returns:
            Calibrated probability values.
        """
        p = np.clip(p, 1e-6, 1 - 1e-6)
        if self.method == "none" or self.calibrator_ is None:
            return p
        if self.method == "sigmoid":
            return self.calibrator_.predict_proba(p.reshape(-1, 1))[:, 1]
        return self.calibrator_.predict(p)


def compare_calibration_methods(
    base_model: Any,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    methods: tuple[CalibrationMethod, ...] = ("none", "sigmoid", "isotonic"),
) -> dict[str, Any]:
    """Compare all three calibration methods on validation and test.

    Each calibrator is fit on validation raw probabilities only. The same
    calibrator is then applied to both validation and test probabilities
    (the test probabilities come from base_model.predict_proba(X_test) and
    are transformed through the validation-fitted calibrator).

    Args:
        base_model: The trained base model (must have .predict_proba).
        X_val: Validation feature matrix (used only to get base_model raw probs).
        y_val: Validation ground-truth labels.
        X_test: Test feature matrix (used only to get base_model raw probs).
        y_test: Test ground-truth labels.
        methods: Which calibration methods to compare. Default: all three.

    Returns:
        dict with:
          - 'comparison': per-method validation/test metrics at threshold 0.5.
          - 'models': fitted ProbabilityCalibrator instances keyed by method name.
          - 'p_val_raw': the raw validation probabilities (for reference/plotting).

    Side effects: None.

    Notes:
        Validation metrics show calibration quality on the fit distribution.
        Test metrics show generalization. Overfit risk is heuristic: isotonic > sigmoid > none.
    """
    from modeling.evaluation import evaluate_probs

    p_val_raw = base_model.predict_proba(X_val)[:, 1]
    results: dict[str, Any] = {}
    models: dict[str, ProbabilityCalibrator] = {}

    for method in methods:
        wrap = ProbabilityCalibrator(base_model, method=method)
        wrap.fit_calibrator(y_val, p_val_raw)
        models[method] = wrap
        p_val = wrap.calibrate_probabilities(p_val_raw)
        p_test_raw = base_model.predict_proba(X_test)[:, 1]
        p_test = wrap.calibrate_probabilities(p_test_raw)
        results[method] = {
            "validation": evaluate_probs(y_val, p_val, threshold=0.5),
            "test": evaluate_probs(y_test, p_test, threshold=0.5),
            "overfit_risk": (
                "high" if method == "isotonic" else "medium" if method == "sigmoid" else "none"
            ),
        }

    return {"comparison": results, "models": models, "p_val_raw": p_val_raw}


def select_calibration_method(
    comparison: dict[str, Any],
    pr_tolerance: float = 0.01,
    *,
    n_val_positives: int | None = None,
) -> tuple[CalibrationMethod, dict[str, Any]]:
    """Select the best calibration method within a PR-AUC tolerance band.

    Selection logic:
      1. Compute the validation PR-AUC ceiling across all methods.
      2. Keep methods whose validation PR-AUC is within `pr_tolerance` of the ceiling.
      3. If isotonic overfit risk is high (n_val_positives < 200), exclude isotonic
         from the candidate pool (but keep it if sigmoid is not available).
      4. Among remaining candidates, pick the one with the lowest validation Brier score
         (tie-break by lowest ECE).

    This explicitly documents the trade-off: calibration improves truthfulness (Brier/ECE)
    but may slightly hurt ranking (PR-AUC).

    Args:
        comparison: The dict returned by compare_calibration_methods().
        pr_tolerance: Absolute PR-AUC tolerance band (default 0.01).
        n_val_positives: Number of positive examples in the validation split. Used to
            estimate isotonic overfit risk. If None, isotonic risk defaults to 'medium'.

    Returns:
        Tuple of (chosen_method: CalibrationMethod, rationale: dict). The rationale
        contains per-method metrics, the candidate pool, and the tradeoff note.

    Side effects: None.

    Why calibration is fit only on validation probabilities:
        The calibrator is a univariate function p_raw -> p_cal. Fitting on feature
        matrix X would allow the calibrator to learn feature interactions, defeating
        the purpose of calibration (which should only correct the score distribution
        shape). Validation raw probabilities provide a held-out estimate of the
        base model's score distribution without test-set leakage.
    """
    comp = comparison["comparison"]
    val_pr = {m: comp[m]["validation"]["pr_auc"] for m in comp}
    val_brier = {m: comp[m]["validation"]["brier_score"] for m in comp}
    val_ece = {m: comp[m]["validation"]["ece"] for m in comp}
    ceiling = max(val_pr.values())
    candidates = [m for m in val_pr if val_pr[m] >= ceiling - pr_tolerance]

    isotonic_risk = "high" if n_val_positives is not None and n_val_positives < 200 else "medium"
    if isotonic_risk == "high" and "sigmoid" in candidates:
        pool = [m for m in candidates if m != "isotonic"] or candidates
    else:
        pool = candidates

    chosen = min(pool, key=lambda m: (val_brier[m], val_ece[m]))  # type: ignore[return-value]

    rationale = {
        "chosen": chosen,
        "candidates_in_band": candidates,
        "val_pr_auc_ceiling": ceiling,
        "pr_tolerance": pr_tolerance,
        "isotonic_overfit_risk": isotonic_risk,
        "tradeoff_note": (
            "Calibration fit on validation p_raw only. "
            "May reduce PR-AUC slightly while improving Brier/ECE for CRM risk bands."
        ),
        "per_method": {
            m: {
                "val_pr_auc": val_pr[m],
                "val_brier": val_brier[m],
                "val_ece": val_ece[m],
                "test_pr_auc": comp[m]["test"]["pr_auc"],
                "test_brier": comp[m]["test"]["brier_score"],
                "overfit_risk": comp[m].get("overfit_risk"),
            }
            for m in comp
        },
    }
    return chosen, rationale


def save_calibration_summary(
    comparison: dict[str, Any],
    selection_rationale: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Persist the calibration comparison and selection rationale to disk.

    Args:
        comparison: The dict returned by compare_calibration_methods().
        selection_rationale: The dict returned by select_calibration_method().
        path: Output JSON path. Defaults to OUTPUT_CHAMPION / 'calibration_summary.json'.

    Returns:
        Path to the written file.

    Side effects: Creates parent directory if needed and writes JSON.
    """
    from modeling.config import OUTPUT_CHAMPION

    path = path or OUTPUT_CHAMPION / "calibration_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "comparison": comparison["comparison"],
        "selection": selection_rationale,
        "fit_policy": "validation raw probabilities only — never feature matrix",
    }
    path.write_text(
        __import__("json").dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return path
