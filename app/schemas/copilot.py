from pydantic import BaseModel, Field


class LockedActive(BaseModel):
    name: str
    pct: float | None = None


class FormulationSpec(BaseModel):
    product_category: str = "unknown"
    emulsion_type: str = "unknown"
    target_spf: float | None = None
    viscosity_target_range: list[float] | None = None
    locked_actives: list[LockedActive] = Field(default_factory=list)
    stability_requirement: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)
    canvas: dict | None = None
    brief_id: str | None = Field(default=None, max_length=64)
