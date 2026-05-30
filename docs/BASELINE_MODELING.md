# Baseline Modeling

## Objective

Establish a reproducible **70/15/15 stratified** baseline (seed `42`) on feature engineering features, compare imbalance handling, and separate:

1. **Ranking / propensity** — who is riskiest (PR-AUC, score ordering).
2. **Campaign contact** — who gets CRM outreach (recall-first threshold on validation).

The **test set is untouched** until final reporting.

## Data and features

- Source: `data/cleaned/subscribers_cleaned.parquet` → `build_features()` with Q75 monthly spend fit on **train only**.
- **47** engineered features (`feature_engineering.builders.MODEL_FEATURE_COLUMNS`).
- No full-dataset fit; no spend imputation (preprocessing).

## Models and imbalance strategies

| Model | Imbalance variants |
|-------|-------------------|
| Logistic regression | none, class_weight, SMOTE, undersample |
| Random forest | none, class_weight (+ threshold policies) |
| HistGradientBoosting | none, class_weight |

**HistGradientBoosting:** sklearn has no `class_weight` on this estimator. When `class_weight` is requested we use `compute_sample_weight(class_weight="balanced", y=y)` and pass `sample_weight` to `fit()`. This is recorded in `imbalance_fit_note` in `baseline_results.json`.

## Threshold policies

| Policy | Use | Rule |
|--------|-----|------|
| `default_0.5` | Standard classifier cutoff | Fixed 0.5 |
| `business_min_recall` | **Primary for contact** | Lowest validation threshold with recall ≥ **0.75** and precision ≥ **0.50** when feasible; else lowest threshold meeting recall only |
| `f1_max_reference` | Reference only | Max F1 on validation — **not** the business default |

**Why not F1 as primary?** Retention cares more about **missed churners (FN)** than false alarms (FP). F1 weights precision and recall equally, which does not match “find more true churners without flooding CRM.”

## Baseline decisions (two use cases)

### Ranking baseline

- **Selection:** Best **test PR-AUC** among runs with `imbalance_strategy: none` (no resampling; threshold does not affect PR-AUC).
- **Typical winner:** Random forest without class weights (~0.646 test PR-AUC); weighted RF scores are similar but kept for the **contact** track.
- **Use:** Dashboards, prioritization, SHAP on the same tree family.

### Contact / campaign baseline

- **Model:** Random forest with **`class_weight="balanced"`**.
- **Threshold:** `business_min_recall` on **validation** only; applied unchanged on test for reporting.
- **Metrics:** Recall and precision at that threshold; confusion matrix on test.
- **Use:** Operational “who to call” when capacity is score-threshold based.

For **fixed CRM capacity** (e.g. top 10% of subscribers), see `baseline_decisions.top_k_validation_rf_weighted` in the JSON artifact.

## Validation diagnostics

For weighted RF on validation:

- **`pr_curve_validation_rf_weighted`** — precision/recall vs threshold (see where the chosen threshold sits).
- **`top_k_validation_rf_weighted`** — precision, recall, lift when contacting top 10/20/30% by score.

## How to reproduce

```bash
.venv/bin/python scripts/train_baselines.py
```

Output: `outputs/baselines/baseline_results.json` (`schema_version`: `modeling`).

## Handoff to champion model

- Champion tuning optimizes **PR-AUC** (ranking).
- Operating policy for outreach should follow the same **recall-first** rule as baselines (`min_recall_0.75_validation`), not max F1 alone.
- Uncalibrated probabilities may rank slightly better; calibrated probabilities support truthful risk bands.

## Open business inputs

Confirm with stakeholders:

- Target **minimum recall** (0.75 is a working default).
- Acceptable **precision floor** or **max contact rate** (top-k).
- Relative **cost of FN vs FP** if a full cost-based threshold is preferred later.
