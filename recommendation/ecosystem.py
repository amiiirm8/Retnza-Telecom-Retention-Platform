"""Ecosystem segmentation and analytics (Rubika / EWANO / Hamrah Man / VoLTE).

Computes subscriber-level ecosystem attributes (product adoption, engagement
level, segment taxonomy) and aggregate analytics dashboards.

Pipeline stage: inference/reporting-time (called by engine.py during
recommendation generation).

Key invariants:
  - Flags use a tri-state system: 1 = adopted, 0 = capable non-adopter,
    -1 = structural N/A (e.g. 2G subscribers who cannot use an app).
    This preserves the distinction between "opted out" and "cannot adopt".
  - All wording in analytics is associative (e.g. "is associated with")
    because ecosystem product adoption is correlated with other engagement
    factors; no causal claims are made.
  - Column names are registry-aligned constants, not hardcoded strings.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Registry-aligned column names only — no hardcoded legacy feature sets.
COL_RUBIKA = "rubika_user_flag"
COL_EWANO = "ewano_user_flag"
COL_HAMRAHMAN = "hamrahman_user_flag"
COL_VOLTE = "volte_user_flag"
COL_DIGITAL = "digital_engagement_score"
COL_ECO_COUNT = "ecosystem_service_count"
COL_CAPABLE = "is_data_capable"
COL_PREPAID = "is_prepaid"


def _active(flag: pd.Series) -> pd.Series:
    """Identify active adopters of a product.

    The tri-state flag system:
      - 1  = adopted (active user)
      - 0  = capable non-adopter (user can adopt but has not)
      - -1 = structural N/A (e.g. 2G subscriber who cannot install the app)

    Preserving -1 as False (not adopted) while keeping it distinct from 0
    allows downstream gap analysis to distinguish "opted out" from "cannot".

    Args:
        flag: Column with values in {-1, 0, 1}.

    Returns:
        Boolean Series: True where flag == 1.
    """
    return flag == 1


def _non_adopter(flag: pd.Series, capable: pd.Series) -> pd.Series:
    """Identify capable subscribers who have not adopted a product.

    Args:
        flag: Product adoption flag ({-1, 0, 1}).
        capable: Boolean indicator of data capability.

    Returns:
        Boolean Series: True where flag is 0 AND subscriber is capable.
    """
    return (flag == 0) & (capable == 1)


def compute_ecosystem_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add ecosystem segmentation columns for CRM / dashboards.

    Computed fields:
      - has_rubika, has_ewano, has_hamrahman, has_volte: binary adoption flags.
      - ecosystem_product_count: count of adopted products (0-4).
      - ecosystem_engagement_level: categorical from digital_engagement_score.
      - ecosystem_segment: taxonomy label (e.g. fully_embedded, wallet_only).
      - ecosystem_risk_gap: capable but <=1 product and low digital score.
      - ecosystem_retention_strategy: CRM journey label per segment.

    Args:
        df: Feature-engineered subscriber DataFrame. Must contain at minimum
            the ecosystem flags defined by the COL_* constants. Missing
            columns default to safe sentinels (-1 or 0).

    Returns:
        DataFrame with ecosystem columns, indexed identically to df.

    Side effects:
        None (pure transformation).
    """
    out = pd.DataFrame(index=df.index)
    capable = df[COL_CAPABLE] == 1 if COL_CAPABLE in df.columns else pd.Series(True, index=df.index)

    # Default to -1 (structural N/A) for products that require data capability,
    # so 2G-only subscribers are never counted as "non-adopters" needing onboarding.
    rubika = df.get(COL_RUBIKA, pd.Series(-1, index=df.index))
    ewano = df.get(COL_EWANO, pd.Series(-1, index=df.index))
    # Hamrah Man flag defaults to 0 rather than -1 because it includes USSD
    # (available even on 2G); structural N/A does not apply.
    hamrah = df.get(COL_HAMRAHMAN, pd.Series(0, index=df.index))
    volte = df.get(COL_VOLTE, pd.Series(-1, index=df.index))
    digital = df.get(COL_DIGITAL, pd.Series(0, index=df.index))
    # ecosystem_service_count may have -1 for "unknown" — treat as 0 here
    # since product-level flags handle adoption at individual level.
    eco_count = df.get(COL_ECO_COUNT, pd.Series(0, index=df.index)).replace(-1, 0)

    out["has_rubika"] = _active(rubika).astype(int)
    out["has_ewano"] = _active(ewano).astype(int)
    out["has_hamrahman"] = _active(hamrah).astype(int)
    out["has_volte"] = _active(volte).astype(int)
    out["ecosystem_product_count"] = (
        out["has_rubika"] + out["has_ewano"] + out["has_hamrahman"] + out["has_volte"]
    )

    # Digital engagement score is a 0-4 ordinal — bins align with CRM tiers.
    # The -0.5 / +0.5 boundaries ensure clean integer-to-category mapping
    # (e.g. 0.5 is the upper bound for "none").
    out["ecosystem_engagement_level"] = pd.cut(
        digital.fillna(0).astype(float),
        bins=[-0.5, 0.5, 1.5, 2.5, 10],
        labels=["none", "low", "medium", "high"],
    ).astype(str)

    # Segment taxonomy for storytelling
    # Precedence order matters: more specific segments are checked first.
    # legacy_voice_only (2G) is caught early so it never enters ecosystem logic.
    segments = []
    for i in range(len(df)):
        r, e, h, v = (
            int(out["has_rubika"].iloc[i]),
            int(out["has_ewano"].iloc[i]),
            int(out["has_hamrahman"].iloc[i]),
            int(out["has_volte"].iloc[i]),
        )
        prepaid = int(df[COL_PREPAID].iloc[i]) if COL_PREPAID in df.columns else 0
        cap = int(capable.iloc[i])

        # 2G / voice-only lines have no data ecosystem; upsell path is
        # network migration, not ecosystem onboarding.
        if not cap:
            seg = "legacy_voice_only"
        # Fully embedded: adopted all 4 products — highest loyalty value.
        elif r and e and h and v:
            seg = "fully_embedded"
        # Wallet-only: adopted EWANO but not Rubika or Hamrah Man.
        # Opportunity: cross-sell content and app products.
        elif e and not r and not h:
            seg = "wallet_only"
        # Content-only: adopted Rubika but not EWANO.
        # Opportunity: activate wallet and app.
        elif r and not e:
            seg = "content_only"
        # Prepaid with zero ecosystem adoption — highest churn risk segment.
        elif prepaid and out["ecosystem_product_count"].iloc[i] == 0:
            seg = "non_ecosystem_prepaid"
        # 3+ products but missing at least one — digitally embedded.
        elif out["ecosystem_product_count"].iloc[i] >= 3:
            seg = "digitally_embedded"
        # Data-capable with zero product adoption (postpaid or unknown).
        elif out["ecosystem_product_count"].iloc[i] == 0 and cap:
            seg = "non_ecosystem_capable"
        # Everything else: some adoption but not fully embedded.
        else:
            seg = "partial_ecosystem"
        segments.append(seg)

    out["ecosystem_segment"] = segments

    # Gap flag: capable subscribers with <=1 product AND low digital score.
    # These are the highest-priority targets for ecosystem acquisition —
    # they have data capability but are not yet embedded.
    # The <=1 threshold (not <=0) captures users with exactly one product
    # who may be at risk of single-product dependency.
    out["ecosystem_risk_gap"] = (
        capable
        & (out["ecosystem_product_count"] <= 1)
        & (digital.fillna(0) <= 1)
    ).astype(int)

    # Strategy label for CRM journeys
    # Priority logic: fully_embedded → preserve; gap segments → acquire;
    # partial adopters → cross-sell; high digital → deepen; rest → onboard.
    strategies: list[str] = []
    for seg, gap, eng in zip(
        out["ecosystem_segment"],
        out["ecosystem_risk_gap"],
        out["ecosystem_engagement_level"],
    ):
        if seg == "fully_embedded":
            strategies.append("loyalty_preservation")
        elif seg in ("non_ecosystem_prepaid", "non_ecosystem_capable") and gap:
            strategies.append("ecosystem_acquisition")
        elif seg == "wallet_only":
            strategies.append("cross_sell_content_and_app")
        elif seg == "content_only":
            strategies.append("wallet_and_app_activation")
        elif eng == "high":
            strategies.append("deepen_engagement")
        else:
            strategies.append("digital_onboarding")
    out["ecosystem_retention_strategy"] = strategies

    return out


def _safe_mean(series: pd.Series) -> float:
    """Compute mean safely, returning 0.0 for empty series.

    Args:
        series: Input numeric series.

    Returns:
        Mean value or 0.0 if the series is empty.
    """
    return float(series.mean()) if len(series) else 0.0


def compute_ecosystem_analytics(
    rec: pd.DataFrame,
    fe: pd.DataFrame,
) -> dict[str, Any]:
    """
    Aggregated ecosystem metrics for manifest / dashboards.

    Produces the analytics dict that feeds the recommendation manifest,
    including segmented risk statistics, adoption rates by risk tier,
    and narrative bullets for stakeholders.

    All wording uses associative language (e.g. "is associated with")
    because ecosystem product adoption is correlated with other engagement
    factors — no causal claims are established.

    Args:
        rec: Recommendation DataFrame with rule_id, risk_tier, churn_probability,
            and ecosystem columns.
        fe: Feature-engineered DataFrame with raw ecosystem flags.

    Returns:
        Dict with keys:
            disclaimer, book_mean_calibrated_risk, rubika_usage,
            ewano_usage, hamrahman_usage, volte_usage,
            ecosystem_segment_summary, risk_tier_ecosystem_adoption,
            high_risk_non_ecosystem_subscribers,
            ecosystem_power_user_count,
            prepaid_ecosystem_penetration,
            retention_action_distribution_by_segment,
            narrative_bullets.

    Side effects:
        None. Merges rec with fe internally but does not modify originals.
    """
    merged = rec.merge(
        fe[
            [
                "subscriber_id",
                COL_RUBIKA,
                COL_EWANO,
                COL_HAMRAHMAN,
                COL_VOLTE,
                COL_DIGITAL,
                COL_PREPAID,
                COL_CAPABLE,
            ]
        ].drop_duplicates("subscriber_id"),
        on="subscriber_id",
        how="left",
    )
    p_cal = merged["churn_probability"]
    base_rate = _safe_mean(p_cal)

    def _by_flag(col: str, label: str) -> dict[str, Any]:
        """Build usage stats for a single ecosystem product flag.

        Compares risk between active users (flag==1) and capable
        non-adopters (flag==0 & data_capable==1). Structural N/A
        (-1, e.g. 2G users) is excluded from the comparison because
        those subscribers cannot adopt the product.

        Args:
            col: Column name for the product flag.
            label: Display label for the product.

        Returns:
            Dict with counts, mean risks, and associative wording.
        """
        if col not in merged.columns:
            return {"label": label, "note": "column_missing"}
        active = merged[col] == 1
        inactive = merged[col] == 0
        return {
            "label": label,
            "active_n": int(active.sum()),
            "inactive_capable_n": int(inactive.sum()),
            "mean_calibrated_risk_active": _safe_mean(p_cal[active]),
            "mean_calibrated_risk_inactive_capable": _safe_mean(p_cal[inactive & (merged[COL_CAPABLE] == 1)]),
            "observed_association": (
                f"{label} active subscribers show mean calibrated risk "
                f"{_safe_mean(p_cal[active]):.3f} vs inactive capable "
                f"{_safe_mean(p_cal[inactive & (merged[COL_CAPABLE] == 1)]):.3f} "
                "(associative; not causal)."
            ),
        }

    segment_stats = []
    if "ecosystem_segment" in merged.columns:
        for seg, grp in merged.groupby("ecosystem_segment", observed=True):
            segment_stats.append(
                {
                    "ecosystem_segment": seg,
                    "n": int(len(grp)),
                    "mean_calibrated_risk": _safe_mean(grp["churn_probability"]),
                    "churn_rate_vs_book": _safe_mean(grp["churn_probability"]) / base_rate if base_rate else 0,
                    "share_of_base": len(grp) / len(merged),
                }
            )

    risk_by_tier = {}
    if "risk_tier" in merged.columns:
        for tier, grp in merged.groupby("risk_tier", observed=True):
            risk_by_tier[tier] = {
                "n": int(len(grp)),
                "rubika_adoption_rate": float((grp.get("has_rubika", grp.get(COL_RUBIKA)) == 1).mean())
                if COL_RUBIKA in grp.columns or "has_rubika" in grp.columns
                else None,
                "ewano_adoption_rate": float((grp.get("has_ewano", 0) == 1).mean())
                if "has_ewano" in grp.columns
                else None,
            }

    high_risk = merged["risk_tier"].isin(["Very High", "High"]) if "risk_tier" in merged.columns else pd.Series(False)
    non_eco_high = high_risk & merged.get("ecosystem_segment", "").isin(
        ["non_ecosystem_prepaid", "non_ecosystem_capable"]
    )

    power_users = merged.get("ecosystem_segment", "") == "fully_embedded"

    prepaid = merged[COL_PREPAID] == 1 if COL_PREPAID in merged.columns else pd.Series(False)
    eco_pen = merged.get("has_rubika", 0) | merged.get("has_ewano", 0) | merged.get("has_hamrahman", 0)

    action_by_segment: dict[str, Any] = {}
    if "ecosystem_segment" in merged.columns and "rule_id" in merged.columns:
        for seg, grp in merged.groupby("ecosystem_segment", observed=True):
            action_by_segment[seg] = grp["rule_id"].value_counts().head(5).to_dict()

    return {
        "disclaimer": (
            "Metrics describe observed associations in this snapshot. "
            "They do not establish causal effects of ecosystem products on churn."
        ),
        "book_mean_calibrated_risk": base_rate,
        "rubika_usage": _by_flag(COL_RUBIKA, "Rubika"),
        "ewano_usage": _by_flag(COL_EWANO, "EWANO"),
        "hamrahman_usage": _by_flag(COL_HAMRAHMAN, "Hamrah Man"),
        "volte_usage": _by_flag(COL_VOLTE, "VoLTE"),
        "ecosystem_segment_summary": segment_stats,
        "risk_tier_ecosystem_adoption": risk_by_tier,
        "high_risk_non_ecosystem_subscribers": int(non_eco_high.sum()),
        "ecosystem_power_user_count": int(power_users.sum()),
        "prepaid_ecosystem_penetration": float((prepaid & eco_pen).sum() / max(prepaid.sum(), 1)),
        "retention_action_distribution_by_segment": action_by_segment,
        "narrative_bullets": _ecosystem_narratives(merged, base_rate),
    }


def _ecosystem_narratives(merged: pd.DataFrame, base_rate: float) -> list[str]:
    """Generate stakeholder-facing narrative bullets for the manifest.

    Each bullet uses explicitly associative wording ("is associated with",
    "observed relationship") to avoid implying causation. The bullets
    compare mean calibrated risk across adoption groups.

    Args:
        merged: Merged recommendation + feature DataFrame with ecosystem columns.
        base_rate: Book-level mean calibrated risk for relative context.

    Returns:
        List of human-readable narrative strings.
    """
    bullets: list[str] = []
    if "ecosystem_segment" in merged.columns:
        seg_risk = merged.groupby("ecosystem_segment")["churn_probability"].mean()
        if "fully_embedded" in seg_risk.index and "non_ecosystem_prepaid" in seg_risk.index:
            bullets.append(
                "Subscribers embedded across multiple operator ecosystem products "
                f"show lower mean calibrated risk ({seg_risk.get('fully_embedded', 0):.3f}) "
                f"than non-ecosystem prepaid ({seg_risk.get('non_ecosystem_prepaid', 0):.3f}) "
                "in this snapshot (associated, not causal)."
            )
    if COL_EWANO in merged.columns:
        e_yes = merged[merged[COL_EWANO] == 1]["churn_probability"].mean()
        e_no = merged[(merged[COL_EWANO] == 0) & (merged[COL_CAPABLE] == 1)]["churn_probability"].mean()
        bullets.append(
            f"EWANO adoption is associated with mean calibrated risk {e_yes:.3f} "
            f"vs {e_no:.3f} among capable non-adopters (observed relationship)."
        )
    if COL_RUBIKA in merged.columns:
        r_yes = merged[merged[COL_RUBIKA] == 1]["churn_probability"].mean()
        r_no = merged[(merged[COL_RUBIKA] == 0) & (merged[COL_CAPABLE] == 1)]["churn_probability"].mean()
        bullets.append(
            f"Rubika participation is associated with mean calibrated risk {r_yes:.3f} "
            f"vs {r_no:.3f} for capable non-users (correlated with engagement; not causal)."
        )
    bullets.append(
        "Power users of Rubika, EWANO, Hamrah Man, and VoLTE represent a high-value "
        "retention cohort — prioritize loyalty preservation over acquisition-style offers."
    )
    return bullets
