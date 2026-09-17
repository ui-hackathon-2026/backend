"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base
from app.models.catalog import BatchRecord, OptimizationJob, Supplier
from app.models.chat import ChatMessage, ChatSession
from app.models.compliance import BpomLimit
from app.models.knowledge import KnowledgeChunk
from app.models.formula import Formula, FormulaIngredient, FormulaVersion
from app.models.ingredient import Ingredient
from app.models.project import Brief, Project
from app.models.simulation_run import SimulationRun
from app.models.user import RefreshToken, User, UserRole

__all__ = [
    "Base",
    "BatchRecord",
    "BpomLimit",
    "Brief",
    "ChatMessage",
    "ChatSession",
    "Formula",
    "FormulaIngredient",
    "FormulaVersion",
    "Ingredient",
    "KnowledgeChunk",
    "OptimizationJob",
    "Project",
    "RefreshToken",
    "SimulationRun",
    "Supplier",
    "User",
    "UserRole",
]
