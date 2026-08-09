"""WhatsApp adapter for the shared report conversation flow."""

import logging

from app.core.settings import settings
from app.models.report import SourceChannel
from app.schemas.inbound import InboundReportMessage
from app.schemas.whatsapp import InboundMessage
from app.services.classifier.base import WasteClassifier
from app.services.report_conversation import process_inbound_report
from app.services.whatsapp import download_media, send_text_message

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    source_channel = SourceChannel.WHATSAPP

    async def send_text(self, recipient_id: str, body: str) -> None:
        await send_text_message(recipient_id, body)

    async def download_image(self, media_ref: str) -> bytes:
        if settings.whatsapp_configured:
            return await download_media(media_ref)
        logger.info("WhatsApp not configured; skipping media download (dev).")
        return b""


def to_inbound_report(message: InboundMessage) -> InboundReportMessage:
    return InboundReportMessage(
        message_id=message.message_id,
        session_key=message.from_phone,
        reporter_label=message.from_phone,
        message_type=message.message_type,
        image_media_ref=message.image_media_id,
        latitude=message.latitude,
        longitude=message.longitude,
        text=message.text,
    )


async def process_inbound_message(message: InboundMessage, classifier: WasteClassifier) -> None:
    """Advance the report conversation for a single inbound WhatsApp message."""
    await process_inbound_report(
        to_inbound_report(message),
        classifier,
        WhatsAppChannel(),
    )
