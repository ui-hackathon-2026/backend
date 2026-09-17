from pydantic import BaseModel, Field


class ProjectBriefInput(BaseModel):
    projectName: str = Field(min_length=1, max_length=255)
    brand: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=128)
    skinProfile: str | None = Field(default=None, max_length=255)
    sensoryFinish: str | None = Field(default=None, max_length=255)
    targetSpf: float | None = Field(default=None, ge=0, le=100)
    targetViscosityMpaS: float | None = Field(default=None, gt=0)
    maxCogsIdrPerKg: float | None = Field(default=None, gt=0)
    targetTkdnPct: float | None = Field(default=None, ge=0, le=100)
    selectedHeroIngredients: list[str] = Field(default_factory=list)
    specialInstructions: str | None = Field(default=None, max_length=4000)


class BlueprintIngredient(BaseModel):
    id: str
    name: str
    inci: str
    phase: str
    weightPct: float
    functionDesc: str
    isLocalTkdn: bool


class FormulationBlueprint(BaseModel):
    id: str
    title: str
    category: str | None = None
    brand: str | None = None
    targetSpf: float | None = None
    estimatedViscosityMpaS: float
    estimatedCogsIdrPerKg: float
    calculatedTkdnPct: float
    systemHlb: float
    scientificRationale: str
    ingredients: list[BlueprintIngredient]


class ExtractedBrief(BaseModel):
    projectName: str | None = None
    brand: str | None = None
    category: str | None = None
    targetViscosityMpaS: float | None = None
    maxCogsIdrPerKg: float | None = None


class ParseBriefResponse(BaseModel):
    extractedBrief: ExtractedBrief
    detectedClaims: list[str] = Field(default_factory=list)
    suggestedHeroIngredients: list[str] = Field(default_factory=list)


class ChassisIngredient(BaseModel):
    name: str
    inci: str
    phase: str
    weightPct: float
    functionDesc: str


class ChassisModel(BaseModel):
    id: str
    brand: str
    name: str
    category: str
    description: str
    baseViscosity: float = 0.0
    cogsIdrPerKg: float = 0.0
    tkdnPct: float = 0.0
    ingredients: list[ChassisIngredient] = Field(default_factory=list)


class HeroIngredient(BaseModel):
    id: str
    name: str
    inci: str
    localOrigin: str | None = None
    benefit: str
    isLocalTkdn: bool
