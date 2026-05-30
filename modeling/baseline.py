"""Task 5 — configurable baseline benchmarking engine.

Systematically trains every available ModelFamily × imbalance strategy and
records ranking, threshold-dependent, and top-k metrics on the validation and
test splits. Produces the baseline_decisions block used downstream for:

  - **ranking_propensity**: Best test PR-AUC among default-threshold runs
    (identifies the strongest ranker for prioritisation).
  - **campaign_contact**: Random Forest with class_weight +
    business_min_recall_validation threshold (identifies the operating-point
    champion for CRM contact lists).

Pipeline position: entry point (Task 5), called before champion selection.
Workflow stage: training + reporting.
Key invariants:
  - Every experiment uses the SAME canonical split (load_feature_splits).
  - Thresholds are resolved on validation probabilities only; test is purely
    evaluative.
  - Imbalance strategies (smote / undersample) compared fairly on LR only,
    because other families handle imbalance internally via class_weight.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from modeling.candidates import (
    ImbalanceStrategy,
    ModelFamily,
    available_model_families,
    fit_model,
    predict_proba,
    resample_train,
)
from modeling.config import (
    MIN_PRECISION_CONTACT,
    MIN_RECALL_CONTACT,
    MODELING_SCHEMA_VERSION,
    OUTPUT_BASELINES,
    RANDOM_STATE,
)
from modeling.evaluation import evaluate_probs, ranking_metrics
from modeling.splits import load_feature_splits


@dataclass
class BaselineExperiment:
    """A single baseline run: one model family × one imbalance strategy × one threshold policy.

    Attributes:
        model: The model family to train.
        imbalance_strategy: How class imbalance is handled ('none', 'class_weight', 'smote',
            'undersample'). Note that smote/undersample only apply to logistic_regression.
        use_class_weight: Whether to pass class_weight='balanced' during fit. Overridden to
            False when an explicit resampling strategy is used.
        threshold_policy_key: Which policy to use for selecting the operating threshold.
            'default_0.5' is used for ranking comparison; 'business_min_recall_validation'
            targets recall >= MIN_RECALL_CONTACT on validation.
    """
    model: ModelFamily
    imbalance_strategy: ImbalanceStrategy
    use_class_weight: bool
    threshold_policy_key: str = "business_min_recall_validation"


@dataclass
class BaselineConfig:
    """Collection of BaselineExperiments describing the benchmarking grid.

    Attributes:
        experiments: List of experiments to run.
        include_optional_boosters: If True, scans for optional booster libraries
            (lightgbm, xgboost, catboost) and adds them to the experiment grid.
            Default True for thorough benchmarking.

    The default grid includes:
      - Every family × (none, class_weight) × (default_0.5, business_min_recall_validation)
      - logistic_regression × (smote, undersample) for explicit resampling comparison.
    """
    experiments: list[BaselineExperiment] = field(default_factory=list)
    include_optional_boosters: bool = True

    @classmethod
    def default(cls) -> "BaselineConfig":
        """Build the standard benchmarking grid.

        Three core families always present;
        optional boosters (lightgbm, xgboost, catboost) added when installed.

        Returns:
            BaselineConfig with the full experiment grid.
        """
        exps: list[BaselineExperiment] = []
        families: list[ModelFamily] = [
            "logistic_regression",
            "random_forest",
            "hist_gradient_boosting",
        ]
        if cls().include_optional_boosters:
            for f in available_model_families():
                if f not in families:
                    families.append(f)  # type: ignore[arg-type]

        for name in families:
            exps.append(BaselineExperiment(name, "none", False, "default_0.5"))
            exps.append(BaselineExperiment(name, "class_weight", True, "default_0.5"))
            exps.append(
                BaselineExperiment(name, "class_weight", True, "business_min_recall_validation")
            )
        exps.append(BaselineExperiment("logistic_regression", "smote", False))
        exps.append(BaselineExperiment("logistic_regression", "undersample", False))
        return cls(experiments=exps)


def _resolve_threshold(
    policy_key: str,
    y_val: np.ndarray,
    p_val: np.ndarray,
) -> tuple[float, dict[str, Any]]:
    """Map a policy key to a (threshold_value, metadata) pair.

    Resolution is done exclusively on validation probabilities (y_val, p_val)
    to avoid any test-set leakage into threshold decisions.

    Args:
        policy_key: One of 'default_0.5', 'f1_max_reference', or a key handled by
            select_threshold_business_policy (e.g. 'business_min_recall_validation').
        y_val: Ground-truth labels for the validation split.
        p_val: Raw positive-class probabilities on the validation split.

    Returns:
        Tuple of (threshold_float, info_dict). The info dict includes the policy name,
        rationale, and validation metrics at the chosen threshold.

    Side effects: None.
    """
    from modeling.thresholds import (
        best_f1_threshold,
        select_threshold_business_policy,
    )

    if policy_key == "default_0.5":
        return 0.5, {
            "threshold_policy": "default_0.5",
            "threshold_rationale": "Default 0.5 — ranking comparison only",
        }
    if policy_key == "f1_max_reference":
        t = best_f1_threshold(y_val, p_val)
        return t, {"threshold_policy": policy_key, "threshold_rationale": "Max F1 reference"}
    sel = select_threshold_business_policy(y_val, p_val)
    return float(sel["threshold"]), {
        "threshold_policy": policy_key,
        "threshold_rationale": sel.get("policy", ""),
        "validation_at_threshold": sel,
    }


def run_baselines(config: BaselineConfig | None = None) -> dict[str, Any]:
    """Run the full baseline experiment grid and produce the baseline decisions report.

    For each experiment in the config:
      1. Load the canonical split (train/val/test).
      2. Optionally resample the training set (smote / undersample). Resampling is
         only applied for logistic_regression to enable a fair comparison — other
         families handle imbalance via class_weight internally.
      3. Fit the model on the (possibly resampled) training data.
      4. Predict raw probabilities on val and test.
      5. Resolve the operating threshold policy on validation probabilities only.
      6. Compute ranking metrics, threshold-dependent metrics, and top-k contact metrics.
      7. Collect results into a list of result dicts.

    After all experiments, two key decisions are derived:
      - **ranking_propensity**: the model with best test PR-AUC among default_0.5 runs
        (identifies the strongest ranker for prioritization).
      - **campaign_contact**: Random Forest with class_weight + business policy threshold
        (the default operating-point champion for CRM contact lists).

    Args:
        config: BaselineConfig describing the experiment grid. If None, uses
            BaselineConfig.default() which covers all families × strategies.

    Returns:
        A dict with schema_version, all experiment results, baseline_decisions, and
        telecom_notes. The full dict is saved via save_baseline_report().

    Side effects: None (pure computation; no files written).

    Failure modes:
      - If no families are installed, results will be empty and ranking_best falls
        back to the first experiment (which may have pr_auc=-1).
    """
    config = config or BaselineConfig.default()
    split = load_feature_splits()
    results: list[dict[str, Any]] = []

    for exp in config.experiments:
        if exp.model not in available_model_families():
            continue

        X_tr, y_tr = split.X_train.copy(), split.y_train.copy()
        use_cw = exp.use_class_weight

        if exp.imbalance_strategy in ("smote", "undersample"):
            if exp.model != "logistic_regression":
                continue  # resampling only compared fairly on LR
            X_tr, y_tr = resample_train(X_tr, y_tr, exp.imbalance_strategy)
            use_cw = False  # resampled data is already balanced; disable class_weight

        model, fit_note = fit_model(exp.model, X_tr, y_tr, class_weight=use_cw)
        p_val = predict_proba(model, split.X_val)
        p_test = predict_proba(model, split.X_test)

        if exp.threshold_policy_key in ("default_0.5", "f1_max_reference"):
            thr, thr_info = _resolve_threshold(exp.threshold_policy_key, split.y_val, p_val)
        else:
            thr, thr_info = _resolve_threshold(
                exp.threshold_policy_key or "business_min_recall_validation",
                split.y_val,
                p_val,
            )

        row: dict[str, Any] = {
            "model": exp.model,
            "imbalance_strategy": exp.imbalance_strategy,
            "class_weight_in_fit": use_cw,
            "imbalance_fit_note": fit_note,
            "n_train_fit": int(len(y_tr)),
            **thr_info,
            "threshold": thr,
            "validation_ranking": ranking_metrics(split.y_val, p_val),
            "test_ranking": ranking_metrics(split.y_test, p_test),
            "validation": evaluate_probs(split.y_val, p_val, thr),
            "test": evaluate_probs(split.y_test, p_test, thr),
        }
        results.append(row)

    # Derive ranking_best: prefer default_0.5 + no resampling rows for fair comparison;
    # fall back to any default_0.5 row, then any row at all.
    ranking_rows = [
        r
        for r in results
        if r.get("threshold_policy") == "default_0.5" and r["imbalance_strategy"] == "none"
    ]
    if not ranking_rows:
        ranking_rows = [r for r in results if r.get("threshold_policy") == "default_0.5"]
    if not ranking_rows:
        ranking_rows = results
    ranking_best = max(ranking_rows, key=lambda r: r["test_ranking"]["pr_auc"])

    # campaign_contact: default to RF + class_weight + business policy.
    # This is the default operating champion for CRM. If not found, falls to results[0].
    rf_contact = next(
        (
            r
            for r in results
            if r["model"] == "random_forest"
            and r["imbalance_strategy"] == "class_weight"
            and "business" in r.get("threshold_policy", "")
        ),
        results[0],
    )

    return {
        "schema_version": MODELING_SCHEMA_VERSION,
        "task": "baseline_benchmark",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_state": RANDOM_STATE,
        "split": split.meta,
        "n_features": len(split.feature_columns),
        "available_families": available_model_families(),
        "experiments_run": len(results),
        "results": results,
        "baseline_decisions": {
            "ranking_propensity": {
                "model": ranking_best["model"],
                "test_pr_auc": ranking_best["test_ranking"]["pr_auc"],
                "rationale": "Best test PR-AUC among default-threshold ranking runs.",
            },
            "campaign_contact": {
                "model": rf_contact["model"],
                "test_recall": rf_contact["test"]["recall"],
                "test_precision": rf_contact["test"]["precision"],
                "threshold": rf_contact["threshold"],
                "rationale": (
                    f"Weighted model + validation threshold recall>={MIN_RECALL_CONTACT} "
                    f"(precision floor {MIN_PRECISION_CONTACT} when feasible)."
                ),
            },
            "use_case_separation": {
                "raw_score": "Use predict_proba for ranking / top-k contact",
                "calibrated_score": "Use champion calibrated score for risk bands",
            },
        },
        "telecom_notes": {
            "prepaid_effect": "Check is_prepaid / prepaid_* flags in SHAP and baselines",
            "ecosystem": "rubika_user_flag, ewano_user_flag, hamrahman_user_flag in feature set",
            "legacy_2g": "is_data_capable separates structural N/A from true non-adoption",
        },
    }


def run_all_baselines() -> dict[str, Any]:
    """Backward-compatible alias for run_baselines().

    Kept for any notebook / script that imported this name before the rename.
    """
    return run_baselines()


def save_baseline_report(report: dict[str, Any]) -> Path:
    """Persist the full baseline report to outputs/baselines/baseline_results.json.

    Args:
        report: The dict returned by run_baselines().

    Returns:
        Path to the written JSON file.

    Side effects: Creates the OUTPUT_BASELINES directory if needed and writes JSON.
    """
    OUTPUT_BASELINES.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_BASELINES / "baseline_results.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
