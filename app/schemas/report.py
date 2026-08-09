"""Pydantic schemas for waste reports (request validation & response serialization)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ReportStatus, SourceChannel


class WasteReportCreate(BaseModel):
    whatsapp_message_id: str
    reporter_phone: str
    source_channel: SourceChannel
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    image_url: str | None = None


class WasteReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_phone: str
    source_channel: SourceChannel
    latitude: float
    longitude: float
    status: ReportStatus
    waste_category: str | None
    confidence: float | None
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[WasteReportRead]
    total: int
    limit: int
    offset: int


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    weight: float = Field(description="Aggregated report count at this grid cell.")


class CategoryCount(BaseModel):
    category: str | None
    count: int


class ReportStats(BaseModel):
    total: int
    by_category: list[CategoryCount]
