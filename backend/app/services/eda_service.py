"""
EDA Insights service — reads pre-computed analytics from outputs/eda and outputs/analytics.

Pipeline position:
  Serves EDA findings, executive narratives, and structured churn analysis from
  pre-computed CSV/JSON files generated during the analytics pipeline stage.

Workflow stage:
  Called by the /dashboard/eda endpoint. Pure file-read; no DB dependency.
"""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_csv(path: Path) -> list[dict[str, str | float | int]]:
    if not path.exists():
        return []
    rows: list[dict[str, str | float | int]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed: dict[str, str | float | int] = {}
            for k, v in row.items():
                parsed[k] = _try_numeric(v)
            rows.append(parsed)
    return rows


def _try_numeric(v: str) -> str | float | int:
    v = v.strip()
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_churn_by_sim() -> list[dict[str, Any]]:
    return _read_csv(PROJECT_ROOT / "outputs" / "eda" / "churn_by_sim_type.csv")


def get_churn_by_tenure() -> list[dict[str, Any]]:
    return _read_csv(PROJECT_ROOT / "outputs" / "eda" / "churn_by_tenure_band.csv")


def get_churn_by_generation() -> list[dict[str, Any]]:
    return _read_csv(PROJECT_ROOT / "outputs" / "eda" / "churn_by_generation.csv")


def get_churn_by_sim_and_generation() -> list[dict[str, Any]]:
    return _read_csv(PROJECT_ROOT / "outputs" / "eda" / "churn_by_sim_and_generation.csv")


def get_volte_impact() -> list[dict[str, Any]]:
    return _read_csv(PROJECT_ROOT / "outputs" / "eda" / "churn_volte_data_capable.csv")


def get_executive_summary() -> dict[str, Any] | None:
    return _read_json(PROJECT_ROOT / "outputs" / "analytics" / "executive_summary.json")


def get_retention_simulation() -> dict[str, Any] | None:
    return _read_json(PROJECT_ROOT / "outputs" / "analytics" / "retention_simulation_summary.json")


def get_top_shap_features() -> list[str]:
    path = PROJECT_ROOT / "outputs" / "explainability" / "global_shap_importance.csv"
    rows = _read_csv(path)
    return [str(r.get("feature", "")) for r in rows[:10] if r.get("feature")]


def get_eda_summary() -> dict[str, Any]:
    executive = get_executive_summary() or {}
    narratives_raw = executive.get("narratives", {})
    narratives = [
        {"key": k, "bullets": v if isinstance(v, list) else [str(v)]}
        for k, v in narratives_raw.items()
    ]

    simulation = get_retention_simulation()
    sim_scenarios = (simulation or {}).get("scenarios", {})

    return {
        "n_subscribers": executive.get("n_subscribers", 7043),
        "mean_calibrated_risk": executive.get("mean_calibrated_risk", 0.269),
        "churn_by_sim": get_churn_by_sim(),
        "churn_by_tenure": get_churn_by_tenure(),
        "churn_by_generation": get_churn_by_generation(),
        "churn_by_sim_and_generation": get_churn_by_sim_and_generation(),
        "volte_impact": get_volte_impact(),
        "executive_narratives": narratives,
        "retention_simulation": sim_scenarios,
        "top_shap_features": get_top_shap_features()[:10],
        "generated_at_utc": executive.get("generated_at_utc", ""),
    }
