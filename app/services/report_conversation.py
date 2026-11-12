"""Shared two-step report conversation flow for any messaging channel.

WhatsApp and Telegram both buffer photo + location across separate messages. This module
owns that state machine; each channel supplies a thin adapter for outbound replies and
media download.
"""

import logging
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.report import SourceChannel
from app.schemas.classification import ClassificationResult
from app.schemas.inbound import InboundReportMessage
from app.schemas.report import WasteReportCreate
from app.services import conversation_service, report_service
from app.services.classifier.base import WasteClassifier
from app.services.image_store import store_report_image
from app.services.reporter_notify import reply_classified, reply_queued
from app.services.runtime_config import load_runtime_config

logger = logging.getLogger(__name__)

# Citizen-facing replies (pt-BR — Blumenau, SC). Markdown works on WhatsApp and Telegram.
REPLY_ASK_LOCATION = (
    "\U0001f4f8 Foto recebida! Agora envie a *localização* do resíduo "
    "para concluir o registro."
)
REPLY_ASK_PHOTO = (
    "\U0001f4cd Localização recebida! Agora envie uma *foto* do resíduo "
    "para concluir o registro."
)
REPLY_HELP = (
    "Olá! \U0001f44b Sou o assistente do *Limcity*. Para registrar um descarte "
    "irregular de resíduos, envie uma *foto* e a *localização* do local "
    "(pode ser em qualquer ordem)."
)
REPLY_ERROR = (
    "\u26a0\ufe0f Recebemos seu registro, mas houve um erro ao classificar a imagem. "
    "Nossa equipe foi notificada."
)
REPLY_PROCESSING = (
    "\u23f3 Recebemos sua foto e localização. Sua denúncia está sendo analisada; "
    "enviaremos o resultado assim que terminar."
)
REPLY_INVALID_REPORT = (
    "Não conseguimos identificar resíduos descartados em uma área aberta nessa foto. "
    "Envie outra imagem mostrando claramente o descarte irregular."
)


class ReportChannel(Protocol):
    """Outbound + media hooks implemented per channel (WhatsApp, Telegram, …)."""

    source_channel: SourceChannel

    async def send_text(self, recipient_id: str, body: str) -> None: ...

    async def download_image(self, media_ref: str) -> bytes: ...


def _reply_confirmed(report_id: int, result: ClassificationResult) -> str:
    return reply_classified(report_id, result.category, result.confidence)


async def process_inbound_report(
    message: InboundReportMessage,
    classifier: WasteClassifier,
    channel: ReportChannel,
) -> None:
    """Advance the report conversation for a single normalized inbound message."""
    async with SessionLocal() as session:
        if message.is_actionable:
            assert message.image_media_ref is not None
            assert message.latitude is not None and message.longitude is not None
            await _complete_report(
                session,
                classifier,
                channel,
                reporter_label=message.reporter_label,
                session_key=message.session_key,
                message_id=message.message_id,
                media_ref=message.image_media_ref,
                latitude=message.latitude,
                longitude=message.longitude,
            )
            await session.commit()
            return

        if message.has_image:
            assert message.image_media_ref is not None
            convo = await conversation_service.set_image(
                session,
                message.session_key,
                message.image_media_ref,
                message.message_id,
            )
            if convo.pending_latitude is not None and convo.pending_longitude is not None:
                await _complete_report(
                    session,
                    classifier,
                    channel,
                    reporter_label=message.reporter_label,
                    session_key=message.session_key,
                    message_id=message.message_id,
                    media_ref=message.image_media_ref,
                    latitude=convo.pending_latitude,
                    longitude=convo.pending_longitude,
                )
                await conversation_service.clear_session(session, message.session_key)
                await session.commit()
            else:
                await session.commit()
                await channel.send_text(message.session_key, REPLY_ASK_LOCATION)
            return

        if message.has_location:
            assert message.latitude is not None and message.longitude is not None
            convo = await conversation_service.set_location(
                session, message.session_key, message.latitude, message.longitude
            )
            if convo.pending_image_media_id is not None and convo.pending_image_message_id:
                await _complete_report(
                    session,
                    classifier,
                    channel,
                    reporter_label=message.reporter_label,
                    session_key=message.session_key,
                    message_id=convo.pending_image_message_id,
                    media_ref=convo.pending_image_media_id,
                    latitude=message.latitude,
                    longitude=message.longitude,
                )
                await conversation_service.clear_session(session, message.session_key)
                await session.commit()
            else:
                await session.commit()
                await channel.send_text(message.session_key, REPLY_ASK_PHOTO)
            return

        logger.info("Non-actionable message %s (%s)", message.message_id, message.message_type)
        await channel.send_text(message.session_key, REPLY_HELP)


async def _complete_report(
    session: AsyncSession,
    classifier: WasteClassifier,
    channel: ReportChannel,
    *,
    reporter_label: str,
    session_key: str,
    message_id: str,
    media_ref: str,
    latitude: float,
    longitude: float,
) -> None:
    """Idempotently persist, classify, and confirm a fully-collected report."""
    existing = await report_service.get_by_message_id(session, message_id)
    if existing is not None:
        logger.info("Duplicate message %s ignored", message_id)
        return

    demo_mode = load_runtime_config().demo_mode
    if demo_mode:
        await _queue_demo_report(
            session,
            channel,
            reporter_label=reporter_label,
            session_key=session_key,
            message_id=message_id,
            media_ref=media_ref,
            latitude=latitude,
            longitude=longitude,
        )
        return

    # Vision models can take some time, especially when hosted locally. Confirm receipt
    # before downloading and classifying so the citizen does not mistake the delay for failure.
    await channel.send_text(session_key, REPLY_PROCESSING)

    try:
        image_bytes = await channel.download_image(media_ref)
        result = await classifier.classify(image_bytes)
    except Exception:
        logger.exception("Classification failed for %s", message_id)
        await channel.send_text(session_key, REPLY_ERROR)
        return

    if not result.is_valid_report:
        logger.info("Rejected non-waste report %s", message_id)
        await channel.send_text(session_key, REPLY_INVALID_REPORT)
        return

    report = await report_service.create_report(
        session,
        WasteReportCreate(
            whatsapp_message_id=message_id,
            reporter_phone=reporter_label,
            source_channel=channel.source_channel,
            latitude=latitude,
            longitude=longitude,
        ),
    )
    report.image_url = store_report_image(report.id, image_bytes)
    await report_service.apply_classification(session, report, result)
    await channel.send_text(session_key, _reply_confirmed(report.id, result))


async def _queue_demo_report(
    session: AsyncSession,
    channel: ReportChannel,
    *,
    reporter_label: str,
    session_key: str,
    message_id: str,
    media_ref: str,
    latitude: float,
    longitude: float,
) -> None:
    """Save the pin and the photo now. The classification worker finishes the report."""
    try:
        image_bytes = await channel.download_image(media_ref)
    except Exception:
        logger.exception("Media download failed for %s", message_id)
        await channel.send_text(session_key, REPLY_ERROR)
        return

    report = await report_service.create_report(
        session,
        WasteReportCreate(
            whatsapp_message_id=message_id,
            reporter_phone=reporter_label,
            source_channel=channel.source_channel,
            latitude=latitude,
            longitude=longitude,
        ),
    )
    report.image_url = store_report_image(report.id, image_bytes)
    logger.info("Demo report %s queued for classification", report.id)
    await channel.send_text(session_key, reply_queued(report.id))
