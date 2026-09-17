from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BpomLimit(Base):
    __tablename__ = "bpom_limits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inci: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    max_pct: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(64))
    regulation_ref: Mapped[str] = mapped_column(
        String(255), default="Perka BPOM No. 17/2022"
    )
