from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inci: Mapped[str] = mapped_column(String(255), unique=True, index=True)
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
