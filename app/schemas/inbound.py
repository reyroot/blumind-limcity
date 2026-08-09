"""Channel-agnostic schema for normalized inbound report messages.

WhatsApp and Telegram deliver photos and locations in separate messages. Both channels
parse their native webhook payload into this shape before handing off to the shared
report conversation flow.
"""

from typing import Literal

from pydantic import BaseModel

MessageType = Literal["image", "location", "text", "other"]


class InboundReportMessage(BaseModel):
    message_id: str
    session_key: str
    reporter_label: str
    message_type: MessageType = "other"
    image_media_ref: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    text: str | None = None

    @property
    def has_image(self) -> bool:
        return self.image_media_ref is not None

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def is_actionable(self) -> bool:
        """True when a single update already carries both photo and location."""
        return self.has_image and self.has_location
