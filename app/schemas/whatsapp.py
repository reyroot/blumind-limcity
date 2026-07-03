"""Lightweight schemas for parsed WhatsApp inbound messages.

We intentionally do NOT model Meta's full nested webhook envelope with Pydantic; that
structure is large and changes often. Instead the WhatsApp service parses the raw
payload defensively and produces this normalized ``InboundMessage``.
"""

from pydantic import BaseModel


class InboundMessage(BaseModel):
    message_id: str
    from_phone: str
    image_media_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def is_actionable(self) -> bool:
        """A report needs both an image and a location to be geo-classified."""
        return (
            self.image_media_id is not None
            and self.latitude is not None
            and self.longitude is not None
        )
