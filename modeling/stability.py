"""Cross-validated stability analysis for champion selection (train+val pool only).

Repeated stratified K-fold cross-validation on the canonical train+val pool.
The test split is never used in stability CV — it is held out for final evaluation only.

Why stability CV uses the train+val pool:
  The canonical split reserves a 15% test set for final evaluation. Running CV only on
  the training split (70% of data) would leave 15% unused and reduce the reliability
  of CV estimates. Pooling train+val (85% of data) gives more robust fold-level
  estimates while preserving the test split as a completely unseen final holdout.

Pipeline position: called by train_champion() in champion.py before candidate scoring.
Workflow stage: training (provides CV mean/std for champion selection).
Key invariants:
  - Test split is NEVER used (held out via holdout_test=True).
  - FE thresholds (monthly_spend_q75, lifetime_arpu_q75) are re-fit per fold
    on the fold's training subset (simulates deployment scenario).
  - Multiple seeds (42, 123, 456) detect seed-sensitivity.
  - Results are summarised as mean ± std per metric per family.
  - High std flags (>0.03) are stored in stability_flags for the selection rationale.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from feature_engineering.builders import (
    build_features,
    fit_lifetime_arpu_q75,
    fit_monthly_spend_q75,
    get_model_feature_columns,
)
from modeling.candidates import available_model_families, fit_model, predict_proba
from modeling.config import (
    CLEANED_PATH,
    OUTPUT_CHAMPION,
    STABILITY_CV_FOLDS,
    STABILITY_CV_SEEDS,
)
from modeling.evaluation import evaluate_probs, ranking_metrics
from modeling.splits import create_stratified_splits


_METRIC_KEYS = (
    "roc_auc",
    "pr_auc",
    "brier_score",
    "ece",
    "precision",
    "recall",
    "f1",
)


def _aggregate_fold_metrics(fold_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Aggregate fold-level metrics into mean ± std ± min ± max per metric.

    Args:
        fold_rows: List of metric dicts, one per (seed, fold) combination.

    Returns:
        dict mapping metric key -> {'mean', 'std', 'min', 'max', 'n_folds'}.
        Returns empty dict if fold_rows is empty.
    """
    if not fold_rows:
        return {}
    out: dict[str, dict[str, float]] = {}
    for key in _METRIC_KEYS:
        if key not in fold_rows[0]:
            continue
        vals = [float(r[key]) for r in fold_rows]
        out[key] = {
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "n_folds": len(vals),
        }
    return out


def run_cv_stability(
    *,
    families: list[str] | None = None,
    n_splits: int = STABILITY_CV_FOLDS,
    seeds: tuple[int, ...] = STABILITY_CV_SEEDS,
    holdout_test: bool = True,
) -> dict[str, Any]:
    """Run repeated stratified K-fold CV on the canonical train+val pool (test held out).

    For each repetition (seeds 42, 123, 456):
      - Stratified K-fold splitting on the train+val pool.
      - Per fold: re-fit FE thresholds on fold's training subset, build features,
        train each candidate family, evaluate on fold's validation subset.
      - Collect metrics (PR-AUC, ROC-AUC, Brier, ECE, precision, recall, F1).

    After all folds, aggregate per-family metrics and flag high-variance winners.

    Why CV stability is run before candidate scoring:
        The CV stability results feed into the champion selection process. If a
        family has high PR-AUC std across folds (>0.03), it is flagged as unstable
        and the selection logic may prefer a simpler model even if its mean PR-AUC
        is slightly lower.

    Args:
        families: List of family names to evaluate. If None, uses all available families.
        n_splits: Number of CV folds per seed (default 5).
        seeds: Tuple of random seeds for repeated CV (default (42, 123, 456)).
        holdout_test: If True (default), explicitly documents that test is excluded.

    Returns:
        dict with:
          - by_family: per-family aggregated metrics (mean, std, min, max, n_folds).
          - fold_details: list of per-fold metric dicts (for detailed analysis).
          - stability_flags: list of warning strings for high-variance families.
          - metadata (schema, pool size, etc.).
    """
    df = pd.read_parquet(CLEANED_PATH)
    idx_train, idx_val, idx_test = create_stratified_splits(df)
    pool_idx = np.concatenate([idx_train, idx_val])
    pool = df.iloc[pool_idx].reset_index(drop=True)
    y_pool = pool["churn_binary"].values
    cols = get_model_feature_columns()

    families = families or available_model_families()
    skipped: list[dict[str, str]] = []
    fold_details: list[dict[str, Any]] = []
    by_family: dict[str, list[dict[str, Any]]] = {f: [] for f in families}

    for seed in seeds:
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for fold_id, (tr_rel, va_rel) in enumerate(skf.split(np.zeros(len(pool)), y_pool)):
            train_raw = pool.iloc[tr_rel].reset_index(drop=True)
            val_raw = pool.iloc[va_rel].reset_index(drop=True)
            q_m = fit_monthly_spend_q75(train_raw)
            q_a = fit_lifetime_arpu_q75(train_raw)
            train_fe = build_features(train_raw, monthly_spend_q75=q_m, lifetime_arpu_q75=q_a)
            val_fe = build_features(val_raw, monthly_spend_q75=q_m, lifetime_arpu_q75=q_a)

            X_tr = train_fe[cols].values.astype(np.float64)
            y_tr = train_fe["churn_binary"].values
            X_va = val_fe[cols].values.astype(np.float64)
            y_va = val_fe["churn_binary"].values

            for fam in families:
                if fam not in available_model_families():
                    skipped.append({"family": fam, "reason": "not_installed"})
                    continue
                try:
                    use_cw = fam in (
                        "random_forest",
                        "logistic_regression",
                        "lightgbm",
                        "catboost",
                    )
                    model, _ = fit_model(fam, X_tr, y_tr, class_weight=use_cw)  # type: ignore[arg-type]
                    p_va = predict_proba(model, X_va)
                    rank = ranking_metrics(y_va, p_va)
                    ops = evaluate_probs(y_va, p_va, threshold=0.5)
                    row = {
                        "family": fam,
                        "seed": seed,
                        "fold": fold_id,
                        **rank,
                        "precision": ops["precision"],
                        "recall": ops["recall"],
                        "f1": ops["f1"],
                    }
                    fold_details.append(row)
                    by_family[fam].append(row)
                except Exception as exc:
                    skipped.append({"family": fam, "reason": str(exc)})

    family_summary: dict[str, Any] = {}
    for fam, rows in by_family.items():
        if not rows:
            continue
        family_summary[fam] = _aggregate_fold_metrics(rows)

    # Flag high-variance winners (unstable)
    pr_means = {
        f: family_summary[f]["pr_auc"]["mean"]
        for f in family_summary
        if "pr_auc" in family_summary[f]
    }
    pr_stds = {
        f: family_summary[f]["pr_auc"]["std"]
        for f in family_summary
        if "pr_auc" in family_summary[f]
    }
    stability_flags: list[str] = []
    if pr_means:
        best_f = max(pr_means, key=pr_means.get)  # type: ignore[arg-type]
        if pr_stds.get(best_f, 0) > 0.03:
            stability_flags.append(
                f"{best_f} has high PR-AUC fold std ({pr_stds[best_f]:.4f}) — "
                "may be split-sensitive; prefer simpler model within tolerance."
            )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "repeated_stratified_kfold",
        "n_splits": n_splits,
        "seeds": list(seeds),
        "cv_pool": "canonical_train_plus_val",
        "holdout_test_excluded": holdout_test,
        "n_cv_pool": len(pool),
        "n_holdout_test": len(idx_test) if holdout_test else None,
        "available_families": available_model_families(),
        "families_evaluated": list(family_summary.keys()),
        "skipped": skipped,
        "by_family": family_summary,
        "fold_details": fold_details,
        "stability_flags": stability_flags,
        "metric_keys": [
            "pr_auc",
            "roc_auc",
            "brier_score",
            "ece",
            "precision",
            "recall",
            "f1",
        ],
    }


def run_temporal_proxy_diagnostic(
    *,
    families: list[str] | None = None,
    tenure_split: str = "median",
) -> dict[str, Any]:
    """Secondary temporal-stability diagnostic using tenure as a cohort proxy.

    Why temporal proxy uses tenure:
        The dataset has no observation date / timestamp column. True temporal
        cross-validation (train on older data, test on newer data) is not possible.
        As a weak proxy, we split on sim_tenure_months: train on shorter-tenure
        subscribers, validate on longer-tenure subscribers. This simulates the
        effect of training on a younger subscriber base and evaluating on an older one.

    This is NOT a substitute for true temporal CV. Results should be interpreted
    as heuristic only.

    Args:
        families: List of family names to evaluate. If None, uses all available families.
        tenure_split: 'median' (default) splits at the median tenure, or a float
            quantile like 0.33 for a 33/67 split.

    Returns:
        dict with feasibility flag, limitations note, per-family ranking metrics,
        and churn rates for both tenure cohorts.
    """
    df = pd.read_parquet(CLEANED_PATH)
    if "sim_tenure_months" not in df.columns:
        return {
            "feasible": False,
            "reason": "sim_tenure_months missing — temporal proxy unavailable",
        }

    cutoff = float(df["sim_tenure_months"].median()) if tenure_split == "median" else float(
        df["sim_tenure_months"].quantile(0.33)
    )
    train_mask = df["sim_tenure_months"] <= cutoff
    val_mask = df["sim_tenure_months"] > cutoff

    train_raw = df[train_mask].reset_index(drop=True)
    val_raw = df[val_mask].reset_index(drop=True)
    cols = get_model_feature_columns()

    q_m = fit_monthly_spend_q75(train_raw)
    q_a = fit_lifetime_arpu_q75(train_raw)
    train_fe = build_features(train_raw, monthly_spend_q75=q_m, lifetime_arpu_q75=q_a)
    val_fe = build_features(val_raw, monthly_spend_q75=q_m, lifetime_arpu_q75=q_a)

    X_tr = train_fe[cols].values.astype(np.float64)
    y_tr = train_fe["churn_binary"].values
    X_va = val_fe[cols].values.astype(np.float64)
    y_va = val_fe["churn_binary"].values

    families = families or available_model_families()
    results: list[dict[str, Any]] = []
    for fam in families:
        if fam not in available_model_families():
            continue
        try:
            use_cw = fam in ("random_forest", "logistic_regression", "lightgbm", "catboost")
            model, _ = fit_model(fam, X_tr, y_tr, class_weight=use_cw)  # type: ignore[arg-type]
            p_va = predict_proba(model, X_va)
            results.append(
                {
                    "family": fam,
                    "ranking": ranking_metrics(y_va, p_va),
                    "at_threshold_0.5": evaluate_probs(y_va, p_va, 0.5),
                }
            )
        except Exception as exc:
            results.append({"family": fam, "error": str(exc)})

    return {
        "feasible": True,
        "limitation": (
            "Dataset has no observation date. Tenure-based split is a weak proxy only; "
            "churn labels may not align with true time-based drift."
        ),
        "proxy_variable": "sim_tenure_months",
        "cutoff_months": cutoff,
        "n_train_shorter_tenure": int(train_mask.sum()),
        "n_val_longer_tenure": int(val_mask.sum()),
        "churn_rate_train": float(train_raw["churn_binary"].mean()),
        "churn_rate_val": float(val_raw["churn_binary"].mean()),
        "results": results,
    }


def save_stability_summary(summary: dict[str, Any], path: Path | None = None) -> Path:
    """Persist the CV stability summary to OUTPUT_CHAMPION / model_stability_summary.json.

    Args:
        summary: The dict returned by run_cv_stability().
        path: Output path. Defaults to OUTPUT_CHAMPION / 'model_stability_summary.json'.

    Returns:
        Path to the written JSON file.

    Side effects: Creates parent directory if needed and writes JSON.
    """
    path = path or OUTPUT_CHAMPION / "model_stability_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return path
