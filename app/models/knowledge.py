from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    regulation: Mapped[str] = mapped_column(String(255))
    appendix: Mapped[str] = mapped_column(String(255))
    clause_entry: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    substance_name: Mapped[str] = mapped_column(String(255), index=True)
    inci_name: Mapped[str] = mapped_column(String(255), index=True)
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    cas_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_concentration_pct: Mapped[float | None] = mapped_column(nullable=True)
    allowed_product_types: Mapped[list] = mapped_column(JSON, default=list)
    conditions_of_use: Mapped[str] = mapped_column(Text, default="")
    mandatory_warnings: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    halal_critical_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
