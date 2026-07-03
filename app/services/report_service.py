"""Business logic for persisting and updating waste reports."""

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportStatus, WasteReport
from app.schemas.classification import ClassificationResult
from app.schemas.report import WasteReportCreate


async def get_by_message_id(session: AsyncSession, message_id: str) -> WasteReport | None:
    """Idempotency helper: find an existing report for a WhatsApp message id."""
    result = await session.execute(
        select(WasteReport).where(WasteReport.whatsapp_message_id == message_id)
    )
    return result.scalar_one_or_none()


async def create_report(session: AsyncSession, payload: WasteReportCreate) -> WasteReport:
    """Persist a new pending report with a PostGIS POINT (SRID 4326)."""
    point = WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326)
    report = WasteReport(
        whatsapp_message_id=payload.whatsapp_message_id,
        reporter_phone=payload.reporter_phone,
        location=point,
        latitude=payload.latitude,
        longitude=payload.longitude,
        image_url=payload.image_url,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    await session.flush()
    return report


async def apply_classification(
    session: AsyncSession, report: WasteReport, result: ClassificationResult
) -> WasteReport:
    """Attach an AI classification result to an existing report."""
    report.waste_category = result.category
    report.confidence = result.confidence
    report.status = ReportStatus.CLASSIFIED
    await session.flush()
    return report
