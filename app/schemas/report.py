"""Pydantic schemas for waste reports (request validation & response serialization)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ReportStatus


class WasteReportCreate(BaseModel):
    whatsapp_message_id: str
    reporter_phone: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    image_url: str | None = None


class WasteReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_phone: str
    latitude: float
    longitude: float
    status: ReportStatus
    waste_category: str | None
    confidence: float | None
    created_at: datetime
