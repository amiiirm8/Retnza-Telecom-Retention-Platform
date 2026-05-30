"""CSV and PDF operational reports."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import Recommendation


async def recommendations_to_csv(session: AsyncSession, priority: str | None = None) -> bytes:
    q = select(Recommendation).order_by(Recommendation.campaign_queue_rank)
    if priority:
        q = q.where(Recommendation.campaign_priority == priority)
    rows = (await session.execute(q)).scalars().all()
    data = [
        {
            "subscriber_id": r.subscriber_id,
            "churn_probability_raw": r.churn_probability_raw,
            "churn_probability": r.churn_probability,
            "risk_tier": r.risk_tier,
            "rule_top_driver": r.rule_top_driver,
            "shap_top_driver": r.shap_top_driver,
            "final_top_driver": r.final_top_driver,
            "final_top_driver_source": r.final_top_driver_source,
            "recommended_action": r.recommended_action,
            "rule_id": r.rule_id,
            "campaign_priority": r.campaign_priority,
            "campaign_cost_tier": r.campaign_cost_tier,
            "crm_queue": r.crm_queue,
            "digital_only_flag": r.digital_only_flag,
            "escalation_required": r.escalation_required,
            "ecosystem_segment": r.ecosystem_segment,
            "ecosystem_retention_strategy": r.ecosystem_retention_strategy,
            "primary_channel": r.primary_channel,
        }
        for r in rows
    ]
    buf = io.StringIO()
    pd.DataFrame(data).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


async def campaign_summary_pdf(session: AsyncSession) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, h - inch, "Retnza Campaign Summary")
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, h - 1.35 * inch, f"Generated: {datetime.now(timezone.utc).isoformat()}")
    y = h - 2 * inch
    for priority in ("P1", "P2", "P3", "P4"):
        count = await session.scalar(
            select(func.count())
            .select_from(Recommendation)
            .where(Recommendation.campaign_priority == priority)
        )
        c.drawString(1 * inch, y, f"Priority {priority}: {count or 0} subscribers")
        y -= 0.25 * inch
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
