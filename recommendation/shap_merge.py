"""Validated SHAP overlay (explanatory only — never drives rule selection).

Merges SHAP feature attribution data into the recommendation DataFrame to
provide narrative explanations for Very High / High risk tier subscribers.

Pipeline stage: inference/reporting-time (called optionally by engine.py
after rule application, before manifest generation).

Key invariants:
  - SHAP does NOT select or modify rule_id, recommended_action, or any
    operational delivery field. It only enriches final_top_driver narrative.
  - SHAP overlay is limited to Very High / High tiers because these are
    the subscribers where model explainability adds stakeholder value.
  - All SHAP fields are validated against the champion schema before merge.
  - If validation fails, the merge is skipped and rule-only explanations
    are preserved without raising an error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modeling.config import CHAMPION_BUNDLE_SCHEMA
from modeling.governance import validate_champion_bundle, validate_shap_parquet
from recommendation.config import COMPATIBLE_SHAP_SCHEMA


def validate_shap_for_merge(
    shap_path: Path,
    bundle: dict[str, Any],
    feature_columns: list[str],
) -> dict[str, Any]:
    """Pre-merge governance check for SHAP parquet compatibility.

    Validates that:
      1. The SHAP parquet file exists and is readable.
      2. The champion bundle passes validation (non-blocking).
      3. Schema versions are compatible.
      4. SHAP feature column count matches champion feature count.
      5. The parquet passes modeling-level SHAP validation.

    Args:
        shap_path: Path to the SHAP values parquet file.
        bundle: Loaded champion model bundle dict.
        feature_columns: List of feature column names from champion.

    Returns:
        Dict with keys:
          path, compatible (bool), warnings (list), errors (list),
          expected_shap_schema, and any shap_* fields from
          validate_shap_parquet.

    Side effects:
        None (read-only file access).
    """
    report: dict[str, Any] = {
        "path": str(shap_path),
        "compatible": True,
        "warnings": [],
        "errors": [],
    }

    if not shap_path.is_file():
        report["compatible"] = False
        report["errors"].append("SHAP parquet not found")
        return report

    # Non-blocking champion bundle validation — schema warnings do not
    # prevent merge but are logged for audit.
    try:
        validate_champion_bundle(bundle, strict=False)
    except Exception as exc:
        report["warnings"].append(f"Champion bundle check: {exc}")

    if bundle.get("schema_version") != CHAMPION_BUNDLE_SCHEMA:
        report["warnings"].append(
            f"Champion schema {bundle.get('schema_version')} != {CHAMPION_BUNDLE_SCHEMA}"
        )

    # Delegate low-level parquet validation to modeling layer.
    shap_rep = validate_shap_parquet(shap_path, feature_columns)
    report.update({f"shap_{k}": v for k, v in shap_rep.items() if k not in report})

    if not shap_rep.get("compatible", True):
        report["compatible"] = False
        report["errors"].extend(shap_rep.get("errors", []))

    # Check feature count consistency between SHAP and champion.
    # Each feature should have one shap_* column.
    n_expected = len(feature_columns)
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(shap_path)
        n_cols = meta.num_columns
        shap_col_count = sum(
            1
            for i in range(n_cols)
            if meta.schema.column(i).name.startswith("shap_")
        )
        if shap_col_count and shap_col_count != n_expected:
            report["compatible"] = False
            report["errors"].append(
                f"SHAP feature count {shap_col_count} != champion {n_expected}"
            )
    except Exception:
        pass

    report["expected_shap_schema"] = COMPATIBLE_SHAP_SCHEMA
    return report


def merge_shap_explanations(
    rec: pd.DataFrame,
    shap_path: Path,
    feature_columns: list[str],
    bundle: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Add SHAP narrative fields to the recommendation DataFrame.

    SHAP values are merged onto the base recommendations and used to set
    final_top_driver ONLY for Very High / High risk tiers. For all other
    tiers, the rule-driven top driver is preserved unchanged.

    Critical design decisions:
      - SHAP does NOT modify rule_id or recommended_action (always rule-driven).
      - SHAP overlay is limited to Very High / High because these are the
        tiers where stakeholders most often ask "why is this subscriber high risk?"
      - final_top_driver_source tracks provenance: "rule" vs "shap_overlay".
      - A backward-compatible alias (top_driver = final_top_driver) is set so
        existing dashboards referencing top_driver continue to work.

    Args:
        rec: Recommendation DataFrame with subscriber_id, risk_tier, etc.
        shap_path: Path to the SHAP values parquet file.
        feature_columns: List of feature column names from champion model.
        bundle: Champion model bundle (used for validation).

    Returns:
        Tuple of (updated DataFrame with SHAP columns, validation report dict).
        If validation fails, returns original rec with rule-only drivers.

    Side effects:
        None (does not write to disk).
    """
    from modeling.explainability import extract_local_shap_drivers

    validation = validate_shap_for_merge(shap_path, bundle, feature_columns)
    if not validation["compatible"]:
        # Incompatible SHAP: preserve rule-only explanations silently.
        # No warnings raised to the caller — the merge is optional.
        rec = rec.copy()
        rec["rule_top_driver"] = rec.get("rule_top_driver", rec.get("top_driver", ""))
        rec["shap_top_driver"] = None
        rec["final_top_driver"] = rec["rule_top_driver"]
        rec["final_top_driver_source"] = "rule"
        return rec, validation

    shap_df = pd.read_parquet(shap_path)
    if "subscriber_id" not in shap_df.columns:
        validation["compatible"] = False
        validation["errors"].append("subscriber_id missing in SHAP parquet")
        rec["final_top_driver_source"] = "rule"
        return rec, validation

    # Build per-subscriber SHAP narrative fields.
    # Each row's SHAP vector is passed to extract_local_shap_drivers which
    # returns the top-3 positive (risk-up) and negative (risk-down) features.
    extras: list[dict[str, Any]] = []
    for _, r in shap_df.iterrows():
        shap_cols = [c for c in r.index if c.startswith("shap_")]
        if not shap_cols:
            extras.append(
                {
                    "shap_top_driver": None,
                    "shap_explanation_summary": None,
                    "shap_risk_up_drivers": None,
                    "shap_risk_down_drivers": None,
                }
            )
            continue
        # Reconstruct SHAP vector in champion feature order.
        shap_vec = [float(r[f"shap_{f}"]) for f in feature_columns if f"shap_{f}" in r.index]
        if len(shap_vec) != len(feature_columns):
            extras.append({"shap_top_driver": None, "shap_explanation_summary": None})
            continue
        detail = extract_local_shap_drivers(np.array(shap_vec), feature_columns, top_k=3)
        top_pos = detail.get("shap_top_positive") or []
        top_neg = detail.get("shap_top_negative") or []
        extras.append(
            {
                "shap_top_driver": top_pos[0]["business_label"] if top_pos else None,
                "shap_explanation_summary": detail.get("explanation_summary"),
                "shap_risk_up_drivers": " | ".join(d["business_label"] for d in top_pos[:2]),
                "shap_risk_down_drivers": " | ".join(d["business_label"] for d in top_neg[:2]),
            }
        )

    shap_extra = pd.DataFrame(extras)
    if shap_extra.empty:
        shap_extra = pd.DataFrame(
            columns=[
                "shap_top_driver",
                "shap_explanation_summary",
                "shap_risk_up_drivers",
                "shap_risk_down_drivers",
            ]
        )
    shap_extra["subscriber_id"] = shap_df["subscriber_id"].values

    drop_cols = [c for c in ("shap_top_driver", "shap_explanation_summary") if c in rec.columns]
    rec_base = rec.drop(columns=drop_cols, errors="ignore")
    out = rec_base.merge(shap_extra, on="subscriber_id", how="left")

    if "rule_top_driver" not in out.columns:
        out["rule_top_driver"] = out.get("top_driver", "")

    for col in ("shap_top_driver", "shap_explanation_summary", "shap_risk_up_drivers", "shap_risk_down_drivers"):
        if col not in out.columns:
            out[col] = None

    # SHAP overlay only for Very High / High tiers.
    # This is a deliberate design choice: for Medium/Low subscribers the
    # rule-driven explanation is sufficient and SHAP may introduce noise.
    overlay = (
        out["shap_top_driver"].notna()
        & out["risk_tier"].isin(["Very High", "High"])
    )
    out["final_top_driver_source"] = "rule"
    out.loc[overlay, "final_top_driver_source"] = "shap_overlay"
    out["final_top_driver"] = out["rule_top_driver"]
    out.loc[overlay, "final_top_driver"] = out.loc[overlay, "shap_top_driver"]

    # Backward-compatible alias for dashboards still using top_driver
    out["top_driver"] = out["final_top_driver"]

    validation["shap_overlay_rows"] = int(overlay.sum())
    validation["shap_overlay_policy"] = (
        "SHAP may replace final_top_driver narrative for Very High / High only; "
        "rule_id and recommended_action remain rule-driven."
    )
    return out, validation
