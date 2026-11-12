"""WasteReport ORM model.

Stores a geo-referenced waste report. The ``location`` column is a PostGIS POINT in
SRID 4326 (WGS84 lat/long) with a GiST spatial index for fast proximity/heatmap
queries. ``whatsapp_message_id`` is unique to enforce webhook idempotency (Meta may
redeliver the same message).
"""

from datetime import datetime
from enum import Enum

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    FAILED = "failed"
    COLLECTED = "collected"


class SourceChannel(str, Enum):
    """Inbound channel that originated the report (extensible for future integrations)."""

    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class WasteReport(Base):
    __tablename__ = "waste_reports"

    id: Mapped[int] = mapped_column(primary_key=True)

    whatsapp_message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    reporter_phone: Mapped[str] = mapped_column(String(32), index=True)
    source_channel: Mapped[SourceChannel] = mapped_column(String(16), index=True)

    # PostGIS POINT (SRID 4326). Redundant lat/long floats kept for convenience.
    # spatial_index=False: the GiST index is declared explicitly below so Alembic owns it.
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    image_url: Mapped[str | None] = mapped_column(String(1024), default=None)

    status: Mapped[ReportStatus] = mapped_column(String(16), default=ReportStatus.PENDING)
    waste_category: Mapped[str | None] = mapped_column(String(64), default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_waste_reports_location", "location", postgresql_using="gist"),)
