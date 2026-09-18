from sqlalchemy import Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inci: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    name: Mapped[str] = mapped_column(String(255))
    smiles: Mapped[str] = mapped_column(String(1024))
    cas_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_phase: Mapped[str] = mapped_column(String(1))
    default_role: Mapped[str] = mapped_column(String(32))
    hlb: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_weight_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_recommended_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_recommended_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_kg_idr: Mapped[float] = mapped_column(Float, default=0.0)
    tkdn_pct: Mapped[float] = mapped_column(Float, default=0.0)
    bpom_limit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    halal_status: Mapped[str] = mapped_column(String(32), default="HALAL")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    identity_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    structure_representation_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    molecular_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    logp: Mapped[float | None] = mapped_column(Float, nullable=True)
    tpsa: Mapped[float | None] = mapped_column(Float, nullable=True)
    hbd: Mapped[int | None] = mapped_column(nullable=True)
    hba: Mapped[int | None] = mapped_column(nullable=True)
