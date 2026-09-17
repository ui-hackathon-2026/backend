from pydantic import BaseModel, Field


class IngredientCatalogItem(BaseModel):
    id: str
    name: str
    inci: str
    smiles: str
    cas_number: str | None = None
    default_phase: str
    role: str
    hlb: float | None = None
    default_weight_pct: float | None = None
    min_recommended_pct: float | None = None
    max_recommended_pct: float | None = None
    bpom_limit_pct: float | None = None
    is_halal: bool
    tkdn_pct: float
    cost_per_kg_idr: float
    description: str | None = None

    model_config = {"from_attributes": True}


class IngredientListResponse(BaseModel):
    total: int
    items: list[IngredientCatalogItem]


class MomentIngredient(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    inci: str = Field(min_length=1, max_length=255)
    smiles: str = Field(min_length=1, max_length=1024)
    weight_pct: float = Field(ge=0, le=100)
    phase: str = Field(min_length=1, max_length=1)
    role: str = Field(min_length=1, max_length=32)
    hlb: float | None = None
    cost_per_kg_idr: float = Field(default=0.0, ge=0)
    tkdn_pct: float = Field(default=0.0, ge=0, le=100)


class FormulaCompositionDto(BaseModel):
    batch_size_g: float = Field(default=1000.0, gt=0)
    ingredients: list[MomentIngredient] = Field(min_length=1)


class RadarMetrics(BaseModel):
    hlb_equilibrium: float
    surfactant_efficiency: float
    viscosity_potential: float
    cost_efficiency: float
    tkdn_score: float


class MomentWarning(BaseModel):
    code: str
    severity: str
    message: str


class FormulaMomentsDto(BaseModel):
    system_hlb: float
    required_hlb: float
    delta_hlb: float
    sor_ratio: float
    phase_totals: dict[str, float]
    total_weight_pct: float
    estimated_cogs_per_kg_idr: float
    overall_tkdn_pct: float
    radar_metrics: RadarMetrics
    warnings: list[MomentWarning] = Field(default_factory=list)


class WorkbenchSaveIngredient(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    inci: str = Field(min_length=1, max_length=255)
    smiles: str = Field(min_length=1, max_length=1024)
    weight_pct: float = Field(ge=0, le=100)
    phase: str = Field(min_length=1, max_length=1)
    role: str = Field(min_length=1, max_length=32)
    is_locked: bool = False


class WorkbenchSaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    batch_size_g: float = Field(default=1000.0, gt=0)
    notes: str | None = Field(default=None, max_length=1024)
    ingredients: list[WorkbenchSaveIngredient] = Field(min_length=1)


class WorkbenchSaveResponse(BaseModel):
    id: str
    name: str
    category: str | None = None
    batch_size_g: float
    created_at: str
    updated_at: str
