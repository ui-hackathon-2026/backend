from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.workbench import IngredientListResponse
from app.services.search_service import search_ingredients

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("/search", response_model=IngredientListResponse)
def search(
    db: SessionDep,
    q: str,
    phase: str | None = None,
    halal_only: bool = False,
    tkdn_min: float = 0.0,
    limit: int = 20,
) -> IngredientListResponse:
    return search_ingredients(
        db, q, phase=phase, halal_only=halal_only, tkdn_min=tkdn_min, limit=limit
    )
