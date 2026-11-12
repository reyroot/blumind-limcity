"""Business logic for the two-step WhatsApp conversation state.

Buffers a citizen's pending photo and/or location (keyed by phone) until both parts of
a report are present, then the pipeline promotes them into a persisted ``WasteReport``.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationSession

_SESSION_TTL = timedelta(hours=1)


async def get_session(session: AsyncSession, phone: str) -> ConversationSession | None:
    """Return the in-progress session for a phone, if any."""
    result = await session.execute(
        select(ConversationSession).where(ConversationSession.phone == phone)
    )
    return result.scalar_one_or_none()


async def _get_or_create(session: AsyncSession, phone: str) -> ConversationSession:
    convo = await get_session(session, phone)
    if convo is not None and _is_expired(convo):
        await session.delete(convo)
        await session.flush()
        convo = None
    if convo is None:
        convo = ConversationSession(phone=phone)
        session.add(convo)
        await session.flush()
    return convo


def _is_expired(convo: ConversationSession) -> bool:
    """Treat photo/location pairs older than one hour as separate reports."""
    updated_at = convo.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated_at >= _SESSION_TTL


async def set_image(
    session: AsyncSession, phone: str, media_id: str, message_id: str
) -> ConversationSession:
    """Buffer the citizen's photo (latest wins if they send several)."""
    convo = await _get_or_create(session, phone)
    convo.pending_image_media_id = media_id
    convo.pending_image_message_id = message_id
    await session.flush()
    return convo


async def set_location(
    session: AsyncSession, phone: str, latitude: float, longitude: float
) -> ConversationSession:
    """Buffer the citizen's location (latest wins if they send several)."""
    convo = await _get_or_create(session, phone)
    convo.pending_latitude = latitude
    convo.pending_longitude = longitude
    await session.flush()
    return convo


async def clear_session(session: AsyncSession, phone: str) -> None:
    """Delete the in-progress session once a report has been created from it."""
    await session.execute(
        delete(ConversationSession).where(ConversationSession.phone == phone)
    )
