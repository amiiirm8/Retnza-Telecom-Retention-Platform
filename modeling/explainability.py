"""Task 7 — SHAP explainability (base model only, telecom-aware narratives).

Explains the champion model using SHAP (SHapley Additive exPlanations) with
telecom-domain-specific feature labels, risk direction hints, and cohort
analysis (prepaid/postpaid, digital engagement, etc.).

Why SHAP explains base model only — not calibrator:
  SHAP decomposes a prediction into additive feature attributions. The calibrator
  is a monotonic univariate function f(p_raw) that preserves rank order. Adding
  SHAP values through the calibrator would either be a no-op (for monotonic
  calibrators) or would conflate the calibrator's 1-D transformation with feature
  attributions. All business interpretation (risk drivers, direction of impact)
  is derived from the base model, and the calibrated score is used only for
  risk band assignment where the absolute value matters, not the decomposition.

Pipeline position: called independently after champion training (Task 7).
Workflow stage: reporting.
Key invariants:
  - SHAP is computed on the BASE model, not the ProbabilityCalibrator wrapper.
  - population-level SHAP is exported for recommendation.engine merge.
  - Feature labels and risk directions are maintained in FEATURE_RISK_DIRECTION.
  - Cohort masks are defined by telecom segment flags (is_prepaid, rubika, etc.).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from feature_engineering.builders import build_features
from feature_engineering.registry import MODEL_FEATURE_GROUPS, get_business_labels
from modeling.config import CLEANED_PATH, OUTPUT_CHAMPION, OUTPUT_EXPLAINABILITY, RANDOM_STATE
from modeling.governance import validate_champion_bundle, validate_shap_parquet
from modeling.scoring import calibrate_raw_proba, predict_raw_proba
from modeling.splits import load_feature_splits

CHAMPION_PATH = OUTPUT_CHAMPION / "champion_model.joblib"
"""Path to the serialised champion model bundle."""

FEATURE_BUSINESS_LABELS: dict[str, str] = get_business_labels()
"""Human-readable label for each feature column (from feature_engineering registry)."""

FEATURE_RISK_DIRECTION: dict[str, str] = {
    "is_prepaid": "Prepaid segment associated with higher churn risk",
    "early_lifecycle_flag": "Short tenure raises risk",
    "zero_vas_capable_flag": "No VAS on capable network raises risk",
    "volte_non_adopter_capable": "VoLTE non-adoption raises risk",
    "prepaid_5g_risk_flag": "Prepaid on 5G — high-risk segment",
    "rubika_user_flag": "Rubika adoption may lower risk when active",
    "ewano_user_flag": "EWANO financial engagement pattern",
    "hamrahman_user_flag": "Hamrah Man app engagement",
    "digital_engagement_score": "Low digital engagement raises risk",
    "monthly_to_lifetime_arpu_ratio": "Spend spike vs history raises risk",
    "possible_bill_shock_flag": "Bill-shock pattern raises risk",
}
"""Domain-specific risk direction hints for SHAP narratives."""


def _shap_to_business_text(feature: str, shap_value: float) -> str:
    """Generate a human-readable narrative for a single SHAP contribution.

    Args:
        feature: Raw feature name.
        shap_value: SHAP value for this feature on this prediction.

    Returns:
        A string combining the business label, the numerical SHAP value, and
        a risk-direction hint.
    """
    label = FEATURE_BUSINESS_LABELS.get(feature, feature)
    if shap_value > 0:
        hint = FEATURE_RISK_DIRECTION.get(feature, "Increases predicted churn risk")
        return f"{label}: +{shap_value:.3f} — {hint}"
    if shap_value < 0:
        return f"{label}: {shap_value:.3f} — Lowers predicted churn risk"
    return f"{label}: neutral"


def extract_local_shap_drivers(
    shap_row: np.ndarray,
    feature_names: list[str],
    top_k: int = 3,
) -> dict[str, Any]:
    """Extract the top-k positive and negative SHAP drivers for a single prediction.

    Returns a structured dict with business_label and narrative for each driver,
    suitable for populating per-subscriber explainability records.

    Args:
        shap_row: SHAP values for a single prediction (1-D array).
        feature_names: Names of the feature columns (same order as shap_row).
        top_k: Number of top positive and negative drivers to extract (default 3).

    Returns:
        dict with keys:
          - 'shap_top_positive': list of driver dicts (sorted by |SHAP| descending).
          - 'shap_top_negative': list of driver dicts.
          - 'explanation_summary': short string summarising the top 2 risk drivers.
    """
    shap_row = np.asarray(shap_row, dtype=float)
    pos_idx = np.argsort(-shap_row)[:top_k]
    neg_idx = np.argsort(shap_row)[:top_k]

    def _pack(indices: np.ndarray, effect: str) -> list[dict[str, Any]]:
        out = []
        for j in indices:
            if abs(shap_row[j]) < 1e-8:
                continue
            feat = feature_names[j]
            out.append(
                {
                    "feature": feat,
                    "business_label": FEATURE_BUSINESS_LABELS.get(feat, feat),
                    "shap_value": float(shap_row[j]),
                    "effect": effect,
                    "narrative": _shap_to_business_text(feat, float(shap_row[j])),
                }
            )
        return out

    positive = _pack(pos_idx, "increases_risk")
    negative = _pack(neg_idx, "decreases_risk")
    return {
        "shap_top_positive": positive,
        "shap_top_negative": negative,
        "explanation_summary": "; ".join(d["narrative"] for d in positive[:2])
        or "No dominant risk drivers",
    }


def _transform_for_shap(model: Any, X: np.ndarray) -> np.ndarray:
    """Apply pipeline scaler when the model is an sklearn Pipeline.

    SHAP explainers need to see the internal representation of the classifier,
    not the raw features. For LogisticRegression (wrapped in Pipeline), we
    pass the scaled representation to SHAP.

    Args:
        model: The fitted model (may be a Pipeline).
        X: Feature matrix.

    Returns:
        Transformed feature matrix (scaled if Pipeline, else unchanged).
    """
    from sklearn.pipeline import Pipeline

    if isinstance(model, Pipeline) and "scaler" in model.named_steps:
        return model.named_steps["scaler"].transform(X)
    return X


def _compute_shap_values(model: Any, X: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Compute SHAP values for the base model using the best available explainer.

    Dispatch order:
      1. RandomForest / tree-based → shap.TreeExplainer (interventional).
      2. LogisticRegression → shap.LinearExplainer.
      3. Other sklearn trees (HGB) → shap.TreeExplainer with model_output='probability'.
      4. Fallback → shap.Explainer with a callable wrapper.

    Args:
        model: The base model (may be Pipeline; inner estimator is extracted).
        X: Feature matrix to explain.
        background: Background dataset for SHAP (subset of training data).

    Returns:
        2-D array of SHAP values with shape (n_samples, n_features).

    Side effects: None (pure computation).
    """
    import shap
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    X_bg = _transform_for_shap(model, background)
    X_ex = _transform_for_shap(model, X)

    inner = model.named_steps["clf"] if isinstance(model, Pipeline) else model

    if isinstance(inner, (RandomForestClassifier,)) or hasattr(inner, "tree_"):
        explainer = shap.TreeExplainer(inner, data=X_bg, feature_perturbation="interventional")
        sv = explainer.shap_values(X_ex)
        if isinstance(sv, list):
            sv = sv[1]
        sv = np.asarray(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        return sv.reshape(len(X), -1)

    if isinstance(inner, LogisticRegression):
        explainer = shap.LinearExplainer(inner, X_bg)
        return np.asarray(explainer.shap_values(X_ex), dtype=float)

    # HistGradientBoosting, optional boosters, fallbacks
    try:
        explainer = shap.TreeExplainer(model, data=background, model_output="probability")
        sv = explainer.shap_values(X)
        if isinstance(sv, list):
            sv = sv[1]
        return np.asarray(sv).reshape(len(X), -1)
    except Exception:
        masker = shap.maskers.Independent(background)
        explainer = shap.Explainer(
            lambda data: predict_raw_proba({"base_model": model}, np.asarray(data)),
            masker,
        )
        sv = explainer(X)
        return np.asarray(sv.values, dtype=float)


def _cohort_shap_summary(
    shap_values: np.ndarray,
    feature_names: list[str],
    cohort_mask: np.ndarray,
    cohort_name: str,
) -> dict[str, Any]:
    """Compute mean |SHAP| top-5 features for a cohort (subgroup).

    Args:
        shap_values: Full SHAP value array (n_samples, n_features).
        feature_names: Column names.
        cohort_mask: Boolean mask selecting the cohort.
        cohort_name: Human-readable cohort label.

    Returns:
        dict with 'cohort', 'n', and 'top_features' list (5 entries with
        feature, mean_abs_shap, business_label).
    """
    if not cohort_mask.any():
        return {"cohort": cohort_name, "n": 0, "top_features": []}
    mean_abs = np.abs(shap_values[cohort_mask]).mean(axis=0)
    order = np.argsort(-mean_abs)[:5]
    return {
        "cohort": cohort_name,
        "n": int(cohort_mask.sum()),
        "top_features": [
            {
                "feature": feature_names[j],
                "mean_abs_shap": float(mean_abs[j]),
                "business_label": FEATURE_BUSINESS_LABELS.get(feature_names[j], feature_names[j]),
            }
            for j in order
        ],
    }


def _group_importance(
    shap_values: np.ndarray,
    feature_names: list[str],
) -> pd.DataFrame:
    """Aggregate |SHAP| by feature family / group (ecosystem, demographic, etc.).

    Uses MODEL_FEATURE_GROUPS from the feature_engineering registry to group
    related features and compute mean absolute SHAP per group.

    Args:
        shap_values: Full SHAP value array.
        feature_names: Column names.

    Returns:
        DataFrame with columns 'feature_group', 'mean_abs_shap', 'n_features',
        sorted by mean_abs_shap descending.
    """
    rows = []
    name_to_idx = {f: i for i, f in enumerate(feature_names)}
    for group, feats in MODEL_FEATURE_GROUPS.items():
        idxs = [name_to_idx[f] for f in feats if f in name_to_idx]
        if not idxs:
            continue
        rows.append(
            {
                "feature_group": group,
                "mean_abs_shap": float(np.abs(shap_values[:, idxs]).mean()),
                "n_features": len(idxs),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_abs_shap", ascending=False)


def _telecom_cohort_masks(test_fe: pd.DataFrame) -> list[tuple[str, np.ndarray]]:
    """Define telecom retention cohorts for grouped SHAP narratives.

    Cohorts are defined by telecom segment flags:
      - age_bucket_*
      - rubika_active / ewano_active / hamrahman_active
      - high / low digital_engagement_score
      - prepaid / postpaid

    Args:
        test_fe: Test split feature DataFrame.

    Returns:
        List of (cohort_name, boolean_mask) tuples.
    """
    masks: list[tuple[str, np.ndarray]] = []
    n = len(test_fe)

    def _add(name: str, mask: pd.Series | np.ndarray) -> None:
        m = np.asarray(mask, dtype=bool)
        if m.shape[0] == n and m.any():
            masks.append((name, m))

    if "age_bucket" in test_fe.columns:
        for bucket in sorted(test_fe["age_bucket"].dropna().unique()):
            _add(f"age_bucket_{int(bucket)}", test_fe["age_bucket"] == bucket)
    if "rubika_user_flag" in test_fe.columns:
        _add("rubika_active", test_fe["rubika_user_flag"] == 1)
    if "ewano_user_flag" in test_fe.columns:
        _add("ewano_active", test_fe["ewano_user_flag"] == 1)
    if "hamrahman_user_flag" in test_fe.columns:
        _add("hamrahman_active", test_fe["hamrahman_user_flag"] == 1)
    if "digital_engagement_score" in test_fe.columns:
        _add("high_digital_engagement", test_fe["digital_engagement_score"] >= 3)
        _add("low_digital_engagement", test_fe["digital_engagement_score"] <= 1)
    if "is_prepaid" in test_fe.columns:
        _add("prepaid", test_fe["is_prepaid"] == 1)
        _add("postpaid", test_fe["is_prepaid"] == 0)
    return masks


def run_shap_analysis(
    max_background: int = 500,
    local_top_k: int = 5,
    n_local_examples: int = 8,
) -> dict[str, Any]:
    """Run full SHAP analysis on the champion model and persist all artifacts.

    Steps:
      1. Load champion bundle from CHAMPION_PATH and validate.
      2. Load train/test splits and compute raw + calibrated scores on test.
      3. Sample background dataset from training split (max_background rows).
      4. Compute SHAP values for test set using the best available explainer.
      5. Compute global importance (mean |SHAP|), cohort summaries, group importance.
      6. Export CSV artifacts (global, group, cohort).
      7. Export local SHAP drivers for top-N highest-risk subscribers.
      8. Export full subscriber-level SHAP parquet for recommendation.engine.
      9. Generate and save beeswarm plot (if matplotlib available).
      10. Assemble and persist the explainability manifest JSON.

    Args:
        max_background: Max background samples for SHAP explainer (default 500).
        local_top_k: Number of top SHAP drivers per local example (default 5).
        n_local_examples: Number of highest-risk subscribers for local analysis (default 8).

    Returns:
        The explainability manifest dict with all artifact paths and cohort summaries.

    Side effects:
      - Creates OUTPUT_EXPLAINABILITY directory.
      - Writes CSVs: global_shap_importance.csv, group_shap_importance.csv,
        cohort_shap_summary.csv.
      - Writes parquet: subscriber_shap_test.parquet, subscriber_shap_values.parquet.
      - Writes JSON: explainability_manifest.json.
      - Writes PNG: shap_beeswarm.png (if matplotlib available).

    Failure modes:
      - Raises ModelArtifactError if champion bundle is incompatible.
      - Silently catches matplotlib ImportError (writes warning to manifest).
    """
    bundle = joblib.load(CHAMPION_PATH)
    validate_champion_bundle(bundle)
    base_model = bundle["base_model"]
    feature_names: list[str] = list(bundle["feature_columns"])
    split = load_feature_splits()
    X_train, X_test = split.X_train, split.X_test
    y_test = split.y_test
    test_fe = split.test_df

    p_raw = predict_raw_proba(bundle, X_test)
    p_cal = calibrate_raw_proba(bundle, p_raw)

    # Sample a fixed background set from training data for SHAP explainer consistency.
    bg_idx = np.random.default_rng(RANDOM_STATE).choice(
        len(X_train), size=min(max_background, len(X_train)), replace=False
    )
    background = X_train[bg_idx]
    shap_values = _compute_shap_values(base_model, X_test, background)

    mean_abs = np.abs(shap_values).mean(axis=0)
    mean_shap = shap_values.mean(axis=0)
    churn_mask = y_test == 1
    retain_mask = y_test == 0

    global_table = pd.DataFrame(
        {
            "feature": feature_names,
            "business_label": [FEATURE_BUSINESS_LABELS.get(f, f) for f in feature_names],
            "mean_abs_shap": mean_abs,
            "mean_shap_all": mean_shap,
            "direction_overall": np.where(mean_shap > 0, "increases_risk", "decreases_risk"),
            "mean_shap_churners": shap_values[churn_mask].mean(axis=0) if churn_mask.any() else mean_shap,
            "mean_shap_retainers": shap_values[retain_mask].mean(axis=0) if retain_mask.any() else mean_shap,
        }
    ).sort_values("mean_abs_shap", ascending=False)

    cohort_rows = [
        _cohort_shap_summary(shap_values, feature_names, churn_mask, "churners"),
        _cohort_shap_summary(shap_values, feature_names, retain_mask, "retainers"),
    ]
    if "is_prepaid" in test_fe.columns:
        cohort_rows.append(
            _cohort_shap_summary(shap_values, feature_names, test_fe["is_prepaid"] == 1, "prepaid")
        )
        cohort_rows.append(
            _cohort_shap_summary(shap_values, feature_names, test_fe["is_prepaid"] == 0, "postpaid")
        )
    for cohort_name, mask in _telecom_cohort_masks(test_fe):
        if cohort_name not in {r["cohort"] for r in cohort_rows}:
            cohort_rows.append(
                _cohort_shap_summary(shap_values, feature_names, mask, cohort_name)
            )

    group_table = _group_importance(shap_values, feature_names)

    OUTPUT_EXPLAINABILITY.mkdir(parents=True, exist_ok=True)
    global_table.to_csv(OUTPUT_EXPLAINABILITY / "global_shap_importance.csv", index=False)
    group_table.to_csv(OUTPUT_EXPLAINABILITY / "group_shap_importance.csv", index=False)
    pd.DataFrame(cohort_rows).to_csv(OUTPUT_EXPLAINABILITY / "cohort_shap_summary.csv", index=False)

    # Local high-risk examples (top N by calibrated probability)
    order = np.argsort(-p_cal)
    local_records = []
    feature_df = pd.DataFrame(X_test, columns=feature_names)
    for rank, idx in enumerate(order[:n_local_examples], start=1):
        row_shap = shap_values[idx]
        local_records.append(
            {
                "example_rank": rank,
                "subscriber_id": int(test_fe["subscriber_id"].iloc[idx]),
                "churn_actual": int(y_test[idx]),
                "churn_probability_raw": float(p_raw[idx]),
                "churn_probability_calibrated": float(p_cal[idx]),
                **extract_local_shap_drivers(row_shap, feature_names, top_k=local_top_k),
            }
        )

    shap_long = feature_df.copy()
    shap_long.insert(0, "subscriber_id", test_fe["subscriber_id"].values)
    shap_long["churn_probability_raw"] = p_raw
    shap_long["churn_probability_calibrated"] = p_cal
    shap_long["churn_actual"] = y_test
    for i, f in enumerate(feature_names):
        shap_long[f"shap_{f}"] = shap_values[:, i]
    shap_long.to_parquet(OUTPUT_EXPLAINABILITY / "subscriber_shap_test.parquet", index=False)

    pop_path = export_population_shap(bundle=bundle, background=background)

    manifest: dict[str, Any] = {
        "schema_version": "task7-shap-v4",
        "feature_schema": "task4-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_explained": f"{bundle.get('model_family', 'tree')} base model (47-feature contract)",
        "n_features": len(feature_names),
        "shap_target": "base model probability — not calibrator",
        "scores_for_risk_bands": "calibrated probability from champion bundle",
        "outputs": {
            "global_importance": str(OUTPUT_EXPLAINABILITY / "global_shap_importance.csv"),
            "group_importance": str(OUTPUT_EXPLAINABILITY / "group_shap_importance.csv"),
            "cohort_summary": str(OUTPUT_EXPLAINABILITY / "cohort_shap_summary.csv"),
            "test_shap_parquet": str(OUTPUT_EXPLAINABILITY / "subscriber_shap_test.parquet"),
            "population_shap": str(pop_path),
        },
        "cohort_summaries": cohort_rows,
        "top_global_drivers": global_table.head(10).to_dict(orient="records"),
        "local_examples": local_records,
        "feature_groups": list(MODEL_FEATURE_GROUPS.keys()),
        "caveats": [
            "SHAP is associative, not causal.",
            "Explains ranking layer; calibration is monotonic post-process.",
            "Retrain SHAP after any feature schema change.",
        ],
    }
    (OUTPUT_EXPLAINABILITY / "explainability_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    try:
        import matplotlib.pyplot as plt
        import shap

        shap.summary_plot(
            shap_values,
            feature_df,
            feature_names=[FEATURE_BUSINESS_LABELS.get(f, f) for f in feature_names],
            show=False,
            max_display=20,
        )
        plt.tight_layout()
        plt.savefig(OUTPUT_EXPLAINABILITY / "shap_beeswarm.png", dpi=150, bbox_inches="tight")
        plt.close()
    except Exception as e:
        manifest["plot_warning"] = str(e)

    return manifest


def export_population_shap(
    bundle: dict[str, Any] | None = None,
    background: np.ndarray | None = None,
    max_background: int = 500,
    batch_size: int = 2000,
) -> Path:
    """Compute and export SHAP values for the entire subscriber population.

    Used by recommendation.engine to merge SHAP importance into per-subscriber
    recommendation records. Batched for memory efficiency on large populations.

    Why SHAP explains base model only:
        The calibrator is a 1-D monotonic function of p_raw. Decomposing through it
        would not add information. All feature attribution comes from the base model.

    Args:
        bundle: Loaded champion bundle. If None, loaded from CHAMPION_PATH.
        background: Background array for SHAP. If None, sampled from training split.
        max_background: Max background samples.
        batch_size: Number of subscribers per SHAP batch (default 2000).

    Returns:
        Path to the exported parquet file (subscriber_shap_values.parquet).

    Side effects:
        - Creates OUTPUT_EXPLAINABILITY directory.
        - Writes subscriber_shap_values.parquet with columns:
          subscriber_id, churn_probability_raw, churn_probability_calibrated,
          shap_<feature_name> for every feature.
    """
    bundle = bundle or joblib.load(CHAMPION_PATH)
    validate_champion_bundle(bundle)
    base_model = bundle["base_model"]
    feature_names = list(bundle["feature_columns"])

    split = load_feature_splits()
    if background is None:
        bg_idx = np.random.default_rng(RANDOM_STATE).choice(
            len(split.X_train), size=min(max_background, len(split.X_train)), replace=False
        )
        background = split.X_train[bg_idx]

    cleaned = pd.read_parquet(CLEANED_PATH)
    fe = build_features(
        cleaned,
        monthly_spend_q75=float(bundle["monthly_spend_q75"]),
        lifetime_arpu_q75=float(bundle.get("lifetime_arpu_q75", bundle["monthly_spend_q75"])),
    )
    X = fe[feature_names].values.astype(np.float64)
    n = len(X)
    p_raw = predict_raw_proba(bundle, X)
    p_cal = calibrate_raw_proba(bundle, p_raw)

    # Batch SHAP computation to avoid OOM on large populations.
    shap_chunks: list[np.ndarray] = []
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        shap_chunks.append(_compute_shap_values(base_model, X[start:end], background))
    shap_values = np.vstack(shap_chunks)

    out = pd.DataFrame({"subscriber_id": fe["subscriber_id"].values})
    out["churn_probability_raw"] = np.round(p_raw, 4)
    out["churn_probability_calibrated"] = np.round(p_cal, 4)
    for i, f in enumerate(feature_names):
        out[f"shap_{f}"] = shap_values[:, i]

    path = OUTPUT_EXPLAINABILITY / "subscriber_shap_values.parquet"
    out.to_parquet(path, index=False)
    validate_shap_parquet(path, feature_names)
    return path
