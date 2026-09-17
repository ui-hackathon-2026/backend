from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inci: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    smiles: Mapped[str] = mapped_column(String(1024))
    default_phase: Mapped[str] = mapped_column(String(1))
    default_role: Mapped[str] = mapped_column(String(32))
    hlb: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_kg_idr: Mapped[float] = mapped_column(Float, default=0.0)
    tkdn_pct: Mapped[float] = mapped_column(Float, default=0.0)
    bpom_limit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    halal_status: Mapped[str] = mapped_column(String(32), default="HALAL")
