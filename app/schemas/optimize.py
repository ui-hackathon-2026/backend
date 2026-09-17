from pydantic import BaseModel, Field


class LockedIngredient(BaseModel):
    inci: str = Field(min_length=1, max_length=255)
    pct: float = Field(gt=0, le=100)


class TargetObjectives(BaseModel):
    maximize_stability: float = Field(default=1.0, ge=0, le=1)
    minimize_cogs: float = Field(default=0.8, ge=0, le=1)
    maximize_tkdn: float = Field(default=0.7, ge=0, le=1)
    target_viscosity_mpas: float = Field(default=5500.0, gt=0)


class OptimizeRequest(BaseModel):
    num_trials: int = Field(default=50, ge=3, le=200)
    locked_ingredients: list[LockedIngredient] = Field(default_factory=list)
    target_objectives: TargetObjectives = Field(default_factory=TargetObjectives)


class TopCandidate(BaseModel):
    label: str
    stability: float
    cogs_idr_per_kg: float
    tkdn_pct: float
    recipe: dict[str, float]


class ScatterPoint(BaseModel):
    x: float
    y: float
    z: float
    id: str


class OptimizeResponse(BaseModel):
    experiment_id: str
    total_evaluated: int
    duration_seconds: float
    top_candidates: list[TopCandidate]
    scatter_3d: list[ScatterPoint]
