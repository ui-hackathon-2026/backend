from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.schemas.nsga import (
    ParetoOptimizationRequest,
    ParetoOptimizationResponse,
)
from app.services.nsga_service import InfeasibleConstraintsError, run_nsga2

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.post("/run-nsga2", response_model=ParetoOptimizationResponse)
def run(
    body: ParetoOptimizationRequest, db: SessionDep, seed: int | None = None
) -> ParetoOptimizationResponse:
    try:
        return run_nsga2(db, body, seed=seed)
    except InfeasibleConstraintsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "suggestions": exc.suggestions},
        )
