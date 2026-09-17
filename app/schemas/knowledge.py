from pydantic import BaseModel, Field


class SimilarityIngredient(BaseModel):
    inci: str = Field(min_length=1, max_length=255)
    weight_pct: float = Field(gt=0, le=100)


class SimilarityRequest(BaseModel):
    ingredients: list[SimilarityIngredient] = Field(min_length=1)


class SimilarityMatch(BaseModel):
    formula_id: str
    name: str
    jaccard: float
    cosine: float
    chassis_overlap_pct: float


class SimilarityResponse(BaseModel):
    matches: list[SimilarityMatch]


class ExternalSimilarityRequest(BaseModel):
    ingredients: list[SimilarityIngredient] = Field(min_length=1)


class ExternalMatch(BaseModel):
    brand: str
    product_name: str
    url: str
    similarity: float
    shared_ingredients: list[str] = Field(default_factory=list)


class ExternalSimilarityResponse(BaseModel):
    novelty_score: float
    estimated_basis: str
    top_matches: list[ExternalMatch] = Field(default_factory=list)


class FtoRequest(BaseModel):
    ingredients: list[SimilarityIngredient] = Field(min_length=1)


class ConformerRequest(BaseModel):
    smiles: str = Field(min_length=1, max_length=1024)
    name: str | None = Field(default=None, max_length=255)
    energy_minimize: bool = True


class SupplierResponse(BaseModel):
    id: int
    name: str
    ingredient_inci: str | None = None
    grade: str | None = None
    halal_certified: bool = False
    lead_time_days: int | None = None
    price_per_kg_idr: float | None = None

    model_config = {"from_attributes": True}
