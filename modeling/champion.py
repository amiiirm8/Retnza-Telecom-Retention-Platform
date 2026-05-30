"""Task 6 — champion selection, calibration, stability, and artifact packaging.

Orchestrates the entire champion training pipeline:
  1. Load canonical train/val/test split (splits.py).
  2. Run CV stability analysis on train+val pool (stability.py).
  3. Run temporal proxy diagnostic (stability.py).
  4. Score each candidate family: train on train, predict on val+test.
     RF optionally tuned via RandomizedSearchCV.
  5. Select champion via tolerance-band selection (selection.py).
  6. Compare calibration methods on validation raw probabilities (calibration.py).
  7. Select best calibration method (calibration.py).
  8. Compute calibrated scores, resolve threshold policies (thresholds.py).
  9. Build drift snapshot (drift.py).
  10. Package champion bundle (base_model + calibrator + metadata) as joblib.
  11. Validate bundle, write manifest, audit ecosystem, write governance report.

Pipeline position: main orchestrator (Task 6), called after baselines (Task 5).
Workflow stage: training + reporting + governance.
Key invariants:
  - Stability CV runs on train+val pool; test held out at all times.
  - FE thresholds (monthly_spend_q75, lifetime_arpu_q75) fit on train only.
  - Calibrator fit on validation raw probabilities only.
  - SHAP explains base model only (not the calibrator).
  - Champion selection prefers simpler models within PR-AUC tolerance band.
  - The bundle schema includes retrain_required_if triggers for governance.
  - Legacy 18-feature artifacts are explicitly detected and blocked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from modeling.calibration import (
    compare_calibration_methods,
    save_calibration_summary,
    select_calibration_method,
)
from modeling.candidates import (
    available_model_families,
    fit_model,
    predict_proba,
    tune_random_forest,
)
from modeling.config import (
    CHAMPION_BUNDLE_SCHEMA,
    CHAMPION_PR_AUC_TOLERANCE_ABS,
    CHAMPION_PR_AUC_TOLERANCE_REL,
    MODELING_SCHEMA_VERSION,
    OUTPUT_CHAMPION,
    RISK_TIER_THRESHOLDS,
)
from modeling.drift import build_drift_snapshot, save_drift_snapshot, save_drift_summary_governance
from modeling.evaluation import decile_gain_table, ranking_metrics
from modeling.governance import (
    audit_artifact_ecosystem,
    bundle_metadata,
    validate_champion_bundle,
    write_compatibility_report,
)
from modeling.scoring import predict_raw_proba
from modeling.selection import select_champion_with_tolerance
from modeling.splits import SplitBundle, load_feature_splits
from modeling.stability import (
    run_cv_stability,
    run_temporal_proxy_diagnostic,
    save_stability_summary,
)
from modeling.thresholds import build_threshold_policy_report


@dataclass
class ChampionReport:
    """Result of the full champion training pipeline.

    Attributes:
        manifest: The complete champion manifest dict (schema_version, selection,
            calibration, drift, governance, etc.) suitable for JSON serialisation.
        model_path: Path to the serialised champion_model.joblib bundle.
    """
    manifest: dict[str, Any]
    model_path: Path


def _score_candidate(
    family: str,
    split: SplitBundle,
    *,
    tune_rf: bool = True,
) -> dict[str, Any]:
    """Train a candidate model and compute val/test metrics.

    Special handling:
      - Random Forest is optionally tuned with RandomizedSearchCV (24 iterations,
        avg_precision scoring, 3-fold CV).
      - For all other families, class_weight='balanced' is applied for those
        that support it natively (RF, LR, LGBM, CatBoost).

    Args:
        family: The model family name.
        split: The canonical SplitBundle.
        tune_rf: If True and family is 'random_forest', run hyperparameter tuning.
            Default True.

    Returns:
        dict with keys: 'family', 'model' (fitted), 'tuning' (dict or note),
        'p_val_raw', 'p_test_raw', 'validation_ranking', 'test_ranking',
        'test_decile_gains'.

    Side effects: Fits a model on split.X_train.
    """
    if family == "random_forest" and tune_rf:
        model, tuning = tune_random_forest(split.X_train, split.y_train)
        fit_note = "randomized_search_cv_pr_auc"
    else:
        use_cw = family in ("random_forest", "logistic_regression", "lightgbm", "catboost")
        model, fit_note = fit_model(family, split.X_train, split.y_train, class_weight=use_cw)  # type: ignore[arg-type]
        tuning = {"note": fit_note}

    p_val = predict_proba(model, split.X_val)
    p_test = predict_proba(model, split.X_test)
    val_rank = ranking_metrics(split.y_val, p_val)
    test_rank = ranking_metrics(split.y_test, p_test)

    return {
        "family": family,
        "model": model,
        "tuning": tuning,
        "p_val_raw": p_val,
        "p_test_raw": p_test,
        "validation_ranking": val_rank,
        "test_ranking": test_rank,
        "test_decile_gains": decile_gain_table(split.y_test, p_test),
    }


def train_champion(
    *,
    candidate_families: list[str] | None = None,
    tune_rf: bool = True,
    run_stability: bool = True,
    run_temporal: bool = True,
) -> ChampionReport:
    """Run the full champion training pipeline and produce the champion bundle.

    Orchestration sequence:
      1. Load canonical splits.
      2. (Optional) Run CV stability analysis and temporal proxy diagnostic.
      3. Score all candidate families (train on train, evaluate on val+test).
      4. Select champion using tolerance-band + simplicity/stability preference.
      5. Compare calibration methods on validation raw probabilities.
      6. Select best calibration method (prefer sigmoid when isotonic overfit risk high).
      7. Compute calibrated scores for train/val/test.
      8. Build threshold policy report (4 policies, operating point, top-k metrics).
      9. Build and save drift reference snapshot.
      10. Assemble champion bundle (base_model + calibrator + feature columns + metadata).
      11. Serialise bundle to joblib, validate, write manifest, audit ecosystem.

    Args:
        candidate_families: List of family names to consider. If None, uses all
            available families from available_model_families().
        tune_rf: If True (default), run hyperparameter tuning for Random Forest.
        run_stability: If True (default), run CV stability analysis before selection.
        run_temporal: If True (default), run temporal proxy diagnostic.

    Returns:
        ChampionReport with manifest dict and model_path.

    Side effects:
      - Writes to OUTPUT_CHAMPION: champion_model.joblib, champion_manifest.json,
        model_stability_summary.json, calibration_summary.json,
        drift_reference_snapshot.json.
      - Writes to OUTPUT_GOVERNANCE: drift_reference_summary.json,
        model_compatibility.json.

    Failure modes:
      - Raises RuntimeError if no candidates train successfully.
      - Raises ModelArtifactError if the assembled bundle fails strict validation.
    """
    split = load_feature_splits()
    families = candidate_families or available_model_families()
    env_available = available_model_families()

    stability_summary: dict[str, Any] | None = None
    temporal_diag: dict[str, Any] | None = None
    if run_stability:
        stability_summary = run_cv_stability(families=families)
        save_stability_summary(stability_summary)
    if run_temporal:
        temporal_diag = run_temporal_proxy_diagnostic(families=families)

    candidate_results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for fam in families:
        if fam not in env_available:
            skipped.append({"family": fam, "reason": "not_installed"})
            continue
        try:
            candidate_results.append(
                _score_candidate(fam, split, tune_rf=tune_rf and fam == "random_forest")
            )
        except Exception as exc:
            candidate_results.append(
                {
                    "family": fam,
                    "error": str(exc),
                    "validation_ranking": {"pr_auc": -1},
                }
            )
            skipped.append({"family": fam, "reason": str(exc)})

    valid = [c for c in candidate_results if "model" in c]
    if not valid:
        raise RuntimeError("No champion candidates trained successfully")

    # Select champion: simplest stable model within PR-AUC tolerance.
    winner, selection_rationale = select_champion_with_tolerance(valid, stability_summary)
    base_model = winner["model"]
    family = winner["family"]

    # Calibration: compare all methods on validation raw probabilities only.
    # The feature matrix X_val is used ONLY to get base_model raw probs, NOT for calibration fit.
    calib = compare_calibration_methods(
        base_model,
        split.X_val,
        split.y_val,
        split.X_test,
        split.y_test,
    )
    n_val_pos = int(split.y_val.sum())
    best_cal_method, cal_rationale = select_calibration_method(
        calib,
        n_val_positives=n_val_pos,
    )
    champion_wrap = calib["models"][best_cal_method]
    save_calibration_summary(calib, cal_rationale)

    p_val_raw = winner["p_val_raw"]
    p_test_raw = winner["p_test_raw"]
    p_train_raw = predict_raw_proba(
        {"base_model": base_model},
        split.X_train,
    )
    p_val_cal = champion_wrap.calibrate_probabilities(p_val_raw)
    p_test_cal = champion_wrap.calibrate_probabilities(p_test_raw)

    # Threshold policies: resolved on calibrated validation probabilities.
    threshold_report = build_threshold_policy_report(
        split.y_val, split.y_test, p_val_cal, p_test_cal
    )
    op_policy = threshold_report["recommended_operating_policy"]
    op_threshold = threshold_report["operating_threshold"]
    test_at_op = threshold_report["policies"][op_policy]["test"]
    cal_comparison = calib["comparison"]

    selection = {
        "winner_family": family,
        "candidates_compared": [c["family"] for c in valid],
        "candidates_skipped": skipped,
        "environment_available_families": env_available,
        "selection_rule": selection_rationale["rule"],
        "tolerance_abs": CHAMPION_PR_AUC_TOLERANCE_ABS,
        "tolerance_rel": CHAMPION_PR_AUC_TOLERANCE_REL,
        "selection_rationale": selection_rationale,
        "holdout_validation_pr_auc": winner["validation_ranking"]["pr_auc"],
        "holdout_test_pr_auc": winner["test_ranking"]["pr_auc"],
        "selected_calibration": best_cal_method,
        "calibration_selection": cal_rationale,
    }

    # Drift reference snapshot (used by post-deployment monitoring).
    drift_snapshot = build_drift_snapshot(
        train_df=split.train_df,
        val_df=split.val_df,
        test_df=split.test_df,
        feature_columns=split.feature_columns,
        p_train_raw=p_train_raw,
        p_val_raw=p_val_raw,
        p_test_raw=p_test_raw,
        p_val_cal=p_val_cal,
        p_test_cal=p_test_cal,
        calibration_method=best_cal_method,
        model_family=family,
        baseline_metrics={
            "test_ranking_raw": winner["test_ranking"],
            "test_at_operating": test_at_op,
        },
        schema_version=MODELING_SCHEMA_VERSION,
    )
    save_drift_snapshot(drift_snapshot)
    save_drift_summary_governance(drift_snapshot)

    manifest: dict[str, Any] = {
        "schema_version": MODELING_SCHEMA_VERSION,
        "bundle_schema_version": CHAMPION_BUNDLE_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "champion_family": family,
        "selection": selection,
        "stability_summary_ref": str(OUTPUT_CHAMPION / "model_stability_summary.json"),
        "temporal_proxy_diagnostic": temporal_diag,
        "candidate_benchmark": [
            {
                "family": c["family"],
                "validation_pr_auc": c.get("validation_ranking", {}).get("pr_auc"),
                "validation_brier": c.get("validation_ranking", {}).get("brier_score"),
                "test_pr_auc": c.get("test_ranking", {}).get("pr_auc"),
                "cv_pr_auc_mean": (
                    stability_summary["by_family"][c["family"]]["pr_auc"]["mean"]
                    if stability_summary and c["family"] in stability_summary.get("by_family", {})
                    else None
                ),
                "cv_pr_auc_std": (
                    stability_summary["by_family"][c["family"]]["pr_auc"]["std"]
                    if stability_summary and c["family"] in stability_summary.get("by_family", {})
                    else None
                ),
                "error": c.get("error"),
            }
            for c in candidate_results
        ],
        "split": split.meta,
        "tuning": winner.get("tuning", {}),
        "calibration_comparison": cal_comparison,
        "calibration_summary_ref": str(OUTPUT_CHAMPION / "calibration_summary.json"),
        "selected_calibration": best_cal_method,
        "calibrator_fit_data": "validation split raw probabilities only",
        "dual_score_outputs": {
            "churn_probability_raw": {
                "use": "Ranking, prioritization, top-k, PR-AUC monitoring",
            },
            "churn_probability_calibrated": {
                "use": "Risk bands, CRM thresholds, executive reporting",
            },
        },
        "threshold_policies": threshold_report["policies"],
        "threshold_policy_summary": {
            "recommended": op_policy,
            "operating_threshold": op_threshold,
            "config": threshold_report.get("policy_config"),
            "ranking_vs_operating": threshold_report.get("ranking_vs_operating"),
            "why_fn_costly": threshold_report.get("why_fn_costly"),
        },
        "recommended_operating_policy": op_policy,
        "operating_threshold": op_threshold,
        "risk_band_thresholds": RISK_TIER_THRESHOLDS,
        "test_at_operating_policy": test_at_op,
        "uncalibrated_vs_selected_test": {
            "pr_auc_raw": cal_comparison["none"]["test"]["pr_auc"],
            "pr_auc_calibrated": cal_comparison[best_cal_method]["test"]["pr_auc"],
            "brier_raw": cal_comparison["none"]["test"]["brier_score"],
            "brier_calibrated": cal_comparison[best_cal_method]["test"]["brier_score"],
            "ece_raw": cal_comparison["none"]["test"]["ece"],
            "ece_calibrated": cal_comparison[best_cal_method]["test"]["ece"],
        },
        "drift_snapshot_ref": str(OUTPUT_CHAMPION / "drift_reference_snapshot.json"),
        "governance": bundle_metadata(
            family,
            split.feature_columns,
            best_cal_method,
            split.meta,
            selection,
            stability_summary=stability_summary,
        ),
        "telecom_interpretation": {
            "prepaid": "is_prepaid and prepaid_* interaction flags",
            "ecosystem": "rubika, ewano, hamrahman, digital_engagement_score",
            "legacy_2g": "is_data_capable + tri-state -1 semantics",
            "spend": "bill shock and revenue_risk_segment",
            "stability": "CV stability summary flags split-sensitive winners",
        },
        "warnings": [
            "Prior 18-feature champion artifacts are INVALID — retrain required.",
            "SHAP explains base model only, not calibrator.",
            "Temporal validation uses tenure proxy only — no observation date in data.",
        ],
    }

    OUTPUT_CHAMPION.mkdir(parents=True, exist_ok=True)
    model_path = OUTPUT_CHAMPION / "champion_model.joblib"
    bundle = {
        "schema_version": CHAMPION_BUNDLE_SCHEMA,
        "modeling_schema_version": MODELING_SCHEMA_VERSION,
        "base_model": base_model,
        "calibrator": champion_wrap,
        "calibration_method": best_cal_method,
        "model_family": family,
        "feature_columns": split.feature_columns,
        "n_features": len(split.feature_columns),
        "monthly_spend_q75": split.monthly_spend_q75,
        "lifetime_arpu_q75": split.lifetime_arpu_q75,
        "operating_threshold": op_threshold,
        "operating_policy": op_policy,
        "risk_band_thresholds": RISK_TIER_THRESHOLDS,
        "selection": selection,
        "stability_pr_auc_mean": (
            stability_summary["by_family"][family]["pr_auc"]["mean"]
            if stability_summary and family in stability_summary.get("by_family", {})
            else None
        ),
    }
    joblib.dump(bundle, model_path)
    validate_champion_bundle(bundle)

    manifest_path = OUTPUT_CHAMPION / "champion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    compat = write_compatibility_report(audit_artifact_ecosystem())

    manifest["compatibility_report_ref"] = str(compat)
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    return ChampionReport(manifest=manifest, model_path=model_path)
