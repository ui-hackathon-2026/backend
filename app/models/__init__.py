"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base
from app.models.chat import ChatMessage, ChatSession
from app.models.compliance import BpomLimit
from app.models.formula import Formula, FormulaIngredient, FormulaVersion
from app.models.ingredient import Ingredient
from app.models.project import Brief, Project
from app.models.simulation_run import SimulationRun
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "BpomLimit",
    "Brief",
    "ChatMessage",
    "ChatSession",
    "Formula",
    "FormulaIngredient",
    "FormulaVersion",
    "Ingredient",
    "Project",
    "SimulationRun",
    "User",
    "UserRole",
]
