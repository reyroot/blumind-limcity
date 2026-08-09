"""Seed the database with demo waste reports around Blumenau.

Dev utility only — generates clustered, geo-referenced reports so the heatmap
dashboard is demonstrable while the real WhatsApp/AI pipeline is still stubbed.

Usage:
    venv\\Scripts\\python -m scripts.seed_demo            # 300 reports
    venv\\Scripts\\python -m scripts.seed_demo 800        # custom count
"""

import asyncio
import random
import selectors
import sys
import uuid
from datetime import datetime, timedelta, timezone

from geoalchemy2.elements import WKTElement

from app.db.session import SessionLocal
from app.models.report import ReportStatus, SourceChannel, WasteReport
from app.schemas.classification import WASTE_CATEGORIES

# Approximate neighborhood centers (lat, lng) to create realistic hotspots.
HOTSPOTS: list[tuple[float, float]] = [
    (-26.9194, -49.0661),  # Centro
    (-26.9330, -49.0900),  # Velha
    (-26.9480, -49.0700),  # Garcia
    (-26.8700, -49.0800),  # Itoupava Norte
    (-26.8900, -49.0600),  # Fortaleza
]


def _random_report() -> WasteReport:
    lat0, lng0 = random.choice(HOTSPOTS)
    lat = lat0 + random.gauss(0, 0.008)
    lng = lng0 + random.gauss(0, 0.008)
    category = random.choice(WASTE_CATEGORIES)
    created = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, 30), hours=random.randint(0, 23)
    )
    return WasteReport(
        whatsapp_message_id=f"seed-{uuid.uuid4()}",
        reporter_phone=f"+5547{random.randint(90000000, 99999999)}",
        source_channel=SourceChannel.WHATSAPP,
        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
        latitude=lat,
        longitude=lng,
        status=ReportStatus.CLASSIFIED,
        waste_category=category,
        confidence=round(random.uniform(0.6, 0.99), 2),
        created_at=created,
    )


async def seed(count: int) -> None:
    async with SessionLocal() as session:
        session.add_all([_random_report() for _ in range(count)])
        await session.commit()
    print(f"Seeded {count} demo reports.")


def _selector_loop() -> asyncio.AbstractEventLoop:
    # psycopg async requires a SelectorEventLoop on Windows (not Proactor).
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    if sys.platform == "win32":
        loop = _selector_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(seed(n))
    else:
        asyncio.run(seed(n))
