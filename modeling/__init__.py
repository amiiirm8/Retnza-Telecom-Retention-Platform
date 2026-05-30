"""Retnza modeling layer — core ML pipeline (modeling pipeline).

Pipeline stages covered by submodules:
  - **Splits** (splits.py): Canonical stratified 70/15/15 train/val/test split,
    single source of truth for all downstream tasks.
  - **Candidates** (candidates.py): Estimator factories, tuning, resampling.
    Defines ModelFamily (7 families) and ImbalanceStrategy types.
  - **Baselines** (baseline.py): Systematic benchmarking of all families ×
    imbalance strategies to produce the baseline decisions report.
  - **Selection** (selection.py): Champion model selection with PR-AUC
    tolerance band and simplicity / stability preference.
  - **Calibration** (calibration.py): Post-hoc probability calibration on
    validation raw probabilities only — never on feature matrix X.
  - **Stability** (stability.py): Repeated stratified K-fold on the train+val
    pool (test held out) to flag split-sensitive winners.
  - **Evaluation** (evaluation.py): Telecom-specific metrics, decile gains,
    top-k contact lift, and calibration-error computation.
  - **Thresholds** (thresholds.py): Operating threshold policies tuned for
    retention business context (FN cost >> FP cost).
  - **Champion** (champion.py): Orchestrates candidate scoring → selection →
    calibration → drift snapshot → bundle packaging → governance validation.
    Produces the champion_model.joblib and champion_manifest.json.
  - **Drift** (drift.py): Reference distribution snapshots for post-deployment
    PSI / score monitoring.
  - **Scoring** (scoring.py): Production scoring contract — raw ranking
    probability + calibrated risk communication + risk-tier assignment.
  - **Explainability** (explainability.py): SHAP analysis on the base model
    only (not the calibrator) with telecom-aware cohort narratives.
  - **Governance** (governance.py): Artifact validation, compatibility checks,
    legacy detection, and lifecycle management.
  - **Config** (config.py): Central constants, paths, schema versions,
    and business policy defaults.

Workflow stages modeled:
  - **Training**: splits, candidates, baselines, selection, calibration,
    stability, champion, explainability.
  - **Inference / Scoring**: scoring module only (predict_raw_proba,
    calibrate_raw_proba, assign_risk_tier).
  - **Reporting**: evaluation, thresholds, drift (snapshots), explainability
    (SHAP manifests).
  - **Governance / Lifecycle**: governance module (validate, audit, archive).

Key invariants:
  - FE threshold fit (monthly_spend_q75, lifetime_arpu_q75) on train only.
  - Calibrator fit on validation raw probabilities only.
  - SHAP explains base model only — not the calibrator.
  - Test split is never used for any fit or selection decision.
  - Champion selection prefers simpler models within a PR-AUC tolerance band.
  - stability CV uses the train+val pool; test is always held out.

Import submodules directly to avoid loading heavy training deps at package import.
"""

__all__: list[str] = []
