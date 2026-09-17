from pydantic import BaseModel, Field


class ComplianceIngredientInput(BaseModel):
    inci: str = Field(min_length=1, max_length=255)
    percentage: float = Field(ge=0, le=100)


class ComplianceRequest(BaseModel):
    formula_name: str | None = Field(default=None, max_length=255)
    formula_ingredients: list[ComplianceIngredientInput] = Field(min_length=1)


class BpomViolation(BaseModel):
    inci: str
    percentage: float
    max_allowed_pct: float


class BpomAudit(BaseModel):
    status: str
    violations: list[BpomViolation] = Field(default_factory=list)


class HalalAudit(BaseModel):
    status: str
    porcine_risk: str
    non_halal: list[str] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)


class TkdnAudit(BaseModel):
    score_pct: float
    meets_threshold: bool
    local_components: list[str] = Field(default_factory=list)


class ComplianceResponse(BaseModel):
    overall_status: str
    bpom_audit: BpomAudit
    halal_audit: HalalAudit
    tkdn_audit: TkdnAudit
