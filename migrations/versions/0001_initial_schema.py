"""initial schema: postgis extension + waste_reports

Revision ID: 0001
Revises:
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "waste_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("whatsapp_message_id", sa.String(length=128), nullable=False),
        sa.Column("reporter_phone", sa.String(length=32), nullable=False),
        sa.Column(
            "location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("waste_category", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_waste_reports_whatsapp_message_id",
        "waste_reports",
        ["whatsapp_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_waste_reports_reporter_phone", "waste_reports", ["reporter_phone"]
    )
    op.create_index(
        "ix_waste_reports_location",
        "waste_reports",
        ["location"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_waste_reports_location", table_name="waste_reports")
    op.drop_index("ix_waste_reports_reporter_phone", table_name="waste_reports")
    op.drop_index("ix_waste_reports_whatsapp_message_id", table_name="waste_reports")
    op.drop_table("waste_reports")
    # PostGIS extension is left installed intentionally.
