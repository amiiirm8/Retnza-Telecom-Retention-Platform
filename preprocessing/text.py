"""Unicode-safe text normalization for Persian/English telecom tokens.

Pipeline position:
  Utility module consumed by config.py (build_normalized_lookup),
  pipeline.py (normalize_series_tokens), and validators.py (tolerant matching).
  This is a leaf module with no intra-package dependencies.

Workflow stage:
  **Training + Inference** — normalization is applied identically in both
  stages; there is no learned component.

Key invariants:
  - normalize_text_token is idempotent: applying it twice yields the same result.
  - None/NaN values are mapped to empty string (caller must handle NaN downstream).
  - Persian letter unification (ي->ی, ك->ک, ة->ه) is one-directional:
    input variants are collapsed to canonical Persian forms, never the reverse.
  - build_normalized_lookup raises on key collision to prevent silent mapping loss.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

# Zero-width and format characters that commonly appear in Persian CSV exports
# due to copy-paste from BI tools, web UIs, or mixed encoding pipelines.
# These are invisible to the human eye but break exact string matching.
_INVISIBLE_CHARS = (
    "\u200c",  # ZWNJ (Zero-Width Non-Joiner) — frequent in Persian text
    "\u200d",  # ZWJ (Zero-Width Joiner)
    "\u200e",  # LRM (Left-to-Right Mark)
    "\u200f",  # RLM (Right-to-Left Mark)
    "\ufeff",  # BOM (Byte Order Mark) — sometimes at file start
    "\u00a0",  # NBSP (Non-Breaking Space)
)

# Arabic/Persian letter variants -> canonical Persian forms.
# The Unicode standard encodes some Arabic and Persian letters at different
# code points despite identical visual appearance. We unify them here so that
# "ي" (U+064A, Arabic ya) and "ی" (U+06CC, Persian ye) both match "ی".
_CHAR_VARIANTS = str.maketrans(
    {
        "\u064a": "\u06cc",  # Arabic ya (ي) -> Persian ye (ی)
        "\u0643": "\u06a9",  # Arabic kaf (ك) -> Persian kaf (ک)
        "\u0629": "\u0647",  # Arabic teh marbuta (ة) -> Persian heh (ه)
    }
)

_MULTI_SPACE = re.compile(r"\s+")
"""Regex to collapse any sequence of whitespace into a single space."""


def normalize_text_token(value: Any) -> str:
    """Normalize a single categorical/header token for reliable matching.

    The normalization pipeline is:
      1. None/NaN -> empty string (caller is responsible for downstream null handling).
      2. NFKC Unicode normalization (decomposes compatibility characters).
      3. Strip invisible/zero-width characters.
      4. Unify Arabic letter variants into canonical Persian forms.
      5. Collapse multi-run whitespace into one space; strip leading/trailing.

    This function is idempotent: ``normalize_text_token(normalize_text_token(x))``
    produces the same result as a single call.

    Args:
        value: Any scalar value (string, int, float, None, np.nan, pd.NA).

    Returns:
        Normalized string (empty string for None/NaN inputs).
    """
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if pd.isna(value):
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    for ch in _INVISIBLE_CHARS:
        text = text.replace(ch, "")
    text = text.translate(_CHAR_VARIANTS)
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def normalize_column_name(name: Any) -> str:
    """Normalize a CSV header name (Persian label with optional ZWNJ).

    Convenience wrapper around normalize_text_token for readability
    at the call site (pipeline.rename_columns).

    Args:
        name: Raw column header from the CSV.

    Returns:
        Normalized column name string.
    """
    return normalize_text_token(name)


def normalize_series_tokens(series: pd.Series) -> pd.Series:
    """Apply ``normalize_text_token`` element-wise to a pandas Series.

    Preserves the index and dtype (result is always object/string dtype).

    Args:
        series: Series of tokens to normalize.

    Returns:
        Series with each element normalized via normalize_text_token.
    """
    return series.map(normalize_text_token)


def build_normalized_lookup(raw_map: dict[str, str]) -> dict[str, str]:
    """Build a mapping dict with normalized keys for tolerant Persian token matching.

    Normalizes each raw key and raises a ValueError if two different raw
    keys normalize to the same string (which would cause silent mapping loss).

    Args:
        raw_map: Raw key -> canonical value pairs (e.g. {"مرد": "male"}).

    Returns:
        Dict with normalized keys.

    Raises:
        ValueError: If two raw keys normalize to the same string but map
            to different canonical values.
    """
    out: dict[str, str] = {}
    for raw_key, canonical in raw_map.items():
        key = normalize_text_token(raw_key)
        if key in out and out[key] != canonical:
            raise ValueError(
                f"Normalized key collision: {raw_key!r} and another key -> {key!r}"
            )
        out[key] = canonical
    return out


def normalize_allowed_vocab(allowed: frozenset[str] | set[str]) -> frozenset[str]:
    """Normalize every token in an allowed-vocabulary set for comparison.

    Used by validators to build normalized allowed-value sets on the fly.

    Args:
        allowed: Set of allowed token strings.

    Returns:
        Frozenset with each token normalized via normalize_text_token.
    """
    return frozenset(normalize_text_token(v) for v in allowed)
