from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Phase(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class IngredientRole(str, Enum):
    SOLVENT = "solvent"
    ACTIVE = "active"
    EMULSIFIER = "emulsifier"
    EMOLLIENT = "emollient"
    THICKENER = "thickener"
    PRESERVATIVE = "preservative"
    CHELATING = "chelating"
    HUMECTANT = "humectant"
    UV_FILTER = "uv_filter"
    ANTIOXIDANT = "antioxidant"
    FRAGRANCE = "fragrance"
    PH_ADJUSTER = "ph_adjuster"


class Engine(str, Enum):
    LIGHTGBM_GPU = "LIGHTGBM_GPU"
    DEEP_COLLOID_GNN = "DEEP_COLLOID_GNN"


class Verdict(str, Enum):
    HIGHLY_STABLE = "HIGHLY_STABLE"
    MODERATELY_STABLE = "MODERATELY_STABLE"
    UNSTABLE_RISK = "UNSTABLE_RISK"
    PHASE_SEPARATION_IMMINENT = "PHASE_SEPARATION_IMMINENT"


class IngredientInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inci: str = Field(min_length=1, max_length=255)
    smiles: str = Field(min_length=1, max_length=1024)
    weight_pct: float = Field(gt=0, le=100)
    phase: Phase
    hlb: float | None = Field(default=None, ge=0, le=20)
    role: IngredientRole

    @field_validator("smiles")
    @classmethod
    def smiles_is_plain_string(cls, value: str) -> str:
        if not value.strip() or any(ch.isspace() for ch in value):
            raise ValueError("smiles must be a single whitespace-free token")
        return value


class SimulationRequest(BaseModel):
    formula_id: str | None = Field(default=None, max_length=64)
    formula_name: str = Field(min_length=1, max_length=255)
    temperature_c: float = Field(default=40.0, gt=-50, le=100)
    duration_days: int = Field(default=90, gt=0, le=365)
    engine: Engine = Engine.LIGHTGBM_GPU
    ingredients: list[IngredientInput] = Field(min_length=1)


class DropletDistributionPoint(BaseModel):
    diameter_nm: float
    volume_frequency_pct: float


class RheologyPoint(BaseModel):
    shear_rate_s1: float
    viscosity_mpas: float


class ColloidalThermodynamics(BaseModel):
    delta_hlb: float
    sor_ratio: float
    packing_parameter_p: float
    gibbs_free_energy_kj_mol: float
    critical_micelle_concentration_mmol_l: float
    interface_state: str


class SimulationResponse(BaseModel):
    run_id: str
    formula_id: str | None = None
    formula_name: str
    temperature_c: float
    duration_days: int
    engine_used: str
    is_stub: bool = False
    inference_duration_ms: float
    created_at: datetime
    stability_score_40c_90days: float = Field(ge=0, le=1)
    verdict: Verdict
    confidence_score: float = Field(ge=0, le=1)
    is_out_of_distribution: bool
    ood_mahalanobis_distance: float
    dynamic_viscosity_mpas: float
    target_viscosity_mpas: float
    mean_droplet_size_nm: float
    polydispersity_index_pdi: float
    droplet_distribution: list[DropletDistributionPoint]
    rheology_curve: list[RheologyPoint]
    thermodynamics: ColloidalThermodynamics
    risk_factors: list[str]
    stabilizing_factors: list[str]
    recommendations: list[str]
