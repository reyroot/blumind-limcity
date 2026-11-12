"""Simulated Blumenau reports for the admin demo buttons.

Rows are marked with a ``sim-`` message id (the older seed script used ``seed-``).
Clearing deletes only those rows and their photos. Reports that arrived from
Telegram or WhatsApp stay on the map.
"""

import random
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import ColumnElement, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportStatus, SourceChannel, WasteReport
from app.schemas.classification import WASTE_CATEGORIES
from app.services.image_store import get_image_store

SIMULATED_PREFIX = "sim-"
LEGACY_SEED_PREFIX = "seed-"
DEMO_REPORT_COUNT = 90

# Neighborhood centers (lat, lng) so the heatmap clusters like a real city.
_HOTSPOTS: tuple[tuple[float, float], ...] = (
    (-26.9194, -49.0661),  # Centro
    (-26.9330, -49.0900),  # Velha
    (-26.9480, -49.0700),  # Garcia
    (-26.8700, -49.0800),  # Itoupava Norte
    (-26.8900, -49.0600),  # Fortaleza
)

_CATEGORY_RGB: dict[str, tuple[int, int, int]] = {
    "organic": (132, 204, 22),
    "recyclable": (59, 130, 246),
    "construction_debris": (245, 158, 11),
    "electronic": (168, 85, 247),
    "bulky": (236, 72, 153),
    "hazardous": (239, 68, 68),
    "general": (148, 163, 184),
}


def is_simulated_message_id(message_id: str) -> bool:
    return message_id.startswith((SIMULATED_PREFIX, LEGACY_SEED_PREFIX))


def _simulated_filter() -> ColumnElement[bool]:
    return or_(
        WasteReport.whatsapp_message_id.startswith(SIMULATED_PREFIX),
        WasteReport.whatsapp_message_id.startswith(LEGACY_SEED_PREFIX),
    )


def placeholder_png(category: str) -> bytes:
    """Small colored PNG so simulated reports show up in the photo strip."""
    red, green, blue = _CATEGORY_RGB.get(category, _CATEGORY_RGB["general"])
    size = 48
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter: None
        for x in range(size):
            dx, dy = x - 24, y - 20
            if dx * dx + dy * dy < 120:
                rows.extend((255, 255, 255))
            else:
                rows.extend((red, green, blue))
    return _png(size, size, bytes(rows))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _build_report(rng: random.Random, index: int, total: int) -> WasteReport:
    lat0, lng0 = _HOTSPOTS[index % len(_HOTSPOTS)]
    lat = lat0 + rng.gauss(0, 0.006)
    lng = lng0 + rng.gauss(0, 0.006)
    # Keep the newest reports recent so the photo strip is not a month old.
    if index < 12:
        created = datetime.now(timezone.utc) - timedelta(hours=rng.randint(0, 36))
    else:
        span = max(total - 12, 1)
        created = datetime.now(timezone.utc) - timedelta(
            days=1 + int(29 * (index - 12) / span),
            hours=rng.randint(0, 23),
        )
    return WasteReport(
        whatsapp_message_id=f"{SIMULATED_PREFIX}{uuid.uuid4()}",
        reporter_phone=f"+5547{rng.randint(90000000, 99999999)}",
        source_channel=SourceChannel.WHATSAPP,
        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
        latitude=lat,
        longitude=lng,
        status=ReportStatus.CLASSIFIED,
        waste_category=WASTE_CATEGORIES[index % len(WASTE_CATEGORIES)],
        confidence=round(rng.uniform(0.72, 0.98), 2),
        created_at=created,
    )


async def clear_simulated(session: AsyncSession) -> int:
    """Delete simulated reports and their photo files. Real reports stay."""
    result = await session.execute(select(WasteReport.id).where(_simulated_filter()))
    ids = list(result.scalars().all())
    if not ids:
        return 0
    store = get_image_store()
    for report_id in ids:
        store.delete(report_id)
    await session.execute(delete(WasteReport).where(WasteReport.id.in_(ids)))
    await session.flush()
    return len(ids)


async def fill_simulated(
    session: AsyncSession,
    count: int = DEMO_REPORT_COUNT,
) -> tuple[int, int]:
    """Replace any previous simulated set with ``count`` classified reports."""
    removed = await clear_simulated(session)
    rng = random.Random()
    reports = [_build_report(rng, index, count) for index in range(count)]
    session.add_all(reports)
    await session.flush()
    store = get_image_store()
    for report in reports:
        category = report.waste_category or "general"
        report.image_url = store.save(report.id, placeholder_png(category))
    await session.flush()
    return len(reports), removed
