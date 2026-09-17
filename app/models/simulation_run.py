from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    formula_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    formula_name: Mapped[str] = mapped_column(String(255))
    temperature_c: Mapped[float] = mapped_column(Float, default=40.0)
    duration_days: Mapped[int] = mapped_column(Integer, default=90)
    engine_used: Mapped[str] = mapped_column(String(32))
    stability_score: Mapped[float] = mapped_column(Float)
    verdict: Mapped[str] = mapped_column(String(64))
    mean_droplet_size_nm: Mapped[float] = mapped_column(Float)
    dynamic_viscosity_mpas: Mapped[float] = mapped_column(Float)
    is_out_of_distribution: Mapped[bool] = mapped_column(default=False)
    raw_response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
