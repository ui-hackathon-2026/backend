from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.workbench import (
    FormulaCompositionDto,
    FormulaMomentsDto,
    IngredientListResponse,
    WorkbenchSaveRequest,
    WorkbenchSaveResponse,
)
from app.services.workbench_service import (
    calculate_moments,
    list_ingredients,
    save_draft,
)

router = APIRouter(prefix="/workbench", tags=["workbench"])


@router.get("/ingredients", response_model=IngredientListResponse)
def ingredients(
    db: SessionDep,
    phase: str | None = None,
    role: str | None = None,
    q: str | None = None,
    halal_only: bool = False,
) -> IngredientListResponse:
    return list_ingredients(db, phase=phase, role=role, q=q, halal_only=halal_only)


@router.post("/calculate-moments", response_model=FormulaMomentsDto)
def moments(body: FormulaCompositionDto) -> FormulaMomentsDto:
    return calculate_moments(body)


@router.post("/formulas", response_model=WorkbenchSaveResponse, status_code=201)
def save(body: WorkbenchSaveRequest, db: SessionDep) -> WorkbenchSaveResponse:
    return save_draft(db, body)
