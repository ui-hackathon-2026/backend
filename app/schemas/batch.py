from datetime import datetime

from pydantic import BaseModel, Field


class BatchGenerateRequest(BaseModel):
    formula_id: str = Field(min_length=1, max_length=64)
    batch_size_grams: float = Field(gt=0, le=1000000)
    operator_name: str | None = Field(default=None, max_length=255)


class ScaledIngredient(BaseModel):
    phase: str
    inci: str
    grams: float


class BatchResponse(BaseModel):
    batch_record_id: str
    formula_id: str
    batch_size_grams: float
    operator_name: str | None = None
    scaled_ingredients: list[ScaledIngredient]
    shap_contributions: list[dict] = Field(default_factory=list)
    sop_steps: list[str]
    created_at: datetime
