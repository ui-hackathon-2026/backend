from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FormulaMessage(Base):
    __tablename__ = "formula_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    formula_id: Mapped[str] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    linked_artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
