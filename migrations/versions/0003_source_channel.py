"""add source_channel to waste_reports

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "waste_reports",
        sa.Column("source_channel", sa.String(length=16), nullable=False, server_default="whatsapp"),
    )
    op.execute(
        "UPDATE waste_reports SET source_channel = 'telegram' "
        "WHERE whatsapp_message_id LIKE 'tg:%'"
    )
    op.create_index("ix_waste_reports_source_channel", "waste_reports", ["source_channel"])


def downgrade() -> None:
    op.drop_index("ix_waste_reports_source_channel", table_name="waste_reports")
    op.drop_column("waste_reports", "source_channel")
