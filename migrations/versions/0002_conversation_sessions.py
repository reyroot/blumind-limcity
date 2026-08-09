"""conversation_sessions: buffer two-step WhatsApp reports

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("pending_image_media_id", sa.String(length=128), nullable=True),
        sa.Column("pending_image_message_id", sa.String(length=128), nullable=True),
        sa.Column("pending_latitude", sa.Float(), nullable=True),
        sa.Column("pending_longitude", sa.Float(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_sessions_phone",
        "conversation_sessions",
        ["phone"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_sessions_phone", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
