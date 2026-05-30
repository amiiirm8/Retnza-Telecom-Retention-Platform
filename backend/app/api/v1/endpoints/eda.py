"""
EDA Insights endpoint — feeds structured EDA findings to the Evidence & Insights page.

Pipeline position:
  Reads pre-computed EDA CSVs and executive summary JSON from outputs/ directories
  and returns them in a structured format for the frontend Evidence page.

Workflow stage:
  GET /api/v1/dashboard/eda -> dict of EDA findings and narratives.

Security:
  Requires authentication via CurrentUser dependency.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.services.eda_service import get_eda_summary

router = APIRouter()


@router.get("/eda")
async def dashboard_eda(_user: CurrentUser) -> dict[str, Any]:
    """
    Return structured EDA findings and executive narratives.

    Includes:
      - Churn by SIM type, tenure band, mobile generation, SIM x generation, VoLTE
      - Executive narratives across 6 dimensions
      - Retention simulation scenarios
      - Top 10 SHAP features (global importance)
      - Subscriber count and mean calibrated risk

    All data is pre-computed from the analytics pipeline — no real-time computation.
    """
    return get_eda_summary()
