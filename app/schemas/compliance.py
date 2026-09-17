from pydantic import BaseModel, Field


class AuditIngredientInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inci: str = Field(min_length=1, max_length=255)
    smiles: str | None = Field(default=None, max_length=1024)
    weight_pct: float = Field(ge=0, le=100)
    phase: str | None = Field(default=None, max_length=1)
    role: str | None = Field(default=None, max_length=32)


class ComplianceAuditRequest(BaseModel):
    formula_name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    target_audience: str | None = Field(default=None, max_length=128)
    ingredients: list[AuditIngredientInput] = Field(min_length=1)


class RagCitation(BaseModel):
    regulation: str
    appendix: str
    clause_number: str
    excerpt: str


class IngredientAudit(BaseModel):
    ingredient_id: str
    name: str
    inci: str
    weight_pct: float
    status: str
    bpom_limit_pct: float | None = None
    halal_status: str
    tkdn_pct: float
    rag_citation: RagCitation | None = None
    audit_notes: str


class SubstitutionRecommendation(BaseModel):
    current_ingredient: str
    recommended_local: str
    tkdn_impact: str | None = None
    rationale: str


class LlmReasoning(BaseModel):
    toxicology_evaluation: str
    mandatory_label_warnings: list[str] = Field(default_factory=list)
    local_substitution_recommendations: list[SubstitutionRecommendation] = Field(
        default_factory=list
    )


class ComplianceAuditResponse(BaseModel):
    audit_id: str
    formula_name: str | None = None
    overall_status: str
    compliance_score: float
    halal_status: str
    total_tkdn_pct: float
    summary_verdict: str
    ingredients_audit: list[IngredientAudit]
    llm_reasoning: LlmReasoning


class AskRagRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category_context: str | None = Field(default=None, max_length=128)
    active_formula_id: str | None = Field(default=None, max_length=64)


class AskRagCitation(BaseModel):
    document: str
    clause: str
    text: str


class AskRagResponse(BaseModel):
    answer: str
    citations: list[AskRagCitation] = Field(default_factory=list)
    confidence_score: float
