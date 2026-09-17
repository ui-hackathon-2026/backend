"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base
from app.models.user import User

__all__ = ["Base", "User"]
