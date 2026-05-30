"""\nValidation gates for featured output (Feature engineering layer).

This module provides runtime validation of the featured DataFrame before
it is passed to model training or inference.  It enforces the contract
defined by the feature registry and the cleaning pipeline.

Workflow stage : governance (gating step between feature engineering and
                 model training / inference).

Key invariants checked:
  - Row count matches the expected value (when provided).
  - All cleaned input columns and all model feature columns are present.
  - ``churn_binary`` contains no null values (label leakage guard).
  - Tri-state invariant: on 2G (``is_data_capable == 0``), service flags
    must be ``STRUCTURAL_NA`` (-1), never 0 or 1.
  - Raw cleaned columns on 2G rows must retain ``"no_data_service"``
    (not silently collapsed).
  - Float features have float dtypes (not object or int).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from feature_engineering.constants import (
    CLEANED_INPUT_COLUMNS,
    FE_VALIDATION_VERSION,
    STRUCTURAL_NA,
)
from feature_engineering.registry import MODEL_FEATURE_COLUMNS


class FeatureEngineeringValidationError(ValueError):
    """Raised when a featured DataFrame fails validation.

    Carries structured ``details`` (errors, warnings, metrics) so that
    upstream orchestrators can log or surface the full failure context
    rather than relying on a message string alone.

    Attributes:
        details: Dict with ``"errors"`` (list), ``"warnings"`` (list),
            and ``"metrics"`` (dict) from the validation report.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


@dataclass
class FeatureValidationReport:
    """Accumulates validation results and timing for the featured DataFrame.

    Usage::

        report = FeatureValidationReport()
        if some_check_fails:
            report.fail("...")
        report.raise_if_failed()   # raises FeatureEngineeringValidationError on failure

    Design notes:
      - Warnings do not cause failure (intended for soft checks like
        "unexpectedly high null count" in future iterations).
      - ``started_at`` is set once at construction (via ``time.monotonic``),
        so elapsed time always measures the full validation duration.
      - ``finish()`` is called automatically by ``raise_if_failed()`` but
        can also be called manually to finalise metrics without raising.

    Attributes:
        passed: Overall validation status.
        errors: Fatal issues that violate the feature contract.
        warnings: Non-fatal observations.
        metrics: Timestamps, row counts, and validation version.
        started_at: Monotonic timestamp of creation.
        elapsed_ms: Wall-clock duration of validation (set by ``finish()``).
    """
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)
    elapsed_ms: float = 0.0

    def fail(self, msg: str) -> None:
        """Record a validation failure.

        Sets ``passed`` to ``False`` and appends ``msg`` to the errors list.

        Args:
            msg: Description of the violation.
        """
        self.passed = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        """Record a non-fatal warning.

        Does not affect ``passed`` status.

        Args:
            msg: Description of the observation.
        """
        self.warnings.append(msg)

    def finish(self) -> None:
        """Finalise metrics: record elapsed time and validation version.

        Call this before reading ``elapsed_ms`` or before serialising
        the report.  Called automatically by ``raise_if_failed()``.
        """
        self.elapsed_ms = round((time.monotonic() - self.started_at) * 1000, 2)
        self.metrics["validation_version"] = FE_VALIDATION_VERSION

    def raise_if_failed(self) -> None:
        """Raise ``FeatureEngineeringValidationError`` if any failures exist.

        Always calls ``finish()`` first so that elapsed time is captured
        even in the error case.

        Raises:
            FeatureEngineeringValidationError: If ``passed`` is ``False``,
                with all errors, warnings, and metrics attached.
        """
        self.finish()
        if not self.passed:
            raise FeatureEngineeringValidationError(
                "; ".join(self.errors),
                details={"errors": self.errors, "warnings": self.warnings, "metrics": self.metrics},
            )


def validate_featured_frame(
    df: pd.DataFrame,
    *,
    expected_rows: int | None = None,
) -> FeatureValidationReport:
    """Validate a featured DataFrame against the model contract.

    This is the primary validation gate called after
    :func:`build_features` completes.  It checks:

      1. Row count matches expectation (optional).
      2. All cleaned input columns and all model feature columns exist.
      3. ``churn_binary`` has no nulls.
      4. Tri-state encoding invariant: on 2G rows, engineered tri-state
         flags must be ``STRUCTURAL_NA`` (-1).
      5. Raw ``superapp_social`` column on 2G rows still says
         ``"no_data_service"`` (not silently collapsed).
      6. Float features have a float dtype (not object or int).

    Non-fatal warnings are not currently emitted but the report structure
    supports them for future soft checks (e.g. "feature X has 99% zeros").

    Args:
        df: The featured DataFrame to validate.
        expected_rows: If given, the DataFrame must have exactly this
            many rows (catches partial pipeline runs).

    Returns:
        A ``FeatureValidationReport`` with pass/fail status, errors,
        warnings, timing, and metrics.

    Raises:
        FeatureEngineeringValidationError: Auto-raised if the caller
            invokes ``report.raise_if_failed()``.  This function itself
            does not raise — it returns the report for inspection.
    """
    report = FeatureValidationReport()
    report.metrics["n_rows"] = int(len(df))
    report.metrics["n_columns"] = int(len(df.columns))

    if expected_rows is not None and len(df) != expected_rows:
        report.fail(f"Row count {len(df)} != expected {expected_rows}")

    # Check that all columns from the cleaning stage survived the feature
    # build without accidental dropping.
    missing_cleaned = [c for c in CLEANED_INPUT_COLUMNS if c not in df.columns]
    if missing_cleaned:
        report.fail(f"Missing cleaned columns in featured output: {missing_cleaned}")

    # Check that all expected model feature columns are present.
    missing_model = [c for c in MODEL_FEATURE_COLUMNS if c not in df.columns]
    if missing_model:
        report.fail(f"Missing model feature columns: {missing_model}")

    # Label must never be null in the training/inference frame.
    if "churn_binary" in df.columns and df["churn_binary"].isna().any():
        report.fail("Null churn_binary in featured frame")

    # Tri-state flags: on 2G, service flags must be STRUCTURAL_NA (-1)
    # This invariant guarantees that no subscriber who lacked data service
    # is misrepresented as a "no" (eligible but declined).
    if "is_data_capable" in df.columns and "rubika_user_flag" in df.columns:
        is_2g = df["is_data_capable"] == 0
        bad = is_2g & df["rubika_user_flag"].ne(STRUCTURAL_NA)
        if bad.any():
            report.fail(
                f"rubika_user_flag must be {STRUCTURAL_NA} on 2G; found {int(bad.sum())} violations"
            )

    # No silent collapse: raw superapp still has no_data_service on 2G.
    # If the cleaning pipeline erroneously collapses no_data_service to
    # "no", this check catches it.
    if "mobile_data_generation" in df.columns:
        g2 = df["mobile_data_generation"] == "2G"
        if g2.any() and "superapp_social" in df.columns:
            invalid = g2 & ~df["superapp_social"].eq("no_data_service")
            if invalid.any():
                report.fail("2G rows must retain no_data_service on superapp_social in cleaned cols")

    # Float features must not be object or int — catch accidental
    # dtype upcasting from numpy operations.
    float_feats = [
        "lifetime_arpu_toman",
        "monthly_to_lifetime_arpu_ratio",
        "log_monthly_spend_toman",
        "spend_intensity_score",
    ]
    for col in float_feats:
        if col in df.columns and not np.issubdtype(df[col].dtype, np.floating):
            report.fail(f"{col}: expected float dtype, got {df[col].dtype}")

    report.metrics["model_feature_count"] = len(MODEL_FEATURE_COLUMNS)
    return report
