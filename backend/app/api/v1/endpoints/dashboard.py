"""
Dashboard endpoints — executive KPIs, distribution charts, and EDA insights.

Pipeline position:
  Aggregates recommendation data into business-level KPIs and charts for the
  CRM dashboard frontend. Delegates computation to dashboard_service.

Workflow stage:
  GET /api/v1/dashboard/kpis -> KPIResponse (top-level metrics).
  GET /api/v1/dashboard/charts -> ChartsResponse (distribution charts).
  GET /api/v1/dashboard/eda -> dict (EDA findings and narratives).

Security:
  All endpoints require authentication via CurrentUser dependency.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.dashboard import ChartsResponse, KPIResponse
from app.services.dashboard_service import get_charts, get_kpis
from app.services.eda_service import get_eda_summary

router = APIRouter()


@router.get("/kpis", response_model=KPIResponse)
async def dashboard_kpis(db: DbSession, _user: CurrentUser) -> KPIResponse:
    """
    Return top-level KPIs for the executive dashboard.

    Includes subscriber counts, churn rates, action counts by priority, high-risk
    volumes, operational flags, and an executive summary string.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        KPIResponse with all dashboard KPIs.
    """
    return await get_kpis(db)


@router.get("/charts", response_model=ChartsResponse)
async def dashboard_charts(db: DbSession, _user: CurrentUser) -> ChartsResponse:
    """
    Return distribution charts for the dashboard.

    Includes risk distribution, campaign priority distribution, rule distribution,
    churn by SIM type, ecosystem segment distribution, and CRM queue distribution.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        ChartsResponse with all chart series.
    """
    return await get_charts(db)


@router.get("/eda")
async def dashboard_eda(_user: CurrentUser) -> dict[str, Any]:
    """
    Return structured EDA findings and executive narratives.

    Includes churn by SIM type, tenure band, mobile generation, SIM x generation,
    VoLTE impact, executive narratives across 6 dimensions, retention simulation
    scenarios, and top SHAP features.

    All data is pre-computed from the analytics pipeline — no real-time computation.

    Args:
        _user: Authenticated user.

    Returns:
        Dict with EDA findings and narratives.
    """
    return get_eda_summary()
