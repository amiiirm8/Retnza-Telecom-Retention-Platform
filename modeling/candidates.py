"""Model candidate factories and optional library detection.

Defines the ModelFamily (7 model types) and ImbalanceStrategy unions, plus the
factory functions for creating, fitting, tuning, and resampling models.

Pipeline position: consumed by baselines.py and champion.py.
Workflow stage: training.
Key invariants:
  - LogisticRegression always gets StandardScaler via pipeline.
  - class_weight='balanced' is handled differently per family:
      - RF/LightGBM/CatBoost: native class_weight param.
      - HGB/XGBoost: compute_sample_weight used at fit time.
      - LogisticRegression: passed through to sklearn.
  - Resampling (SMOTE/undersample) is only compared on LR for fair comparison.
  - Tuning is RF-only (RandomizedSearchCV, 24 iterations, avg_precision scoring).
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from modeling.config import N_CV_FOLDS, N_RF_TUNING_ITER, RANDOM_STATE

ModelFamily = Literal[
    "logistic_regression",
    "random_forest",
    "hist_gradient_boosting",
    "lightgbm",
    "xgboost",
    "catboost",
]
"""Supported model families for churn prediction.

Three core families always available (sklearn-native):
  - logistic_regression
  - random_forest
  - hist_gradient_boosting

Three optional boosters, detected at import time:
  - lightgbm
  - xgboost
  - catboost
"""

ImbalanceStrategy = Literal["none", "class_weight", "smote", "undersample"]
"""How class imbalance is handled during training.

  - none: No special handling.
  - class_weight: Pass class_weight='balanced' or use sample_weight.
  - smote: Synthetic Minority Over-sampling (LR only, for fair comparison).
  - undersample: Random undersampling of majority class (LR only).
"""


def available_model_families() -> list[str]:
    """Return list of model families that are installed and eligible for benchmarking.

    Three sklearn-native families are always included. Optional boosters (lightgbm,
    xgboost, catboost) are detected via lazy import; silently skipped if not installed.

    Returns:
        List of ModelFamily name strings available in the current environment.

    Side effects: None (imports are lazy and caught by ImportError).
    """
    families: list[str] = [
        "logistic_regression",
        "random_forest",
        "hist_gradient_boosting",
    ]
    try:
        import lightgbm  # noqa: F401

        families.append("lightgbm")
    except ImportError:
        pass
    try:
        import xgboost  # noqa: F401

        families.append("xgboost")
    except ImportError:
        pass
    try:
        import catboost  # noqa: F401

        families.append("catboost")
    except ImportError:
        pass
    return families


def _make_estimator(family: ModelFamily, class_weight: bool) -> Any:
    """Create an untrained estimator for the given model family.

    Args:
        family: The model family name.
        class_weight: If True, configure the estimator to use balanced class weighting
            (either via native class_weight param or via sample_weight expectation).

    Returns:
        An untrained sklearn-compatible estimator.

    Raises:
        ValueError: If family is not recognized.

    Notes:
        HGB does not support class_weight natively; balanced sample_weight is applied
        at fit time in fit_model(). XGBoost uses scale_pos_weight and also receives
        sample_weight at fit time for finer-grained balancing.
    """
    cw = "balanced" if class_weight else None
    if family == "logistic_regression":
        return LogisticRegression(max_iter=2500, class_weight=cw, random_state=RANDOM_STATE)
    if family == "random_forest":
        return RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=20,
            class_weight=cw,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_depth=6,
            learning_rate=0.08,
            max_iter=250,
            random_state=RANDOM_STATE,
        )
    if family == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            class_weight=cw,
            random_state=RANDOM_STATE,
            verbose=-1,
            n_jobs=-1,
        )
    if family == "xgboost":
        from xgboost import XGBClassifier

        if class_weight:
            pass  # handled via sample_weight at fit time for xgb
        return XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            scale_pos_weight=2.7 if class_weight else 1.0,
            random_state=RANDOM_STATE,
            eval_metric="logloss",
            verbosity=0,
            n_jobs=-1,
        )
    if family == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            iterations=300,
            depth=6,
            learning_rate=0.05,
            auto_class_weights="Balanced" if class_weight else None,
            random_seed=RANDOM_STATE,
            verbose=False,
        )
    raise ValueError(family)


def fit_model(
    family: ModelFamily,
    X: np.ndarray,
    y: np.ndarray,
    *,
    class_weight: bool = False,
) -> tuple[Any, str]:
    """Fit an estimator for the given family on training data.

    Special handling per family:
      - LogisticRegression: wrapped in Pipeline(StandardScaler → LR). LR without scaling
        can fail to converge on mixed-scale features.
      - HGB/XGBoost with class_weight: uses compute_sample_weight because these families
        do not support native class_weight='balanced'.
      - RF/LightGBM/CatBoost: native class_weight param is set in _make_estimator.

    Args:
        family: The model family name.
        X: Training feature matrix.
        y: Training labels.
        class_weight: If True, apply balanced class weighting.

    Returns:
        Tuple of (fitted_model, fit_note). fit_note is a short string describing
        how class imbalance was handled (for logging/reporting).

    Side effects: Modifies the estimator's internal state via .fit().
    """
    est = _make_estimator(family, class_weight)

    if family == "logistic_regression":
        pipe = Pipeline([("scaler", StandardScaler()), ("clf", est)])
        pipe.fit(X, y)
        return pipe, "scaled_logistic"

    if family == "hist_gradient_boosting" and class_weight:
        sw = compute_sample_weight(class_weight="balanced", y=y)
        est.fit(X, y, sample_weight=sw)
        return est, "sample_weight_balanced"

    if family == "xgboost" and class_weight:
        sw = compute_sample_weight(class_weight="balanced", y=y)
        est.fit(X, y, sample_weight=sw)
        return est, "sample_weight_balanced"

    est.fit(X, y)
    note = "class_weight_balanced" if class_weight and family in ("random_forest", "lightgbm", "catboost") else "none"
    return est, note


def predict_proba(model: Any, X: np.ndarray) -> np.ndarray:
    """Predict positive-class probability from any fitted model.

    Extracts the second column (index 1) from predict_proba output and ensures
    float64 dtype for downstream numerical stability.

    Args:
        model: A fitted sklearn-compatible model with .predict_proba.
        X: Feature matrix.

    Returns:
        1-D array of positive-class probabilities.

    Side effects: None.
    """
    return np.asarray(model.predict_proba(X)[:, 1], dtype=np.float64)


def tune_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    n_iter: int = N_RF_TUNING_ITER,
) -> tuple[Any, dict[str, Any]]:
    """Hyperparameter tuning for Random Forest via RandomizedSearchCV.

    Tuning is RF-only by design: RF is the core default champion candidate and
    benefits most from tuning given its many hyperparameters. Other families use
    fixed sensible defaults.

    Args:
        X_train: Training feature matrix.
        y_train: Training labels.
        n_iter: Number of random search iterations (default 24, configured in N_RF_TUNING_ITER).

    Returns:
        Tuple of (best_estimator, tuning_info_dict) where tuning_info includes
        best_params, best_cv_pr_auc, and n_iter.

    Side effects: Fits RandomizedSearchCV with 3-fold CV on X_train, y_train.
    """
    param_dist = {
        "n_estimators": [250, 300, 400, 500],
        "max_depth": [8, 10, 12, 14, 16],
        "min_samples_leaf": [8, 12, 16, 20, 30],
        "min_samples_split": [2, 5, 10],
        "max_features": ["sqrt", "log2", 0.4, 0.6],
    }
    base = RandomForestClassifier(
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    search = RandomizedSearchCV(
        base,
        param_distributions=param_dist,
        n_iter=n_iter,
        scoring="average_precision",
        cv=N_CV_FOLDS,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        refit=True,
    )
    search.fit(X_train, y_train)
    return search.best_estimator_, {
        "best_params": search.best_params_,
        "best_cv_pr_auc": float(search.best_score_),
        "n_iter": n_iter,
    }


def resample_train(
    X: np.ndarray,
    y: np.ndarray,
    strategy: ImbalanceStrategy,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply an explicit resampling strategy to the training set.

    Only used for logistic_regression baselines where we want to compare
    algorithmic imbalance handling (class_weight) against explicit resampling.

    Args:
        X: Training feature matrix.
        y: Training labels.
        strategy: 'smote' or 'undersample'. Any other value returns (X, y) unchanged.

    Returns:
        Tuple of (resampled_X, resampled_y).

    Side effects: Fits a SMOTE or RandomUnderSampler (with RANDOM_STATE for reproducibility).
    """
    if strategy == "smote":
        from imblearn.over_sampling import SMOTE

        return SMOTE(random_state=RANDOM_STATE).fit_resample(X, y)
    if strategy == "undersample":
        from imblearn.under_sampling import RandomUnderSampler

        return RandomUnderSampler(random_state=RANDOM_STATE).fit_resample(X, y)
    return X, y
