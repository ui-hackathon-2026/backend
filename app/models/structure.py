from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IngredientStructureComponent(Base):
    __tablename__ = "ingredient_structure_components"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingredient_inci: Mapped[str] = mapped_column(String(255), index=True)
    representation_type: Mapped[str] = mapped_column(String(32))
    smiles: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    marker_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caveat_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="backend")
