"""Business logic for health/readiness probes.

Routes handle HTTP only; anything that can fail lives here and raises
domain exceptions (app.core.exceptions), which main.py maps to HTTP.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.schemas.health import DbHealthResponse


def get_db_status(db: Session) -> DbHealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return DbHealthResponse()
