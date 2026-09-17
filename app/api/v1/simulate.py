from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.services.simulation_service import get_simulation_run, run_simulation

router = APIRouter(prefix="/simulate", tags=["simulation"])


@router.post("/stability", response_model=SimulationResponse)
def simulate_stability(
    body: SimulationRequest, db: SessionDep
) -> SimulationResponse:
    return run_simulation(db, body)


@router.get("/stability/{run_id}", response_model=SimulationResponse)
def get_stability_run(run_id: str, db: SessionDep) -> SimulationResponse:
    result = get_simulation_run(db, run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation run not found",
        )
    return result
