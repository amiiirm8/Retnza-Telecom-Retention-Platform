"""QC summaries, artifact registry, and optional lightweight plots for preprocessing.

Pipeline position:
  Consumed by pipeline.run_preprocessing to log step-level metadata and
  produce inspectable artifacts. The QCReporter is not used during modeling.

Workflow stage:
  **Reporting + Governance** — QC artifacts document what happened during
  preprocessing for data scientists, auditors, and downstream consumers.

Key invariants:
  - QC artifacts never modify the cleaned DataFrame.
  - All artifact paths are registered in QCArtifact entries and indexed
    in qc_index.json for programmatic discovery.
  - Plots are optional (matplotlib may not be installed).
  - Every save_* method registers its output in the artifact registry.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from preprocessing.config import QC_OUTPUT_DIR
from preprocessing.labels import build_display_label_bundle
from preprocessing.validators import UnknownTokenReport, ValidationReport, unknown_tokens_to_dataframe

logger = logging.getLogger(__name__)

ArtifactKind = Literal[
    "csv",
    "json",
    "png",
    "parquet",
    "status",
]
"""Supported QC artifact file types."""


@dataclass
class QCArtifact:
    """Registry entry for a single generated QC file.

    Attributes:
        name: Logical artifact name (e.g. "churn_distribution", "null_counts_cleaned").
        path: Absolute filesystem path to the artifact file.
        kind: File type literal (csv, json, png, parquet, status).
        status: Outcome — "written" (successfully created), "skipped"
            (intentionally skipped), or "missing_column" (prerequisite
            column not found in DataFrame).
        detail: Optional human-readable note (e.g. "first 8 rows" for samples).
    """

    name: str
    path: str
    kind: ArtifactKind
    status: Literal["written", "skipped", "missing_column"] = "written"
    detail: str | None = None


@dataclass
class QCReporter:
    """Write inspectable QC artifacts and step-level summaries under ``outputs/preprocessing/``.

    The reporter maintains an internal registry of all artifacts produced
    during a preprocessing run. At the end of the pipeline, finalize()
    writes qc_summary.json and qc_index.json for programmatic discovery.

    Attributes:
        output_dir: Directory for all QC artifacts.
        write_plots: If True, attempt to render matplotlib sanity plots
            (silently skipped if matplotlib is not installed).
        sample_rows: Number of head rows to capture in sample CSVs.
    """

    output_dir: Path = field(default_factory=lambda: Path(QC_OUTPUT_DIR))
    write_plots: bool = True
    sample_rows: int = 8

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._summaries: dict[str, Any] = {}
        self._artifacts: list[QCArtifact] = []
        self._row_progression: list[dict[str, Any]] = []

    def _register(
        self,
        name: str,
        path: Path | None,
        kind: ArtifactKind,
        status: Literal["written", "skipped", "missing_column"] = "written",
        detail: str | None = None,
    ) -> None:
        """Append an artifact to the internal registry.

        Args:
            name: Logical artifact name.
            path: Filesystem path (None for skipped/missing entries).
            kind: File type literal.
            status: Outcome of the write attempt.
            detail: Optional context note.
        """
        self._artifacts.append(
            QCArtifact(
                name=name,
                path=str(path) if path else "",
                kind=kind,
                status=status,
                detail=detail,
            )
        )

    def log_step(self, step: str, df: pd.DataFrame, extra: dict[str, Any] | None = None) -> None:
        """Record and log a concise row/column/memory summary for a pipeline step.

        The summary is stored both in the step summaries dict and in the
        row count progression list (for row-count-vs-step tracking).

        Args:
            step: Step label (e.g. "01_raw_loaded", "03_mapped").
            df: DataFrame at this step.
            extra: Optional dict of additional metrics to log and store.
        """
        info: dict[str, Any] = {
            "step": step,
            "n_rows": int(len(df)),
            "n_columns": int(len(df.columns)),
            "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1e6, 2),
        }
        if extra:
            info.update(extra)
        self._summaries[step] = info
        self._row_progression.append(
            {"step": step, "n_rows": info["n_rows"], "n_columns": info["n_columns"]}
        )
        logger.info(
            "[%s] rows=%s cols=%s%s",
            step,
            info["n_rows"],
            info["n_columns"],
            f" | {extra}" if extra else "",
        )

    def save_null_counts(self, df: pd.DataFrame, name: str) -> Path:
        """Write a CSV of columns with null counts (empty if none).

        Only columns with at least one null are included.

        Args:
            df: DataFrame to inspect.
            name: Label for the output filename (e.g. "cleaned").

        Returns:
            Path to the written CSV.
        """
        path = self.output_dir / f"null_counts_{name}.csv"
        nulls = df.isna().sum()
        nulls = nulls[nulls > 0]
        if nulls.empty:
            pd.DataFrame({"column": [], "null_count": []}).to_csv(path, index=False)
        else:
            pd.DataFrame(
                {"column": nulls.index.astype(str), "null_count": nulls.astype(int).values}
            ).to_csv(path, index=False)
        self._register(f"null_counts_{name}", path, "csv")
        return path

    def save_value_counts(
        self,
        df: pd.DataFrame,
        columns: list[str],
        prefix: str,
    ) -> list[Path]:
        """Write schema-safe value counts to CSV for specified columns.

        All values are cast to string for deterministic JSON-safe output.
        Missing columns are registered as "missing_column" artifacts.

        Args:
            df: DataFrame to compute counts from.
            columns: Column names to inspect.
            prefix: Filename prefix (e.g. "mapped", "cleaned").

        Returns:
            List of paths to the written CSV files.
        """
        paths: list[Path] = []
        for col in columns:
            if col not in df.columns:
                self._register(
                    f"value_counts_{prefix}_{col}",
                    None,
                    "csv",
                    status="missing_column",
                    detail=f"Column {col} not in frame",
                )
                continue
            vc = df[col].astype(str).value_counts(dropna=False)
            out = pd.DataFrame(
                {
                    "value": vc.index.astype(str),
                    "count": vc.values.astype(int),
                    "pct": (vc.values / max(len(df), 1) * 100).round(2),
                }
            )
            path = self.output_dir / f"value_counts_{prefix}_{col}.csv"
            out.to_csv(path, index=False)
            paths.append(path)
            self._register(f"value_counts_{prefix}_{col}", path, "csv")
        return paths

    def save_churn_outputs(self, df: pd.DataFrame) -> dict[str, Any]:
        """Write churn distribution CSV and overall metrics JSON.

        Gracefully handles the case where churn_binary column is missing
        by returning a status dict and registering skipped artifacts
        rather than raising.

        Args:
            df: DataFrame that may contain a 'churn_binary' column.

        Returns:
            Status dict with keys: column, written, status, and optionally
            paths/metrics when data was present.
        """
        status: dict[str, Any] = {"column": "churn_binary", "written": False}

        if "churn_binary" not in df.columns:
            status["status"] = "missing_column"
            status["message"] = "churn_binary not present — churn QC skipped"
            logger.warning(status["message"])
            self._register("churn_distribution", None, "status", status="missing_column", detail=status["message"])
            self._register("churn_overall_metrics", None, "status", status="missing_column", detail=status["message"])
            return status

        counts = df["churn_binary"].value_counts().sort_index()
        dist = pd.DataFrame(
            {
                "churn_binary": counts.index.astype(str),
                "count": counts.values.astype(int),
                "pct": (counts.values / len(df) * 100).round(4),
            }
        )
        dist_path = self.output_dir / "churn_distribution.csv"
        dist.to_csv(dist_path, index=False)

        churned = int((df["churn_binary"] == 1).sum())
        metrics = {
            "n_rows": int(len(df)),
            "n_churned": churned,
            "n_retained": int(len(df) - churned),
            "churn_rate": round(float(df["churn_binary"].mean()), 6),
            "churn_rate_pct": round(float(df["churn_binary"].mean()) * 100, 4),
        }
        metrics_path = self.output_dir / "churn_overall_metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        self._register("churn_distribution", dist_path, "csv")
        self._register("churn_overall_metrics", metrics_path, "json")
        status.update({"written": True, "status": "ok", "paths": {"distribution": str(dist_path), "metrics": str(metrics_path)}, "metrics": metrics})
        return status

    def save_flag_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        """Write a CSV of value counts for all QC/operational flag columns.

        Identifies flag columns by name convention: columns ending in
        '_flag' or named 'is_data_capable'. Returns a status dict with
        an explicit message when no flag columns are found.

        Args:
            df: DataFrame that may contain flag columns.

        Returns:
            Status dict with keys: flag_columns, written, status, path.
        """
        flag_cols = sorted(
            c for c in df.columns if c.endswith("_flag") or c == "is_data_capable"
        )
        status: dict[str, Any] = {"flag_columns": flag_cols, "written": False}

        path = self.output_dir / "qc_flag_counts.csv"
        if not flag_cols:
            msg = "No QC/operational flag columns discovered in frame"
            status["status"] = "no_flags"
            status["message"] = msg
            logger.warning(msg)
            pd.DataFrame(columns=["flag", "value", "count"]).to_csv(path, index=False)
            self._register("qc_flag_counts", path, "csv", status="skipped", detail=msg)
            status["path"] = str(path)
            return status

        rows: list[dict[str, Any]] = []
        for col in flag_cols:
            vc = df[col].astype(str).value_counts(dropna=False)
            for val, cnt in vc.items():
                rows.append({"flag": col, "value": str(val), "count": int(cnt)})

        pd.DataFrame(rows).to_csv(path, index=False)
        self._register("qc_flag_counts", path, "csv")
        status.update({"written": True, "status": "ok", "path": str(path), "n_flags": len(flag_cols)})
        return status

    def save_unknown_token_table(self, reports: list[UnknownTokenReport]) -> Path | None:
        """Write a flattened CSV of unknown tokens discovered during validation.

        Writes an empty DataFrame with the expected columns if no unknown
        tokens were found (so downstream tools always get a file).

        Args:
            reports: List of UnknownTokenReport from validation steps.

        Returns:
            Path to the written CSV.
        """
        path = self.output_dir / "unknown_tokens.csv"
        table = unknown_tokens_to_dataframe(reports)
        if table.empty:
            pd.DataFrame(
                columns=["column", "unknown_token", "row_count", "allowed_sample"]
            ).to_csv(path, index=False)
            self._register("unknown_tokens", path, "csv", status="skipped", detail="No unknown tokens")
        else:
            table.to_csv(path, index=False)
            self._register("unknown_tokens", path, "csv")
        return path

    def save_validation_report(self, report: ValidationReport, name: str) -> Path:
        """Persist a validation report as JSON for audit.

        Args:
            report: ValidationReport to serialize.
            name: Short label for the filename (e.g. "raw_schema", "mapped").

        Returns:
            Path to the written JSON file.
        """
        path = self.output_dir / f"validation_{name}.json"
        payload = {
            "passed": report.passed,
            "errors": report.errors,
            "warnings": report.warnings,
            "metrics": report.metrics,
            "unknown_token_summary": report.metrics.get("unknown_token_summary", {}),
            "policy": report.policy.to_dict(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._register(f"validation_{name}", path, "json")
        return path

    def save_sample_rows(
        self,
        df: pd.DataFrame,
        name: str,
        n: int | None = None,
    ) -> Path:
        """Write a deterministic head sample CSV for before/after inspection.

        Args:
            df: DataFrame to sample from.
            name: Label for the output filename (e.g. "01_raw_head").
            n: Number of rows to capture (defaults to self.sample_rows).

        Returns:
            Path to the written CSV.
        """
        n = n or self.sample_rows
        path = self.output_dir / f"sample_{name}.csv"
        df.head(n).to_csv(path, index=False)
        self._register(f"sample_{name}", path, "csv", detail=f"first {n} rows")
        return path

    def save_row_count_progression(self) -> Path:
        """Write a CSV tracking row/column counts across pipeline steps.

        Useful for spotting unexpected row drops or column additions.

        Returns:
            Path to the written CSV.
        """
        path = self.output_dir / "row_count_progression.csv"
        pd.DataFrame(self._row_progression).to_csv(path, index=False)
        self._register("row_count_progression", path, "csv")
        return path

    def maybe_write_plots(self, df: pd.DataFrame) -> list[str]:
        """Conditionally render matplotlib sanity charts.

        Plots are written only if self.write_plots is True AND matplotlib
        is importable. Silent skip otherwise (no error raised).

        Three plots may be generated:
          - Churn distribution bar chart.
          - Mobile data generation bar chart.
          - Churn rate % by SIM type (normalized crosstab).

        Args:
            df: Cleaned DataFrame to visualize.

        Returns:
            List of paths to generated PNG files (empty if none written).
        """
        if not self.write_plots:
            return []
        written: list[str] = []
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available; skipping QC plots")
            return written

        if "churn_binary" in df.columns:
            fig, ax = plt.subplots(figsize=(5, 3))
            df["churn_binary"].value_counts().sort_index().plot(
                kind="bar", ax=ax, color=["#4cd6ff", "#7000ff"]
            )
            ax.set_title("Churn distribution (cleaned)")
            ax.set_xlabel("churn_binary")
            ax.set_ylabel("count")
            p = self.output_dir / "plot_churn_distribution.png"
            fig.tight_layout()
            fig.savefig(p, dpi=120)
            plt.close(fig)
            written.append(str(p))
            self._register("plot_churn_distribution", p, "png")

        if "mobile_data_generation" in df.columns:
            fig, ax = plt.subplots(figsize=(6, 3))
            df["mobile_data_generation"].value_counts().sort_index().plot(kind="bar", ax=ax)
            ax.set_title("Mobile data generation")
            ax.set_ylabel("count")
            p = self.output_dir / "plot_mobile_generation.png"
            fig.tight_layout()
            fig.savefig(p, dpi=120)
            plt.close(fig)
            written.append(str(p))
            self._register("plot_mobile_generation", p, "png")

        if "sim_card_type" in df.columns and "churn_binary" in df.columns:
            ct = (
                pd.crosstab(df["sim_card_type"], df["churn_binary"], normalize="index") * 100
            )
            fig, ax = plt.subplots(figsize=(5, 3))
            ct.plot(kind="bar", ax=ax)
            ax.set_title("Churn rate % by SIM type")
            ax.set_ylabel("pct")
            ax.legend(title="churn")
            p = self.output_dir / "plot_churn_by_sim_type.png"
            fig.tight_layout()
            fig.savefig(p, dpi=120)
            plt.close(fig)
            written.append(str(p))
            self._register("plot_churn_by_sim_type", p, "png")

        return written

    def write_qc_index(self) -> Path:
        """Write a JSON registry of all QC artifacts for downstream tool discovery.

        The index contains metadata about every artifact created during
        the preprocessing run (name, path, kind, status, detail).

        Returns:
            Path to the written qc_index.json.
        """
        index_path = self.output_dir / "qc_index.json"
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(self.output_dir),
            "artifacts": [a.__dict__ for a in self._artifacts],
            "n_artifacts": len(self._artifacts),
        }
        index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._register("qc_index", index_path, "json")
        return index_path

    def finalize(self, manifest_extras: dict[str, Any] | None = None) -> dict[str, Any]:
        """Finalize QC reporting: write row progression, index, and summary.

        Should be called once at the end of preprocessing. Writes:
          - row_count_progression.csv
          - qc_index.json
          - qc_summary.json (includes step summaries, display labels, extras)

        Args:
            manifest_extras: Optional dict of additional information to
                include in the summary (e.g. churn status, flag counts,
                plot paths from the pipeline).

        Returns:
            The summary bundle dict with keys: generated_at_utc, output_dir,
            step_summaries, row_count_progression, display_labels,
            artifact_count, manifest_extras (if any), qc_index, qc_summary.
        """
        self.save_row_count_progression()
        self.write_qc_index()

        bundle: dict[str, Any] = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(self.output_dir),
            "step_summaries": self._summaries,
            "row_count_progression": self._row_progression,
            "display_labels": build_display_label_bundle(),
            "artifact_count": len(self._artifacts),
        }
        if manifest_extras:
            bundle["manifest_extras"] = manifest_extras

        summary_path = self.output_dir / "qc_summary.json"
        summary_path.write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._register("qc_summary", summary_path, "json")
        bundle["qc_index"] = str(self.output_dir / "qc_index.json")
        bundle["qc_summary"] = str(summary_path)
        return bundle
