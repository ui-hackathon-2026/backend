from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OptimizationJob(Base):
    __tablename__ = "optimization_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BatchRecord(Base):
    __tablename__ = "batch_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    formula_id: Mapped[str] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"), index=True
    )
    batch_size_g: Mapped[float]
    operator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scaled_ingredients: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    ingredient_inci: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(128), nullable=True)
    halal_certified: Mapped[bool] = mapped_column(default=False)
    lead_time_days: Mapped[int | None] = mapped_column(nullable=True)
    price_per_kg_idr: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
