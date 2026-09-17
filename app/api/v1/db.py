from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.health import DbHealthResponse
from app.services.health_service import get_db_status

router = APIRouter(tags=["db"])


@router.get("/db-health", response_model=DbHealthResponse)
def db_health(db: SessionDep) -> DbHealthResponse:
    return get_db_status(db)
