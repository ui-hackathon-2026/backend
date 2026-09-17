from pydantic import BaseModel, Field


class NsgaWeights(BaseModel):
    stabilityWeight: float = Field(default=35, ge=0, le=100)
    cogsWeight: float = Field(default=30, ge=0, le=100)
    tkdnWeight: float = Field(default=20, ge=0, le=100)
    viscosityWeight: float = Field(default=15, ge=0, le=100)


class NsgaConstraints(BaseModel):
    minStabilityPct: float = Field(default=85.0, ge=0, le=100)
    maxCogsIdrPerKg: float = Field(default=42000.0, gt=0)
    minTkdnPct: float = Field(default=40.0, ge=0, le=100)
    targetViscosityMpaS: float = Field(default=5200.0, gt=0)


class ParetoOptimizationRequest(BaseModel):
    weights: NsgaWeights = Field(default_factory=NsgaWeights)
    constraints: NsgaConstraints = Field(default_factory=NsgaConstraints)
    preset: str = "balanced"
    trialsCount: int = Field(default=2000, ge=3, le=50000)


class FrontierPoint(BaseModel):
    id: str
    trialIndex: int
    stabilityPct: float
    cogsIdr: float
    tkdnPct: float
    viscosityMpaS: float
    isParetoOptimal: bool
    rank: int
    candidateId: str | None = None


class CandidateMetrics(BaseModel):
    stabilityPct: float
    cogsIdrPerKg: float
    tkdnPct: float
    viscosityMpaS: float
    systemHlb: float


class CandidateIngredient(BaseModel):
    id: str
    name: str
    inci: str
    phase: str
    weightPct: float
    functionDesc: str
    isLocalTkdn: bool


class TopCandidateDetail(BaseModel):
    id: str
    title: str
    archetype: str
    badgeLabel: str
    metrics: CandidateMetrics
    tradeOffSummary: str
    physicochemicalRationale: str
    ingredients: list[CandidateIngredient]


class ParetoOptimizationResponse(BaseModel):
    trialsEvaluated: int
    executionTimeMs: float
    nonDominatedCount: int
    hypervolumeScore: float
    points: list[FrontierPoint]
    topCandidates: list[TopCandidateDetail]
