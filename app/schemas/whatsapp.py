"""Lightweight schemas for parsed WhatsApp inbound messages.

We intentionally do NOT model Meta's full nested webhook envelope with Pydantic; that
structure is large and changes often. Instead the WhatsApp service parses the raw
payload defensively and produces this normalized ``InboundMessage``.

Real WhatsApp usage sends the photo and the location as *separate* messages, so a
single message rarely carries both. ``message_type`` lets the pipeline drive a small
conversation (collect a photo, then a location) rather than expecting both at once.
"""

from typing import Literal

from pydantic import BaseModel

MessageType = Literal["image", "location", "text", "other"]


class InboundMessage(BaseModel):
    message_id: str
    from_phone: str
    message_type: MessageType = "other"
    image_media_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    text: str | None = None

    @property
    def has_image(self) -> bool:
        return self.image_media_id is not None

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def is_actionable(self) -> bool:
        """True when a single message already carries both a photo and a location.

        Rare in real WhatsApp, but supported (and used by the local test tooling).
        """
        return self.has_image and self.has_location
