"""Champion selection with PR-AUC tolerance band and simplicity / stability preference.

Selects the best model from a list of scored candidates using a tolerance-band
approach: any model within an absolute and/or relative PR-AUC tolerance of the
best score is eligible. Among eligible candidates, preference is given in order:

  1. Lower cross-validated PR-AUC std (more stable across folds).
  2. Lower MODEL_SIMPLICITY_RANK (simpler / more interpretable).
  3. Lower validation Brier score.

Why champion selection prefers simpler models:
  Simpler models (logistic_regression > random_forest > boosting) generalise
  better to unseen data, are easier to debug, require fewer compute resources,
  and are more interpretable for business stakeholders. The tolerance band ensures
  we do not sacrifice statistically significant performance for simplicity —
  we only prefer simplicity when performance is within the tolerance of the best.

Pipeline position: called by train_champion() in champion.py.
Workflow stage: training.
Key invariants:
  - Selection score prefers CV mean PR-AUC (from stability analysis) over
    single-holdout validation PR-AUC when stability data is available.
  - The test split is NEVER used in selection decisions.
  - A fallback to single-split max validation PR-AUC exists (select_champion_candidate_legacy).
"""

from __future__ import annotations

from typing import Any

from modeling.config import (
    CHAMPION_PR_AUC_TOLERANCE_ABS,
    CHAMPION_PR_AUC_TOLERANCE_REL,
    MODEL_SIMPLICITY_RANK,
)


def _pr_auc_score(
    candidate: dict[str, Any],
    stability: dict[str, Any] | None,
) -> float:
    """Get the PR-AUC selection score for a candidate.

    Prefers CV mean PR-AUC (from stability analysis) over single-holdout validation
    PR-AUC when stability data is available. The CV mean is more robust because it
    averages across multiple train/val splits.

    Args:
        candidate: Candidate result dict with 'family' and 'validation_ranking'.
        stability: Optional stability summary from run_cv_stability().

    Returns:
        PR-AUC score (float). Returns -1 if no metric is available.
    """
    fam = candidate["family"]
    if stability and fam in stability.get("by_family", {}):
        agg = stability["by_family"][fam]
        if "pr_auc" in agg:
            return float(agg["pr_auc"]["mean"])
    return float(candidate.get("validation_ranking", {}).get("pr_auc", -1))


def _pr_auc_std(candidate: dict[str, Any], stability: dict[str, Any] | None) -> float:
    """Get the PR-AUC standard deviation across CV folds for a candidate.

    Used as a stability tie-breaker: lower std = more stable across different
    train/val splits.

    Args:
        candidate: Candidate result dict with 'family'.
        stability: Optional stability summary from run_cv_stability().

    Returns:
        PR-AUC std (float). Returns 999.0 (high penalty) if stability data unavailable.
    """
    fam = candidate["family"]
    if stability and fam in stability.get("by_family", {}):
        agg = stability["by_family"][fam]
        if "pr_auc" in agg:
            return float(agg["pr_auc"]["std"])
    return 999.0


def select_champion_with_tolerance(
    candidates: list[dict[str, Any]],
    stability: dict[str, Any] | None = None,
    *,
    abs_tolerance: float = CHAMPION_PR_AUC_TOLERANCE_ABS,
    rel_tolerance: float = CHAMPION_PR_AUC_TOLERANCE_REL,
    prefer_stable: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select the champion model using a PR-AUC tolerance band with simplicity/stability preference.

    Selection process:
      1. Filter to valid candidates (those with a trained 'model' key).
      2. Score each candidate (prefer CV mean PR-AUC over holdout validation PR-AUC).
      3. Find the best PR-AUC score among all candidates.
      4. Compute the tolerance floor: max(best - abs_tolerance, best * (1 - rel_tolerance)).
      5. Keep only candidates whose score >= floor (eligible pool).
      6. Among eligible candidates, pick the winner by minimising:
         (a) PR-AUC CV std (prefer_stable=True, default)
         (b) MODEL_SIMPLICITY_RANK (lower = simpler)
         (c) Validation Brier score (lower = better calibrated)

    Args:
        candidates: List of candidate result dicts (from _score_candidate).
        stability: Optional stability summary dict from run_cv_stability().
        abs_tolerance: Absolute PR-AUC tolerance (default 0.01).
        rel_tolerance: Relative PR-AUC tolerance (default 0.02).
        prefer_stable: If True (default), prefer lower CV std over simplicity.
            If False, skip the stability tie-breaker.

    Returns:
        Tuple of (winner_candidate_dict, selection_rationale_dict). The rationale
        includes the winner, eligible pool, per-candidate ranking, and the
        preference order explanation.

    Raises:
        RuntimeError: If no valid candidates with trained models remain.

    Side effects: None (pure computation).
    """
    valid = [c for c in candidates if "model" in c]
    if not valid:
        raise RuntimeError("No valid candidates for selection")

    scored = []
    for c in valid:
        pr = _pr_auc_score(c, stability)
        scored.append(
            {
                "candidate": c,
                "family": c["family"],
                "pr_auc_selection_score": pr,
                "pr_auc_cv_std": _pr_auc_std(c, stability),
                "validation_pr_auc": c.get("validation_ranking", {}).get("pr_auc"),
                "validation_brier": c.get("validation_ranking", {}).get("brier_score"),
                "simplicity_rank": MODEL_SIMPLICITY_RANK.get(c["family"], 99),
            }
        )

    best_pr = max(s["pr_auc_selection_score"] for s in scored)
    floor = max(best_pr - abs_tolerance, best_pr * (1.0 - rel_tolerance))
    eligible = [s for s in scored if s["pr_auc_selection_score"] >= floor]

    if prefer_stable:
        winner_entry = min(
            eligible,
            key=lambda s: (
                s["pr_auc_cv_std"],
                s["simplicity_rank"],
                s.get("validation_brier") or 999,
            ),
        )
    else:
        winner_entry = min(
            eligible,
            key=lambda s: (s["simplicity_rank"], s.get("validation_brier") or 999),
        )

    rationale = {
        "rule": "simplest_stable_within_pr_auc_tolerance",
        "best_pr_auc_score": best_pr,
        "tolerance_floor": floor,
        "abs_tolerance": abs_tolerance,
        "rel_tolerance": rel_tolerance,
        "eligible_families": [s["family"] for s in eligible],
        "winner_family": winner_entry["family"],
        "winner_pr_auc_score": winner_entry["pr_auc_selection_score"],
        "winner_pr_auc_cv_std": winner_entry["pr_auc_cv_std"],
        "winner_simplicity_rank": winner_entry["simplicity_rank"],
        "preference_order": (
            "Within tolerance → lower fold PR-AUC std → simpler model → lower Brier"
        ),
        "candidates_ranked": sorted(
            scored,
            key=lambda s: (-s["pr_auc_selection_score"], s["simplicity_rank"]),
        ),
        "stability_used": stability is not None,
    }
    return winner_entry["candidate"], rationale


def select_champion_candidate_legacy(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Single-split winner: max validation PR-AUC (legacy method).

    No tolerance band, no simplicity preference. Kept for:
      - Backward compatibility with notebooks / tests that expect this behaviour.
      - Comparison runs where we want to see the difference between
        legacy (max PR-AUC) and preferred (tolerance + simplicity) selection.

    Args:
        candidates: List of candidate result dicts.

    Returns:
        The candidate dict with the highest validation PR-AUC (tie-break: lower Brier).
    """
    valid = [c for c in candidates if "model" in c]
    return max(
        valid,
        key=lambda c: (
            c["validation_ranking"]["pr_auc"],
            -c["validation_ranking"]["brier_score"],
        ),
    )
