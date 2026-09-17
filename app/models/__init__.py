"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base

__all__ = ["Base"]
