"""SQLAlchemy ORM models.

Import every model module here so Alembic autogenerate picks them up
through Base.metadata.
"""

from app.core.database import Base
from app.models.catalog import BatchRecord, OptimizationJob, Supplier
from app.models.chat import ChatMessage, ChatSession
from app.models.compliance import BpomLimit, ProhibitedSubstance
from app.models.competitor import CompetitorProduct
from app.models.knowledge import KnowledgeChunk
from app.models.formula import Formula, FormulaIngredient, FormulaVersion
from app.models.ingredient import Ingredient
from app.models.project import Brief, Project
from app.models.simulation_run import SimulationRun
from app.models.structure import IngredientStructureComponent
from app.models.user import RefreshToken, User

__all__ = [
    "Base",
    "BatchRecord",
    "BpomLimit",
    "Brief",
    "ChatMessage",
    "ChatSession",
    "CompetitorProduct",
    "Formula",
    "FormulaIngredient",
    "FormulaVersion",
    "Ingredient",
    "IngredientStructureComponent",
    "KnowledgeChunk",
    "OptimizationJob",
    "ProhibitedSubstance",
    "Project",
    "RefreshToken",
    "SimulationRun",
    "Supplier",
    "User",
]
