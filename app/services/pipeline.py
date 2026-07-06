"""Orchestrates the report ingestion pipeline (runs as a background task).

Because it executes after the webhook has already returned 200 to Meta, it manages its
own DB session and swallows/logs errors rather than propagating them to a request.
"""

import logging

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.report import ReportStatus
from app.schemas.report import WasteReportCreate
from app.schemas.whatsapp import InboundMessage
from app.services import report_service
from app.services.classifier.base import WasteClassifier
from app.services.whatsapp import download_media

logger = logging.getLogger(__name__)


async def process_inbound_message(message: InboundMessage, classifier: WasteClassifier) -> None:
    """Idempotently persist and classify a single inbound WhatsApp report."""
    if not message.is_actionable:
        logger.info("Skipping non-actionable message %s", message.message_id)
        return

    async with SessionLocal() as session:
        existing = await report_service.get_by_message_id(session, message.message_id)
        if existing is not None:
            logger.info("Duplicate message %s ignored", message.message_id)
            return

        assert message.latitude is not None and message.longitude is not None
        report = await report_service.create_report(
            session,
            WasteReportCreate(
                whatsapp_message_id=message.message_id,
                reporter_phone=message.from_phone,
                latitude=message.latitude,
                longitude=message.longitude,
            ),
        )

        try:
            assert message.image_media_id is not None
            if settings.whatsapp_configured:
                image_bytes = await download_media(message.image_media_id)
            else:
                # Dev mode: no real WhatsApp token, so skip the Graph API download.
                # The placeholder classifier ignores the bytes anyway.
                logger.info("WhatsApp not configured; skipping media download (dev).")
                image_bytes = b""
            result = await classifier.classify(image_bytes)
            await report_service.apply_classification(session, report, result)
        except Exception:
            logger.exception("Classification failed for %s", message.message_id)
            report.status = ReportStatus.FAILED

        await session.commit()
