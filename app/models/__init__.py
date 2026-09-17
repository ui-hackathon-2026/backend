"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base
from app.models.ingredient import Ingredient
from app.models.simulation_run import SimulationRun
from app.models.user import User, UserRole

__all__ = ["Base", "Ingredient", "SimulationRun", "User", "UserRole"]
