"""Project Brief Studio orchestration over existing engines.

Synthesize reuses the greedy optimizer for recipe math and the LLM
gateway for narrative rationale. Chassis models are curated static
templates, hero ingredients read the TKDN catalog live.
"""

import re
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.core.llm import GroqGateway, get_groq_gateway
from app.models.ingredient import Ingredient
from app.schemas.optimize import OptimizeRequest, TargetObjectives
from app.schemas.orchestrator import (
    BlueprintIngredient,
    ChassisIngredient,
    ChassisModel,
    ExtractedBrief,
    FormulationBlueprint,
    HeroIngredient,
    ParseBriefResponse,
    ProjectBriefInput,
)
from app.services.optimization_service import POOL, run_optimization
from app.services.project_service import BriefRejectedError, extract_text

FUNCTION_DESC = {
    "solvent": "Solven Fase Air (Pelarut Utama)",
    "humectant": "Humektan Penahan Kelembaban",
    "emollient": "Emolien Fase Minyak",
    "emulsifier": "Pengemulsi Non-Ionik",
    "thickener": "Pengental Polimer",
    "active": "Bahan Aktif Fungsional",
    "preservative": "Pengawet Spektrum Luas",
    "chelating": "Pengkelat Ion Logam",
    "uv_filter": "Filter UV",
    "antioxidant": "Antioksidan Lipid",
    "fragrance": "Pewangi",
    "ph_adjuster": "Penyeimbang pH",
}

RATIONALE_SYSTEM = (
    "Given a cosmetic formulation blueprint as JSON, write a concise "
    "scientific rationale in Bahasa Indonesia (2-3 sentences) explaining "
    "the emulsion system and hero ingredients. Return valid JSON with "
    "a single key: rationale."
)

BRIEF_PARSE_SYSTEM = (
    "Extract a cosmetic marketing brief as JSON with keys: projectName "
    "(string or null), brand (string or null), category (string or null), "
    "targetViscosityMpaS (number or null), maxCogsIdrPerKg (number or null), "
    "detectedClaims (array of marketing claim strings), "
    "suggestedHeroIngredients (array of local botanical ingredient names). "
    "Return valid JSON only."
)

CHASSIS = [
    {
        "id": "chassis-wardah-hydra",
        "brand": "Wardah",
        "name": "Hydra Rose Gel Base",
        "category": "Gel-Cream",
        "description": "Basis gel-cream hidrasi mass-prestige halal.",
        "ingredients": [
            ("Aqua Demineralisata", "Aqua", "B", 78.0),
            ("Glycerin", "Glycerin", "B", 5.0),
            ("Butylene Glycol", "Butylene Glycol", "B", 3.0),
            ("Caprylic Triglyceride", "Caprylic/Capric Triglyceride", "A", 4.0),
            ("Dimethicone", "Dimethicone", "A", 1.5),
            ("Glyceryl Stearate", "Glyceryl Stearate", "C", 2.5),
            ("Polysorbate 60", "Polysorbate 60", "C", 1.0),
            ("Niacinamide", "Niacinamide", "D", 2.0),
            ("Panthenol", "Panthenol", "D", 1.0),
            ("Phenoxyethanol", "Phenoxyethanol", "D", 0.8),
            ("Tocopheryl Acetate", "Tocopheryl Acetate", "A", 0.5),
            ("Allantoin", "Allantoin", "D", 0.5),
            ("Disodium EDTA", "Disodium EDTA", "B", 0.1),
            ("Xanthan Gum", "Xanthan Gum", "B", 0.1),
        ],
    },
    {
        "id": "chassis-kahf-lotion",
        "brand": "Kahf",
        "name": "Daily Men Lotion Base",
        "category": "Lotion",
        "description": "Basis lotion pria halal berprofil matte.",
        "ingredients": [
            ("Aqua Demineralisata", "Aqua", "B", 78.0),
            ("Glycerin", "Glycerin", "B", 4.0),
            ("Propylene Glycol", "Propylene Glycol", "B", 2.0),
            ("Squalane", "Squalane", "A", 3.0),
            ("Dimethicone", "Dimethicone", "A", 2.0),
            ("Glyceryl Stearate", "Glyceryl Stearate", "C", 3.0),
            ("Polyglyceryl Ester", "Polyglyceryl-3 Polyricinoleate", "C", 1.5),
            ("Niacinamide", "Niacinamide", "D", 3.0),
            ("Panthenol", "Panthenol", "D", 1.5),
            ("Allantoin", "Allantoin", "D", 0.5),
            ("Tocopheryl Acetate", "Tocopheryl Acetate", "A", 0.5),
            ("Chlorphenesin", "Chlorphenesin", "D", 0.2),
            ("Disodium EDTA", "Disodium EDTA", "B", 0.1),
            ("Carbomer", "Carbomer", "B", 0.3),
            ("Triethanolamine", "Triethanolamine", "D", 0.3),
            ("Citric Acid", "Citric Acid", "B", 0.1),
        ],
    },
    {
        "id": "chassis-emina-gel",
        "brand": "Emina",
        "name": "Light Teen Gel Base",
        "category": "Gel",
        "description": "Basis gel ringan ceria untuk remaja.",
        "ingredients": [
            ("Aqua Demineralisata", "Aqua", "B", 82.0),
            ("Butylene Glycol", "Butylene Glycol", "B", 4.0),
            ("Glycerin", "Glycerin", "B", 3.0),
            ("Dimethicone", "Dimethicone", "A", 1.0),
            ("Caprylic Triglyceride", "Caprylic/Capric Triglyceride", "A", 2.0),
            ("Polysorbate 60", "Polysorbate 60", "C", 1.2),
            ("Glyceryl Stearate", "Glyceryl Stearate", "C", 1.8),
            ("Niacinamide", "Niacinamide", "D", 2.0),
            ("Centella Extract", "Centella Asiatica Leaf Extract", "D", 1.5),
            ("Panthenol", "Panthenol", "D", 0.5),
            ("Chlorphenesin", "Chlorphenesin", "D", 0.2),
            ("Disodium EDTA", "Disodium EDTA", "B", 0.1),
            ("Xanthan Gum", "Xanthan Gum", "B", 0.4),
            ("Citric Acid", "Citric Acid", "B", 0.1),
            ("Tocopheryl Acetate", "Tocopheryl Acetate", "A", 0.2),
        ],
    },
    {
        "id": "chassis-labore-sensitive",
        "brand": "Labore",
        "name": "Sensitive Microbiome Base",
        "category": "Cream",
        "description": "Basis krim sensitif ramah mikrobioma tropis.",
        "ingredients": [
            ("Aqua Demineralisata", "Aqua", "B", 81.0),
            ("Glycerin", "Glycerin", "B", 4.5),
            ("Butylene Glycol", "Butylene Glycol", "B", 2.5),
            ("Squalane", "Squalane", "A", 2.5),
            ("Caprylic Triglyceride", "Caprylic/Capric Triglyceride", "A", 2.0),
            ("Polyglyceryl Ester", "Polyglyceryl-3 Polyricinoleate", "C", 2.0),
            ("Glyceryl Stearate", "Glyceryl Stearate", "C", 1.5),
            ("Panthenol", "Panthenol", "D", 1.5),
            ("Allantoin", "Allantoin", "D", 0.5),
            ("Centella Extract", "Centella Asiatica Leaf Extract", "D", 1.0),
            ("Tocopheryl Acetate", "Tocopheryl Acetate", "A", 0.3),
            ("Chlorphenesin", "Chlorphenesin", "D", 0.2),
            ("Disodium EDTA", "Disodium EDTA", "B", 0.1),
            ("Xanthan Gum", "Xanthan Gum", "B", 0.3),
            ("Citric Acid", "Citric Acid", "B", 0.1),
        ],
    },
]


def slug(inci: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", inci.lower()).strip("-")


def catalog_map(db: Session) -> dict:
    try:
        return {row.inci: row for row in db.query(Ingredient).all()}
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def synthesize(
    db: Session, body: ProjectBriefInput, gateway: GroqGateway | None = None
) -> FormulationBlueprint:
    if body.targetViscosityMpaS is not None and not (
        500 <= body.targetViscosityMpaS <= 100000
    ):
        raise FormulaWeightError("target viscosity must be within 500-100000 mPa.s")
    if body.maxCogsIdrPerKg is not None and body.maxCogsIdrPerKg < 10000:
        raise FormulaWeightError("max COGS must be at least 10000 IDR per kg")
    catalog = catalog_map(db)
    result = run_optimization(
        db,
        OptimizeRequest(
            num_trials=60,
            target_objectives=TargetObjectives(
                target_viscosity_mpas=body.targetViscosityMpaS or 5500.0
            ),
        ),
        seed=11,
        max_cogs=body.maxCogsIdrPerKg,
    )
    best = sorted(
        result.top_candidates, key=lambda c: c.stability, reverse=True
    )[0]
    viscosity = estimate_viscosity(db, best.recipe)
    pool_meta = {inci: (phase, role, hlb) for inci, phase, role, hlb in POOL}
    items: list[BlueprintIngredient] = []
    hlb_num = 0.0
    hlb_den = 0.0
    for position, (inci, pct) in enumerate(best.recipe.items()):
        phase, role, hlb = pool_meta.get(inci, ("B", "active", None))
        known = catalog.get(inci)
        if hlb is not None:
            hlb_num += hlb * pct
            hlb_den += pct
        items.append(
            BlueprintIngredient(
                id=f"ing-{position + 1}",
                name=known.name if known else inci,
                inci=inci,
                phase=phase,
                weightPct=pct,
                functionDesc=FUNCTION_DESC.get(role, role),
                isLocalTkdn=(known.tkdn_pct or 0.0) > 0 if known else False,
            )
        )
    system_hlb = round(hlb_num / hlb_den, 1) if hlb_den > 0 else 0.0
    rationale = build_rationale(
        gateway,
        {
            "project": body.projectName,
            "brand": body.brand,
            "category": body.category,
            "recipe": best.recipe,
            "heroes": body.selectedHeroIngredients,
        },
    )
    return FormulationBlueprint(
        id=f"bp_{secrets.token_hex(6)}",
        title=f"{body.projectName} Architecture v1.0",
        category=body.category,
        brand=body.brand,
        targetSpf=body.targetSpf,
        estimatedViscosityMpaS=viscosity,
        estimatedCogsIdrPerKg=best.cogs_idr_per_kg,
        calculatedTkdnPct=best.tkdn_pct,
        systemHlb=system_hlb,
        scientificRationale=rationale,
        ingredients=items,
    )


def estimate_viscosity(db: Session, recipe: dict[str, float]) -> float:
    from app.ml.predictor import get_lightgbm_predictor
    from app.services.optimization_service import recipe_features
    from app.services.simulation_service import StubPredictor

    try:
        predictor = get_lightgbm_predictor()
    except Exception:
        predictor = StubPredictor()
    try:
        known = {row.inci for row in db.query(Ingredient.inci).all()}
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    try:
        metrics = predictor.predict(recipe_features(db, recipe, known))
        return round(metrics["dynamic_viscosity_mpas"], 0)
    except Exception:
        return 5500.0


def build_rationale(
    gateway: GroqGateway | None, blueprint: dict
) -> str:
    import json as jsonlib

    active = gateway or get_groq_gateway()
    try:
        parsed = active.chat_json(
            [
                {
                    "role": "user",
                    "content": f"{RATIONALE_SYSTEM}\nBlueprint: {jsonlib.dumps(blueprint, ensure_ascii=False)}",
                }
            ],
            model=settings.groq_model_fast,
            max_tokens=1024,
        )
        rationale = str(parsed.get("rationale", "")).strip()
        if rationale:
            return rationale
    except Exception:
        pass
    return (
        "Sistem emulsi O/W lamellar dengan humektan dan polimer penstabil, "
        "dirancang tahan iklim tropis 40C."
    )


def parse_brief_pdf(
    filename: str, data: bytes, gateway: GroqGateway | None = None
) -> ParseBriefResponse:
    import json as jsonlib

    if not filename.lower().endswith(".pdf"):
        raise BriefRejectedError("only pdf briefs accepted")
    text = extract_text(data)
    if not text:
        raise BriefRejectedError("no extractable text found")
    active = gateway or get_groq_gateway()
    try:
        parsed = active.chat_json(
            [
                {
                    "role": "user",
                    "content": f"{BRIEF_PARSE_SYSTEM}\nDokumen:\n{text[:4000]}",
                }
            ],
            model=settings.groq_model_fast,
            max_tokens=1024,
        )
        brief = parsed if isinstance(parsed, dict) else {}
    except Exception:
        brief = {}
    return ParseBriefResponse(
        extractedBrief=ExtractedBrief(
            projectName=brief.get("projectName"),
            brand=brief.get("brand"),
            category=brief.get("category"),
            targetViscosityMpaS=brief.get("targetViscosityMpaS"),
            maxCogsIdrPerKg=brief.get("maxCogsIdrPerKg"),
        ),
        detectedClaims=list(brief.get("detectedClaims", [])),
        suggestedHeroIngredients=list(brief.get("suggestedHeroIngredients", [])),
    )


def list_chassis(db: Session) -> list[ChassisModel]:
    catalog = catalog_map(db)
    models: list[ChassisModel] = []
    for chassis in CHASSIS:
        items = []
        for position, (name, inci, phase, pct) in enumerate(chassis["ingredients"]):
            known = catalog.get(inci)
            role = None
            for pool_inci, pool_phase, pool_role, _ in POOL:
                if pool_inci == inci:
                    role = pool_role
                    break
            items.append(
                ChassisIngredient(
                    name=name,
                    inci=inci,
                    phase=phase,
                    weightPct=pct,
                    functionDesc=FUNCTION_DESC.get(role or "active", role or "active"),
                )
            )
        models.append(
            ChassisModel(
                id=chassis["id"],
                brand=chassis["brand"],
                name=chassis["name"],
                category=chassis["category"],
                description=chassis["description"],
                ingredients=items,
            )
        )
    return models


def list_heroes(db: Session) -> list[HeroIngredient]:
    try:
        rows = (
            db.query(Ingredient)
            .filter(Ingredient.tkdn_pct > 0)
            .order_by(Ingredient.tkdn_pct.desc())
            .all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [
        HeroIngredient(
            id=f"cat-{slug(row.inci)}",
            name=row.name,
            inci=row.inci,
            tkdn_pct=row.tkdn_pct or 0.0,
            provenance=row.origin,
            description=row.description,
        )
        for row in rows
    ]
