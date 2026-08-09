"""Read APIs for waste reports: list, heatmap aggregation, GeoJSON, and stats.

Controllers stay thin — all querying is delegated to the report service. All
endpoints accept the same optional filters (category + created_at range).
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.report import SourceChannel
from app.schemas.report import (
    HeatmapPoint,
    ReportListResponse,
    ReportStats,
    WasteReportRead,
)
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CategoryQuery = Annotated[str | None, Query(description="Filter by waste category.")]
SourceChannelQuery = Annotated[
    SourceChannel | None, Query(description="Filter by inbound channel (whatsapp, telegram).")
]
StartQuery = Annotated[datetime | None, Query(description="created_at >= (ISO 8601).")]
EndQuery = Annotated[datetime | None, Query(description="created_at <= (ISO 8601).")]


def _enum_value(value: Enum | str) -> str:
    """Serialize a str Enum or a plain string column value."""
    return value.value if isinstance(value, Enum) else value


@router.get("", response_model=ReportListResponse)
async def list_reports(
    session: SessionDep,
    category: CategoryQuery = None,
    source_channel: SourceChannelQuery = None,
    start: StartQuery = None,
    end: EndQuery = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportListResponse:
    items = await report_service.list_reports(
        session,
        category=category,
        source_channel=source_channel,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    total = await report_service.count_reports(
        session, category=category, source_channel=source_channel, start=start, end=end
    )
    return ReportListResponse(
        items=[WasteReportRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/heatmap", response_model=list[HeatmapPoint])
async def heatmap(
    session: SessionDep,
    category: CategoryQuery = None,
    source_channel: SourceChannelQuery = None,
    start: StartQuery = None,
    end: EndQuery = None,
) -> list[HeatmapPoint]:
    return await report_service.heatmap_points(
        session, category=category, source_channel=source_channel, start=start, end=end
    )


@router.get("/stats", response_model=ReportStats)
async def stats(
    session: SessionDep,
    category: CategoryQuery = None,
    source_channel: SourceChannelQuery = None,
    start: StartQuery = None,
    end: EndQuery = None,
) -> ReportStats:
    return await report_service.stats(
        session, category=category, source_channel=source_channel, start=start, end=end
    )


@router.get("/geojson")
async def geojson(
    session: SessionDep,
    category: CategoryQuery = None,
    source_channel: SourceChannelQuery = None,
    start: StartQuery = None,
    end: EndQuery = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict[str, Any]:
    """Return matching reports as a GeoJSON FeatureCollection (for map markers)."""
    reports = await report_service.list_reports(
        session,
        category=category,
        source_channel=source_channel,
        start=start,
        end=end,
        limit=limit,
        offset=0,
    )
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.longitude, r.latitude],
            },
            "properties": {
                "id": r.id,
                "source_channel": _enum_value(r.source_channel),
                "category": r.waste_category,
                "confidence": r.confidence,
                "status": _enum_value(r.status),
                "created_at": r.created_at.isoformat(),
            },
        }
        for r in reports
    ]
    return {"type": "FeatureCollection", "features": features}
