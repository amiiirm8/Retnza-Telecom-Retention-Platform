"""
Report export endpoints — CSV and PDF downloads.

Pipeline position:
  Generates downloadable reports from the recommendations database. CSV export
  supports optional priority filtering; PDF export generates a full campaign
  summary with charts.

Workflow stage:
  GET /api/v1/reports/export/csv?priority=P1 -> CSV file download.
  GET /api/v1/reports/export/pdf -> PDF file download.

Security:
  All endpoints require authentication via CurrentUser dependency.
"""

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession
from app.services.report_service import campaign_summary_pdf, recommendations_to_csv

router = APIRouter()


@router.get("/export/csv")
async def export_csv(
    db: DbSession,
    _user: CurrentUser,
    priority: str | None = Query(None),
) -> Response:
    """
    Export recommendations as a CSV file, optionally filtered by campaign priority.

    Args:
        db: Database session.
        _user: Authenticated user.
        priority: Optional campaign priority filter (e.g., 'P1', 'P2', 'P3').

    Returns:
        CSV file download response.
    """
    data = await recommendations_to_csv(db, priority=priority)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=action_queue.csv"},
    )


@router.get("/export/pdf")
async def export_pdf(db: DbSession, _user: CurrentUser) -> Response:
    """
    Generate and download a campaign summary PDF with KPIs and charts.

    Args:
        db: Database session.
        _user: Authenticated user.

    Returns:
        PDF file download response.
    """
    data = await campaign_summary_pdf(db)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=campaign_summary.pdf"},
    )
