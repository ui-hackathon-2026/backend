from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.simulation import Phase


class FormulaIngredientInput(BaseModel):
    inci: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    smiles: str | None = Field(default=None, max_length=1024)
    weight_pct: float = Field(gt=0, le=100)
    is_locked: bool = False
    is_solvent: bool = False


class FormulaPhases(BaseModel):
    phase_a: list[FormulaIngredientInput] = Field(default_factory=list)
    phase_b: list[FormulaIngredientInput] = Field(default_factory=list)
    phase_c: list[FormulaIngredientInput] = Field(default_factory=list)
    phase_d: list[FormulaIngredientInput] = Field(default_factory=list)

    def flattened(self) -> list[tuple[str, FormulaIngredientInput]]:
        mapping = {
            Phase.A: self.phase_a,
            Phase.B: self.phase_b,
            Phase.C: self.phase_c,
            Phase.D: self.phase_d,
        }
        return [
            (phase.value, item)
            for phase, items in mapping.items()
            for item in items
        ]


class FormulaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    batch_size_g: float = Field(default=500.0, gt=0)
    notes: str | None = Field(default=None, max_length=1024)
    project_id: str | None = Field(default=None, max_length=64)
    phases: FormulaPhases


class FormulaUpdate(FormulaCreate):
    pass


class FormulaIngredientOutput(BaseModel):
    inci: str
    name: str | None = None
    smiles: str | None = None
    weight_pct: float
    phase: str
    is_locked: bool

    model_config = {"from_attributes": True}


class FormulaResponse(BaseModel):
    formula_id: str
    name: str
    category: str | None = None
    batch_size_g: float
    notes: str | None = None
    project_id: str | None = None
    total_weight_pct: float
    status: str
    updated_at: datetime
    ingredients: list[FormulaIngredientOutput] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FormulaVersionOutput(BaseModel):
    version: int
    snapshot: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class FormulaAdjustmentRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)


class FormulaChangeItem(BaseModel):
    ingredient_id: str
    name: str
    inci: str
    phase: str
    old_pct: float
    new_pct: float
    action: str = "modified"  # modified, added, removed


class FormulaAdjustmentResponse(BaseModel):
    formula_id: str
    title: str
    explanation: str
    changes: list[FormulaChangeItem]
    updated_phases: FormulaPhases
    total_weight_pct: float


class FormulaChatMessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=10000)
    proposal: dict | None = None
    linked_artifact_id: str | None = None


class FormulaChatMessageOutput(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    proposal: dict | None = None
    linked_artifact_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
