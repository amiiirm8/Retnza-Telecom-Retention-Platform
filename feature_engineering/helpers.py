"""\nStateless helpers for row-level feature engineering (Feature engineering layer).

This module contains pure functions that transform individual pandas
Series or DataFrames into engineered feature values.  Every function
is deterministic (no random seeds, no fitted state) and operates
solely on its inputs — no side effects, no I/O.

Design rationale for separating helpers from builders:
  - Helpers are unit-testable in isolation without instantiating the
    full pipeline.
  - Business logic (tri-state encoding, yes/no scoring, age bucketing)
    lives in one place and is reused across layers.
  - The module boundary enforces that builders compose helpers rather
    than duplicating row-level transformations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from preprocessing.config import PERSIAN_MONTH_ORDER
from preprocessing.text import normalize_series_tokens

from feature_engineering.constants import STRUCTURAL_NA


def ensure_int8(series: pd.Series) -> pd.Series:
    """Cast a Series to ``int8`` without changing values.

    Exists as a named helper so that callers can express intent and so
    that a single point of change exists if storage dtype ever changes.

    Args:
        series: Input pandas Series (must have values representable in int8).

    Returns:
        Series cast to ``int8``.

    Raises:
        ValueError: If values overflow int8 range (-128 to 127).
    """
    return series.astype("int8")


def yes_no_flag(series: pd.Series) -> pd.Series:
    """Binary (non-tri-state) yes/no encoding.

    Used for columns like ``operator_app_usage`` where the source data
    has no ``no_data_service`` value, so the binary 0/1 is semantically
    unambiguous (no -1 sentinel needed).

    Args:
        series: Column with values ``"yes"``, ``"no"``, or similar.

    Returns:
        ``int8`` Series: 1 where value == ``"yes"``, 0 otherwise.
    """
    return series.eq("yes").astype("int8")


def tri_state_adoption_flag(series: pd.Series, capable: pd.Series) -> pd.Series:
    """Tri-state adoption encoding for VAS / ecosystem columns.

    Returns int8:
      1 = yes (active adoption on data-capable network)
      0 = no  (eligible but not adopted)
     -1 = structural N/A (2G / no_data_service — not equivalent to no)

    Why three states instead of two?
      A 2G subscriber with ``no_data_service`` has **no ability** to adopt
      VAS products.  Encoding this as 0 would conflate them with 4G users
      who have data service but chose not to adopt — two fundamentally
      different populations that a churn model must distinguish.

    Args:
        series: Column with values ``"yes"``, ``"no"``, or ``"no_data_service"``.
        capable: Boolean mask where ``True`` means the subscriber is on
            a data-capable network (3G+).

    Returns:
        ``int8`` Series with values in {-1, 0, 1}.
    """
    out = pd.Series(STRUCTURAL_NA, index=series.index, dtype="int8")
    out[capable & series.eq("yes")] = 1
    out[capable & series.eq("no")] = 0
    # Rows with no_data_service on non-capable (2G) remain -1
    return out


def yes_only_binary_score(series: pd.Series, capable: pd.Series | None = None) -> pd.Series:
    """Score whether a service is adopted (1), else 0.

    Unlike :func:`tri_state_adoption_flag`, this function does **not**
    emit -1 for non-capable rows.  It is used inside summation contexts
    (e.g. ``digital_engagement_score``) where -1 would artificially
    reduce the sum and misrepresent non-capable subscribers as having
    "negative" engagement.

    When ``capable`` is ``None`` (e.g. ``operator_app_usage``, which has
    no ``no_data_service`` state), the series is simply treated as binary.

    Args:
        series: Column with values ``"yes"``, ``"no"``, or ``"no_data_service"``.
        capable: Optional boolean mask; if given, only capable & yes rows
            score 1; all others score 0.

    Returns:
        ``int8`` Series: 1 if adopted, 0 otherwise.
    """
    if capable is None:
        return series.eq("yes").astype("int8")
    score = pd.Series(0, index=series.index, dtype="int8")
    score[capable & series.eq("yes")] = 1
    return score


def count_yes_among_capable(df: pd.DataFrame, columns: list[str], capable: pd.Series) -> pd.Series:
    """Count how many of the given columns are ``"yes"`` for capable subscribers.

    Non-capable rows receive ``STRUCTURAL_NA`` (-1) because a count of 0
    would be misleading — it would imply the subscriber evaluated all
    services and chose none, when in fact they had no opportunity to adopt.

    Args:
        df: DataFrame containing the columns to evaluate.
        columns: Subset of column names to count.
        capable: Boolean mask for data-capable subscribers.

    Returns:
        ``int8`` Series: count (0..len(columns)) for capable, -1 otherwise.
    """
    yes_mask = df[columns].eq("yes")
    count = yes_mask.sum(axis=1).astype("int8")
    return np.where(capable, count, STRUCTURAL_NA).astype("int8")


def lifetime_arpu(cumulative: pd.Series, tenure_months: pd.Series) -> pd.Series:
    """Compute lifetime Average Revenue Per User (ARPU).

    Formula: ``cumulative_spend / max(tenure_in_months, 1)``.

    The denominator is clamped to a minimum of 1 to avoid division by zero
    for new subscribers (tenure = 0) while still producing a meaningful per-
    month spend value.  The raw spend columns are never mutated.

    Args:
        cumulative: Total cumulative spend (toman).
        tenure_months: SIM tenure in months (may contain 0 or negative
            values from data-entry errors).

    Returns:
        ``float64`` Series: lifetime ARPU in toman per month.
    """
    denom = np.maximum(tenure_months.clip(lower=0), 1)
    return (cumulative / denom).astype("float64")


def birth_month_to_ordinal(series: pd.Series) -> pd.Series:
    """Map Persian month name to ordinal 1..12.

    Used for demographic explainability (SHAP can surface "born in month X")
    rather than for cyclic seasonality modeling — hence ordinal encoding is
    sufficient.

    Args:
        series: Column containing Persian month names (e.g. ``"Farvardin"``).

    Returns:
        ``int8`` Series with values 1 (Farvardin) through 12 (Esfand).

    Raises:
        ValueError: If any month name cannot be mapped (most likely due to
            unexpected tokens surviving the cleaning stage).
    """
    normalized = normalize_series_tokens(series)
    mapped = normalized.map(PERSIAN_MONTH_ORDER)
    if mapped.isna().any():
        bad = normalized[mapped.isna()].unique()[:5]
        raise ValueError(f"Unknown birth_month_persian tokens: {bad}")
    return mapped.astype("int8")


def age_to_bucket(age: pd.Series) -> pd.Series:
    """Map numeric age to ordinal age segment.

    Buckets (determined by domain conventions for the Iranian telecom market):
      0 = youth       (age ≤ 25)
      1 = young adult (26 – 35)
      2 = adult       (36 – 55)
      3 = senior      (≥ 56)

    The lower bin edge of -1 ensures that age=0 or negative ages (data
    entry errors) are assigned to bucket 0 rather than producing NaN.

    Import is deferred to this function's body to avoid circular dependency
    (helpers are imported by constants during module initialisation).

    Args:
        age: Numeric Series of subscriber ages.

    Returns:
        ``int8`` Series with values in {0, 1, 2, 3}.
    """
    from feature_engineering.constants import (
        AGE_ADULT_MAX,
        AGE_YOUNG_ADULT_MAX,
        AGE_YOUTH_MAX,
    )

    return pd.cut(
        age,
        bins=[-1, AGE_YOUTH_MAX, AGE_YOUNG_ADULT_MAX, AGE_ADULT_MAX, 200],
        labels=[0, 1, 2, 3],
    ).astype("int8")
