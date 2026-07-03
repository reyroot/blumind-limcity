"""WhatsApp Cloud API helpers: signature verification, payload parsing, media download."""

import hashlib
import hmac
from typing import Any

import httpx

from app.core.exceptions import MediaDownloadError
from app.core.settings import settings
from app.schemas.whatsapp import InboundMessage

_GRAPH_BASE = "https://graph.facebook.com/v21.0"


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
    """Defensively extract the first actionable message from Meta's webhook envelope.

    Returns None for non-message events (status callbacks, etc.).
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
    return InboundMessage(
        message_id=message["id"],
        from_phone=message["from"],
        image_media_id=image.get("id"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
    )


async def download_media(media_id: str) -> bytes:
    """Resolve a WhatsApp media id to a temporary URL and download the bytes.

    Media URLs are short-lived and require the access token, so this must run promptly.
    """
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta = await client.get(f"{_GRAPH_BASE}/{media_id}", headers=headers)
        if meta.status_code != 200:
            raise MediaDownloadError(f"Failed to resolve media {media_id}")
        media_url = meta.json().get("url")
        if not media_url:
            raise MediaDownloadError(f"No URL for media {media_id}")

        asset = await client.get(media_url, headers=headers)
        if asset.status_code != 200:
            raise MediaDownloadError(f"Failed to download media {media_id}")
        return asset.content
