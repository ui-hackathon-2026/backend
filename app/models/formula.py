from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Formula(Base):
    __tablename__ = "formulas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    batch_size_g: Mapped[float] = mapped_column(Float, default=500.0)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    ingredients: Mapped[list["FormulaIngredient"]] = relationship(
        back_populates="formula", cascade="all, delete-orphan"
    )


class FormulaIngredient(Base):
    __tablename__ = "formula_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    formula_id: Mapped[str] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[str] = mapped_column(String(1))
    inci: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smiles: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    weight_pct: Mapped[float] = mapped_column(Float)
    is_locked: Mapped[bool] = mapped_column(default=False)
    formula: Mapped[Formula] = relationship(back_populates="ingredients")


class FormulaVersion(Base):
    __tablename__ = "formula_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    formula_id: Mapped[str] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
