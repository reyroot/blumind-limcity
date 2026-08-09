"""ConversationSession ORM model.

Correlates the two-step WhatsApp report flow: a citizen usually sends the *photo* and
the *location* in separate messages (in either order). We buffer whichever arrives
first, keyed by phone number, until the report can be completed. DB-backed (not
in-memory) so it survives restarts and works across background tasks.

There is at most one in-progress session per phone; it is deleted once a report is
created from it.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # Buffered photo (with its message id, reused as the report's idempotency key).
    pending_image_media_id: Mapped[str | None] = mapped_column(String(128), default=None)
    pending_image_message_id: Mapped[str | None] = mapped_column(String(128), default=None)

    # Buffered location.
    pending_latitude: Mapped[float | None] = mapped_column(Float, default=None)
    pending_longitude: Mapped[float | None] = mapped_column(Float, default=None)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
