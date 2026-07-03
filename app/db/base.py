"""Declarative base for all ORM models.

All models inherit from ``Base`` so Alembic autogeneration and metadata creation can
discover them. Import model modules before calling ``create_all`` / migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
