from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models. Import models in app.models so
    Alembic autogenerate sees them via Base.metadata."""


engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Yield a request-scoped session. Override in tests via
    app.dependency_overrides."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
