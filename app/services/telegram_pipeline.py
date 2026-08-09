"""Telegram adapter for the shared report conversation flow."""

import logging

from app.core.settings import settings
from app.models.report import SourceChannel
from app.schemas.inbound import InboundReportMessage
from app.services.classifier.base import WasteClassifier
from app.services.report_conversation import process_inbound_report
from app.services.telegram import download_file, send_text_message

logger = logging.getLogger(__name__)


class TelegramChannel:
    source_channel = SourceChannel.TELEGRAM

    async def send_text(self, recipient_id: str, body: str) -> None:
        await send_text_message(recipient_id, body)

    async def download_image(self, media_ref: str) -> bytes:
        if settings.telegram_configured:
            return await download_file(media_ref)
        logger.info("Telegram not configured; skipping file download (dev).")
        return b""


async def process_inbound_update(
    message: InboundReportMessage, classifier: WasteClassifier
) -> None:
    """Advance the report conversation for a single inbound Telegram update."""
    await process_inbound_report(message, classifier, TelegramChannel())
