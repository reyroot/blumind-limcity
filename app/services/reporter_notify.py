"""Citizen-facing status messages, sent back on the channel that opened the report."""

import logging

from app.models.report import SourceChannel, WasteReport
from app.schemas.classification import ClassificationResult
from app.services import telegram, whatsapp

logger = logging.getLogger(__name__)

CATEGORY_LABELS_PT = {
    "organic": "orgânico",
    "recyclable": "reciclável",
    "construction_debris": "entulho",
    "electronic": "eletrônico",
    "bulky": "volumoso",
    "hazardous": "perigoso",
    "general": "geral",
}


def reply_queued(report_id: int) -> str:
    return (
        f"\u2705 Denúncia *nº {report_id}* recebida! "
        "A foto está em análise. Avisaremos o resultado neste chat."
    )


def reply_classified(report_id: int, category: str, confidence: float | None) -> str:
    label = CATEGORY_LABELS_PT.get(category, category)
    conf = f" (confiança {confidence:.0%})" if confidence is not None else ""
    return (
        f"\u2705 Denúncia *nº {report_id}* registrada como *{label}*{conf}. "
        "Ela já aparece no mapa."
    )


def reply_invalid(report_id: int) -> str:
    return (
        f"Denúncia *nº {report_id}*: não identificamos resíduos descartados "
        "em uma área aberta nessa foto. Ela não entrou no mapa."
    )


def reply_error(report_id: int) -> str:
    return (
        f"\u26a0\ufe0f Denúncia *nº {report_id}*: não conseguimos classificar a foto. "
        "Tente enviar outra imagem."
    )


def reply_collected(report_id: int) -> str:
    return (
        f"\U0001f69b Denúncia *nº {report_id}* foi marcada como *coletada*. "
        "Obrigado por ajudar a cuidar de Blumenau!"
    )


def outcome_reply(report_id: int, result: ClassificationResult | None) -> str:
    if result is None:
        return reply_error(report_id)
    if not result.is_valid_report:
        return reply_invalid(report_id)
    return reply_classified(report_id, result.category, result.confidence)


async def send_to_reporter(report: WasteReport, body: str) -> None:
    """Deliver a status update. A send failure must not undo the saved report."""
    channel = report.source_channel
    channel_value = channel.value if isinstance(channel, SourceChannel) else str(channel)
    try:
        if channel_value == SourceChannel.TELEGRAM.value:
            await telegram.send_text_message(report.reporter_phone, body)
        elif channel_value == SourceChannel.WHATSAPP.value:
            await whatsapp.send_text_message(report.reporter_phone, body)
        else:
            logger.info("No outbound channel for report %s (%s)", report.id, channel_value)
    except Exception:
        logger.exception("Could not notify reporter for report %s", report.id)


async def notify_outcome(report: WasteReport, result: ClassificationResult | None) -> None:
    await send_to_reporter(report, outcome_reply(report.id, result))


async def notify_collected(report: WasteReport) -> None:
    await send_to_reporter(report, reply_collected(report.id))
