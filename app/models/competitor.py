from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorProduct(Base):
    __tablename__ = "competitor_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    inci_list: Mapped[list] = mapped_column(JSON, default=list)
    ingredient_count: Mapped[int] = mapped_column(Integer, default=0)
