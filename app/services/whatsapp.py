"""WhatsApp Cloud API helpers: signature verification, parsing, media, outbound replies."""

import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.exceptions import MediaDownloadError
from app.core.settings import settings
from app.schemas.whatsapp import InboundMessage, MessageType

logger = logging.getLogger(__name__)


def _graph_base() -> str:
    return f"https://graph.facebook.com/{settings.whatsapp_graph_version}"


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate Meta's ``X-Hub-Signature-256`` header against the raw request body.

    Security-critical: without this, anyone could POST forged reports to the webhook.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        key=settings.whatsapp_app_secret.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def parse_inbound(payload: dict[str, Any]) -> InboundMessage | None:
    """Defensively extract the first message from Meta's webhook envelope.

    Returns None for non-message events (status callbacks, etc.). The message may be a
    photo, a location, free text, or something else; the pipeline decides what to do.
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        message = value["messages"][0]
    except (KeyError, IndexError, TypeError):
        return None

    image = message.get("image") or {}
    location = message.get("location") or {}
    text = message.get("text") or {}

    message_type: MessageType
    if image.get("id") is not None:
        message_type = "image"
    elif location.get("latitude") is not None:
        message_type = "location"
    elif text.get("body") is not None:
        message_type = "text"
    else:
        message_type = "other"

    return InboundMessage(
        message_id=message["id"],
        from_phone=message["from"],
        message_type=message_type,
        image_media_id=image.get("id"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        text=text.get("body"),
    )


async def download_media(media_id: str) -> bytes:
    """Resolve a WhatsApp media id to a temporary URL and download the bytes.

    Media URLs are short-lived and require the access token, so this must run promptly.
    """
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta = await client.get(f"{_graph_base()}/{media_id}", headers=headers)
        if meta.status_code != 200:
            raise MediaDownloadError(f"Failed to resolve media {media_id}")
        media_url = meta.json().get("url")
        if not media_url:
            raise MediaDownloadError(f"No URL for media {media_id}")

        asset = await client.get(media_url, headers=headers)
        if asset.status_code != 200:
            raise MediaDownloadError(f"Failed to download media {media_id}")
        return asset.content


async def send_text_message(to: str, body: str) -> None:
    """Send a plain-text reply to a citizen via the Cloud API.

    In dev mode (no real token) the message is logged instead of sent, so the local
    conversation flow is still observable without Meta credentials. Failures are logged
    and swallowed: an undelivered reply must never crash the ingestion pipeline.
    """
    if not settings.whatsapp_configured:
        logger.info("WhatsApp not configured; would reply to %s: %s", to, body)
        return

    url = f"{_graph_base()}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            logger.error(
                "Failed to send WhatsApp reply to %s: %s %s",
                to,
                response.status_code,
                response.text,
            )
    except httpx.HTTPError:
        logger.exception("HTTP error sending WhatsApp reply to %s", to)
