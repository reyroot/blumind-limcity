"""Telegram Bot API helpers: webhook parsing, file download, outbound replies."""

import logging
from typing import Any

import httpx

from app.core.exceptions import MediaDownloadError
from app.core.settings import settings
from app.schemas.inbound import InboundReportMessage, MessageType

logger = logging.getLogger(__name__)


def _api_base() -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def verify_webhook_secret(secret_header: str | None) -> bool:
    """Validate Telegram's optional ``X-Telegram-Bot-Api-Secret-Token`` header.

    When ``telegram_webhook_secret`` is left at the dev placeholder, verification is
    skipped so local testing works without extra setup.
    """
    if settings.telegram_webhook_secret == "change-me":
        return True
    return secret_header == settings.telegram_webhook_secret


def parse_inbound(payload: dict[str, Any]) -> InboundReportMessage | None:
    """Extract a normalized report message from a Telegram ``Update`` object.

    Only private chats are accepted (no group bots). Ignores bot messages, callbacks,
    and edits.
    """
    message = payload.get("message")
    if not isinstance(message, dict):
        return None

    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return None

    sender = message.get("from") or {}
    if sender.get("is_bot"):
        return None

    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return None

    session_key = f"tg:{chat_id}"
    external_id = f"tg:{chat_id}:{message_id}"

    photos = message.get("photo")
    location = message.get("location") or {}
    text_body = message.get("text")

    message_type: MessageType
    image_ref: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    if isinstance(photos, list) and photos:
        message_type = "image"
        image_ref = photos[-1].get("file_id")
    elif location.get("latitude") is not None:
        message_type = "location"
        latitude = location.get("latitude")
        longitude = location.get("longitude")
    elif isinstance(text_body, str):
        message_type = "text"
    else:
        message_type = "other"

    return InboundReportMessage(
        message_id=external_id,
        session_key=session_key,
        reporter_label=session_key,
        message_type=message_type,
        image_media_ref=image_ref,
        latitude=latitude,
        longitude=longitude,
        text=text_body if isinstance(text_body, str) else None,
    )


async def download_file(file_id: str) -> bytes:
    """Resolve a Telegram ``file_id`` and download the raw bytes."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta = await client.get(f"{_api_base()}/getFile", params={"file_id": file_id})
        if meta.status_code != 200:
            raise MediaDownloadError(f"Failed to resolve Telegram file {file_id}")
        file_path = meta.json().get("result", {}).get("file_path")
        if not file_path:
            raise MediaDownloadError(f"No file path for Telegram file {file_id}")

        asset = await client.get(f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}")
        if asset.status_code != 200:
            raise MediaDownloadError(f"Failed to download Telegram file {file_id}")
        return asset.content


async def send_text_message(chat_key: str, body: str) -> None:
    """Send a plain-text reply to a citizen (``chat_key`` is ``tg:<chat_id>``).

    In dev mode (no real bot token) the message is logged instead of sent.
    """
    if not settings.telegram_configured:
        logger.info("Telegram not configured; would reply to %s: %s", chat_key, body)
        return

    chat_id = chat_key.removeprefix("tg:")
    url = f"{_api_base()}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": body,
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            logger.error(
                "Failed to send Telegram reply to %s: %s %s",
                chat_key,
                response.status_code,
                response.text,
            )
    except httpx.HTTPError:
        logger.exception("HTTP error sending Telegram reply to %s", chat_key)
