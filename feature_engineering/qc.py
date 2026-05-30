"""\nQC artifacts for feature engineering (Feature engineering layer).

This module produces quality-control (QC) and governance artefacts for
the feature-engineering pipeline.  It is invoked **after**
:func:`build_features` completes and is purely a reporting / observability
concern — it never modifies the featured DataFrame.

Workflow stage : reporting / governance (post-training, pre-deployment).
Key outputs   :
  - ``feature_summary.json`` — descriptive statistics per feature.
  - ``feature_group_registry.json`` — frozen snapshot of the feature
    registry and group assignments.
  - ``feature_value_counts_*.csv`` — value distributions per feature.
  - ``churn_rate_by_*.csv`` — churn rate conditioned on each feature.
  - ``plot_dist_*.png`` — optional bar plots (if matplotlib is available).
  - ``feature_qc_index.json`` — manifest of all generated artefacts.

The reporter is designed to be safe for non-essential failures: missing
columns produce "skipped" status entries rather than raising exceptions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from feature_engineering.constants import FEATURE_QC_DIR
from feature_engineering.registry import (
    MODEL_FEATURE_COLUMNS,
    MODEL_FEATURE_GROUPS,
    get_feature_metadata,
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureQCArtifact:
    """A single artefact produced by the QC reporter.

    Each artefact represents one output file (or one status entry when
    a file was skipped).  Artefacts are collected in a list and written
    to the QC index manifest at the end of the QC run, providing a
    machine-readable record of what was produced and why.

    Attributes:
        name: Human-readable identifier (e.g. ``"feature_summary"``).
        path: Absolute or relative filesystem path.  Empty string when
            ``status != "written"``.
        kind: Type of artefact (csv, json, png, or status for entries
            that do not produce a file).
        status: Outcome: ``"written"`` (file saved), ``"skipped"``
            (optional feature omitted), or ``"missing_column"`` (column
            not found in the DataFrame).
        detail: Optional context string (e.g. reason for skipping).
    """
    name: str
    path: str
    kind: Literal["csv", "json", "png", "status"]
    status: Literal["written", "skipped", "missing_column"] = "written"
    detail: str | None = None


class FeatureQCReporter:
    """Generates and persists quality-control artefacts for the feature pipeline.

    Usage::

        reporter = FeatureQCReporter()
        reporter.save_feature_summary(featured_df)
        reporter.save_group_registry()
        reporter.save_value_counts(featured_df, MODEL_FEATURE_COLUMNS)
        reporter.save_churn_by_feature(featured_df, "tenure_bucket")
        reporter.maybe_plot_feature(featured_df, "revenue_risk_segment")
        result = reporter.finalize()    # writes index, returns summary

    The reporter is designed to never raise for missing columns or failed
    plots — it records the failure in the artefact manifest and continues.

    Attributes:
        output_dir: Directory where files are written (defaults to
            ``FEATURE_QC_DIR`` from constants).
        write_plots: If ``True``, attempt matplotlib bar plots for
            categorical features.
    """

    def __init__(self, output_dir: Path | None = None, write_plots: bool = True) -> None:
        """Initialise the QC reporter.

        Args:
            output_dir: Target directory for artefacts.  Created
                automatically if it does not exist.
            write_plots: Enable distribution bar plots (requires
                ``matplotlib``).  Set ``False`` in headless or
                containerised environments.
        """
        self.output_dir = Path(output_dir or FEATURE_QC_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.write_plots = write_plots
        self._artifacts: list[FeatureQCArtifact] = []

    def _register(
        self,
        name: str,
        path: Path | None,
        kind: Literal["csv", "json", "png", "status"],
        status: Literal["written", "skipped", "missing_column"] = "written",
        detail: str | None = None,
    ) -> None:
        """Record an artefact in the internal manifest.

        Args:
            name: Artefact identifier (used in index and duplicate-safe).
            path: Filesystem path; ``None`` for non-file entries.
            kind: Type classification.
            status: Outcome of the generation attempt.
            detail: Optional commentary (e.g. "column Y not found").
        """
        self._artifacts.append(
            FeatureQCArtifact(
                name=name,
                path=str(path) if path else "",
                kind=kind,
                status=status,
                detail=detail,
            )
        )

    def save_feature_summary(self, df: pd.DataFrame) -> Path:
        """Compute and persist descriptive statistics for all model features.

        Produces ``feature_summary.json`` with per-column mean, std,
        min, max, and null count.  Only numeric columns (as identified
        by ``pd.DataFrame.select_dtypes``) are included; non-numeric
        feature columns are silently skipped.

        Args:
            df: The featured DataFrame to summarise.

        Returns:
            Path to the written JSON file.
        """
        path = self.output_dir / "feature_summary.json"
        numeric = df[MODEL_FEATURE_COLUMNS].select_dtypes(include=["number"])
        summary: dict[str, Any] = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_rows": int(len(df)),
            "n_model_features": len(MODEL_FEATURE_COLUMNS),
            "numeric_features": {},
        }
        for col in numeric.columns:
            s = numeric[col]
            summary["numeric_features"][col] = {
                "mean": round(float(s.mean()), 4) if s.notna().any() else None,
                "std": round(float(s.std()), 4) if s.notna().any() else None,
                "min": float(s.min()) if s.notna().any() else None,
                "max": float(s.max()) if s.notna().any() else None,
                "null_count": int(s.isna().sum()),
            }
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self._register("feature_summary", path, "json")
        return path

    def save_group_registry(self) -> Path:
        """Persist a frozen snapshot of the feature registry and groups.

        This artefact serves as a governance record: it captures which
        features were expected, their layers/families, and how they are
        grouped at the time the QC was run.

        Returns:
            Path to the written JSON file.
        """
        path = self.output_dir / "feature_group_registry.json"
        payload = {
            "groups": MODEL_FEATURE_GROUPS,
            "registry": get_feature_metadata(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._register("feature_group_registry", path, "json")
        return path

    def save_value_counts(self, df: pd.DataFrame, columns: list[str], max_cols: int = 20) -> None:
        """Write value-count CSV files for each requested column.

        For each column (up to ``max_cols``), a CSV with the top-20
        value-frequency pairs is written.  Columns not present in
        ``df`` produce a ``missing_column`` status entry and are
        silently skipped.

        Args:
            df: Featured DataFrame.
            columns: Columns to profile.  Only the first ``max_cols``
                are processed to avoid excessive I/O on very wide frames.
            max_cols: Maximum number of columns to process.
        """
        for col in columns[:max_cols]:
            if col not in df.columns:
                self._register(
                    f"feature_value_counts_{col}",
                    None,
                    "status",
                    status="missing_column",
                )
                continue
            vc = df[col].astype(str).value_counts(dropna=False).head(20)
            out = pd.DataFrame({"value": vc.index.astype(str), "count": vc.values.astype(int)})
            path = self.output_dir / f"feature_value_counts_{col}.csv"
            out.to_csv(path, index=False)
            self._register(f"feature_value_counts_{col}", path, "csv")

    def save_churn_by_feature(self, df: pd.DataFrame, feature: str) -> Path | None:
        """Compute and persist churn rate per level of a categorical feature.

        Groups the DataFrame by ``feature`` and calculates the mean
        churn rate (``churn_binary``) and row count per group.

        Args:
            df: Featured DataFrame containing both ``feature`` and
                ``churn_binary``.
            feature: Categorical column to condition on.

        Returns:
            Path to the written CSV, or ``None`` if ``churn_binary``
            or ``feature`` is missing.
        """
        if "churn_binary" not in df.columns or feature not in df.columns:
            self._register(
                f"churn_rate_by_{feature}",
                None,
                "status",
                status="missing_column",
            )
            return None
        ct = (
            df.groupby(feature, observed=True)["churn_binary"]
            .agg(["mean", "count"])
            .reset_index()
        )
        ct.columns = [feature, "churn_rate", "count"]
        path = self.output_dir / f"churn_rate_by_{feature}.csv"
        ct.to_csv(path, index=False)
        self._register(f"churn_rate_by_{feature}", path, "csv")
        return path

    def maybe_plot_feature(self, df: pd.DataFrame, feature: str) -> str | None:
        """Optionally generate a distribution bar-plot for a feature.

        Plotting is guarded by ``self.write_plots``, availability of
        ``matplotlib``, and presence of the column in the DataFrame.
        Any failure during plotting (import, rendering) is silently
        swallowed.

        Args:
            df: Featured DataFrame.
            feature: Column to plot (values are cast to string for
                categorical-style bar chart).

        Returns:
            String path to the PNG file, or ``None`` if the plot was
            not generated.
        """
        if not self.write_plots or feature not in df.columns:
            return None
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return None
        fig, ax = plt.subplots(figsize=(5, 3))
        df[feature].astype(str).value_counts().head(10).plot(kind="bar", ax=ax)
        ax.set_title(f"Distribution: {feature}")
        p = self.output_dir / f"plot_dist_{feature}.png"
        fig.tight_layout()
        fig.savefig(p, dpi=100)
        plt.close(fig)
        self._register(f"plot_dist_{feature}", p, "png")
        return str(p)

    def write_index(self) -> Path:
        """Write the QC artefacts index manifest (``feature_qc_index.json``).

        The manifest lists every artefact produced during this reporter's
        lifetime, along with its type and outcome status.  It serves as
        both a table-of-contents and an audit trail.

        Returns:
            Path to the index JSON file.
        """
        path = self.output_dir / "feature_qc_index.json"
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(self.output_dir),
            "artifacts": [a.__dict__ for a in self._artifacts],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def finalize(self) -> dict[str, Any]:
        """Finalise QC: write the index manifest and return a summary.

        Call this as the last step after all ``save_*`` and
        ``maybe_plot_*`` calls.

        Returns:
            Dict with ``"feature_qc_index"`` (path) and
            ``"n_artifacts"`` (count of registered artefacts).
        """
        index_path = self.write_index()
        return {"feature_qc_index": str(index_path), "n_artifacts": len(self._artifacts)}
