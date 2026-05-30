"""
DEPRECATED — legacy sklearn ColumnTransformer pipeline (pre feature-schema features).

This module is retained solely for backward compatibility and optional BI/inference
export experiments. It must NOT be used for any champion training, evaluation, or
test metrics.

Current Retnza modeling path:
  data/cleaned → feature_engineering.build_features → MODEL_FEATURE_COLUMNS

Why this module is deprecated:
  The feature schema migrated from an 18-feature sklearn ColumnTransformer contract
  (modeling.feature_transform) to a 47-feature feature_engineering.builders path
  (feature-schema). All champion artifacts using this module are incompatible and blocked
  by governance validation (LEGACY_FEATURE_COUNT_MAX = 25).

Pipeline position: NOT in active pipeline. Skeleton for legacy compatibility only.
Workflow stage: N/A (deprecated).
Key invariants:
  - All functions raise NotImplementedError with DEPRECATION_MESSAGE.
  - MODEL_INPUT_COLUMNS is intentionally empty to prevent accidental use.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

DEPRECATION_MESSAGE = (
    "modeling.feature_transform is DEPRECATED for champion modeling. "
    "Use feature_engineering.builders.build_features() and MODEL_FEATURE_COLUMNS. "
    "See data/features/subscribers_featured.parquet."
)


def _warn_deprecated() -> None:
    """Emit a DeprecationWarning with the deprecation message.

    Called by all public stubs before raising NotImplementedError.
    """
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)


# Minimal stubs — full legacy implementation removed from active path.
MODEL_INPUT_COLUMNS: list[str] = []  # intentionally empty; do not use


def prepare_model_input_frame(*args: Any, **kwargs: Any):
    """DEPRECATED: Prepare model input frame from raw data.

    Raises NotImplementedError with migration instructions.
    """
    _warn_deprecated()
    raise NotImplementedError(DEPRECATION_MESSAGE)


def fit_preprocessors(*args: Any, **kwargs: Any):
    """DEPRECATED: Fit sklearn preprocessors on training data.

    Raises NotImplementedError with migration instructions.
    """
    _warn_deprecated()
    raise NotImplementedError(DEPRECATION_MESSAGE)


def export_inference_features(*args: Any, **kwargs: Any) -> Path:
    """DEPRECATED: Export inference features for production scoring.

    Raises NotImplementedError with migration instructions to
    scripts/export_inference_features.py.
    """
    _warn_deprecated()
    raise NotImplementedError(
        f"{DEPRECATION_MESSAGE} Use scripts/export_inference_features.py only after migration."
    )
