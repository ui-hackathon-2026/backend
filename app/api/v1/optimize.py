from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.schemas.optimize import OptimizeRequest, OptimizeResponse
from app.services.optimization_service import get_optimization, run_optimization

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/pareto", response_model=OptimizeResponse)
def pareto(
    body: OptimizeRequest, db: SessionDep, seed: int | None = None
) -> OptimizeResponse:
    return run_optimization(db, body, seed=seed)


@router.get("/pareto/{experiment_id}", response_model=OptimizeResponse)
def get_experiment(experiment_id: str, db: SessionDep) -> OptimizeResponse:
    result = get_optimization(db, experiment_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
        )
    return result
