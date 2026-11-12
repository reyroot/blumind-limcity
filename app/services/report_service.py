"""Business logic for persisting, updating, and querying waste reports."""

from collections.abc import Sequence
from datetime import datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import ColumnElement, Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportStatus, SourceChannel, WasteReport
from app.schemas.classification import ClassificationResult
from app.schemas.report import CategoryCount, HeatmapPoint, ReportStats, WasteReportCreate

# ~110m grid cells (3 decimal degrees) for heatmap aggregation.
_HEATMAP_PRECISION = 3


def _filters(
    category: str | None,
    source_channel: SourceChannel | None,
    start: datetime | None,
    end: datetime | None,
    status: ReportStatus | None = None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if category is not None:
        conditions.append(WasteReport.waste_category == category)
    if source_channel is not None:
        conditions.append(WasteReport.source_channel == source_channel)
    if status is not None:
        conditions.append(WasteReport.status == status)
    if start is not None:
        conditions.append(WasteReport.created_at >= start)
    if end is not None:
        conditions.append(WasteReport.created_at <= end)
    return conditions


async def get_by_message_id(session: AsyncSession, message_id: str) -> WasteReport | None:
    """Idempotency helper: find an existing report for a WhatsApp message id."""
    result = await session.execute(
        select(WasteReport).where(WasteReport.whatsapp_message_id == message_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, report_id: int) -> WasteReport | None:
    return await session.get(WasteReport, report_id)


async def claim_next_pending(session: AsyncSession) -> WasteReport | None:
    """Lock the oldest pending report and mark it processing. None when the queue is empty."""
    stmt = (
        select(WasteReport)
        .where(WasteReport.status == ReportStatus.PENDING)
        .order_by(WasteReport.created_at.asc(), WasteReport.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    report = (await session.execute(stmt)).scalar_one_or_none()
    if report is None:
        return None
    report.status = ReportStatus.PROCESSING
    await session.flush()
    return report


async def requeue_processing(session: AsyncSession) -> int:
    """Put reports stuck in ``processing`` back on the queue (worker crash recovery)."""
    result = await session.execute(
        select(WasteReport).where(WasteReport.status == ReportStatus.PROCESSING)
    )
    rows = result.scalars().all()
    for report in rows:
        report.status = ReportStatus.PENDING
    await session.flush()
    return len(rows)


async def status_counts(session: AsyncSession) -> dict[str, int]:
    counts = {status.value: 0 for status in ReportStatus}
    rows = await session.execute(
        select(WasteReport.status, func.count()).group_by(WasteReport.status)
    )
    for status, count in rows.all():
        key = status.value if isinstance(status, ReportStatus) else str(status)
        counts[key] = int(count)
    return counts


async def create_report(session: AsyncSession, payload: WasteReportCreate) -> WasteReport:
    """Persist a new pending report with a PostGIS POINT (SRID 4326)."""
    point = WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326)
    report = WasteReport(
        whatsapp_message_id=payload.whatsapp_message_id,
        reporter_phone=payload.reporter_phone,
        source_channel=payload.source_channel,
        location=point,
        latitude=payload.latitude,
        longitude=payload.longitude,
        image_url=payload.image_url,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    await session.flush()
    return report


def record_result(report: WasteReport, result: ClassificationResult) -> None:
    """Apply a classifier result. Invalid photos stay on the map as failed."""
    if not result.is_valid_report:
        report.status = ReportStatus.FAILED
        report.waste_category = None
        report.confidence = result.confidence
        return
    report.waste_category = result.category
    report.confidence = result.confidence
    report.status = ReportStatus.CLASSIFIED


async def apply_classification(
    session: AsyncSession, report: WasteReport, result: ClassificationResult
) -> WasteReport:
    """Attach a valid AI classification result to an existing report."""
    record_result(report, result)
    await session.flush()
    return report


async def list_reports(
    session: AsyncSession,
    *,
    category: str | None = None,
    source_channel: SourceChannel | None = None,
    status: ReportStatus | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[WasteReport]:
    """Return a filtered, paginated page of reports (newest first)."""
    stmt = (
        select(WasteReport)
        .where(*_filters(category, source_channel, start, end, status))
        .order_by(WasteReport.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_reports(
    session: AsyncSession,
    *,
    category: str | None = None,
    source_channel: SourceChannel | None = None,
    status: ReportStatus | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Count reports matching the given filters."""
    stmt = (
        select(func.count())
        .select_from(WasteReport)
        .where(*_filters(category, source_channel, start, end, status))
    )
    total = (await session.execute(stmt)).scalar_one()
    return int(total)


async def heatmap_points(
    session: AsyncSession,
    *,
    category: str | None = None,
    source_channel: SourceChannel | None = None,
    status: ReportStatus | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[HeatmapPoint]:
    """Aggregate reports onto a coarse grid, returning weighted points for a heatmap."""
    lat_cell = func.round(cast(WasteReport.latitude, Numeric), _HEATMAP_PRECISION)
    lng_cell = func.round(cast(WasteReport.longitude, Numeric), _HEATMAP_PRECISION)
    stmt = (
        select(lat_cell, lng_cell, func.count())
        .where(*_filters(category, source_channel, start, end, status))
        .group_by(lat_cell, lng_cell)
    )
    rows = await session.execute(stmt)
    return [
        HeatmapPoint(latitude=float(lat), longitude=float(lng), weight=float(count))
        for lat, lng, count in rows.all()
    ]


async def stats(
    session: AsyncSession,
    *,
    category: str | None = None,
    source_channel: SourceChannel | None = None,
    status: ReportStatus | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ReportStats:
    """Return total count and a per-category breakdown for the given filters."""
    conditions = _filters(category, source_channel, start, end, status)
    total_raw = (
        await session.execute(select(func.count()).select_from(WasteReport).where(*conditions))
    ).scalar_one()
    total = int(total_raw)

    breakdown_stmt = (
        select(WasteReport.waste_category, func.count())
        .where(*conditions)
        .group_by(WasteReport.waste_category)
        .order_by(func.count().desc())
    )
    rows = await session.execute(breakdown_stmt)
    by_category = [CategoryCount(category=cat, count=count) for cat, count in rows.all()]
    return ReportStats(total=total, by_category=by_category)
