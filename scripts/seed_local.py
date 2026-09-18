"""One-off local seeding script.

Populates a freshly migrated (empty) local Postgres database from the raw
datasets already checked into sibling repos (../experiments, ../supplier-search,
../scrape-compliance, ../scrape-external-products) and from the frontend's
ingredient catalog mock (the actual source of truth for app ingredients,
../../frontend/src/data/mock/ingredientsCatalog.ts).

Idempotent: each seed_* function skips if its table already has rows.

Run from backend/ with the venv active:
    python scripts/seed_local.py
"""

import csv
import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.catalog import Supplier
from app.models.compliance import BpomLimit, ProhibitedSubstance
from app.models.competitor import CompetitorProduct
from app.models.formula import Formula, FormulaIngredient
from app.models.ingredient import Ingredient
from app.models.knowledge import KnowledgeChunk

ROOT = Path(__file__).resolve().parents[2]  # .../hack-ui
BACKEND = ROOT / "backend"
EXPERIMENTS = ROOT / "experiments"
SUPPLIER_SEARCH = ROOT / "supplier-search"
SCRAPE_COMPLIANCE = ROOT / "scrape-compliance"
SCRAPE_EXTERNAL = ROOT / "scrape-external-products"
FRONTEND_CATALOG = ROOT / "frontend" / "src" / "data" / "mock" / "ingredientsCatalog.ts"

PHASE_MAP = {"oil": "A", "water": "B", "emulsifier": "C", "active": "D", "cool_down": "D"}


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    f = parse_float(value)
    return int(f) if f is not None else None


def parse_frontend_catalog() -> list[dict]:
    text = FRONTEND_CATALOG.read_text(encoding="utf-8")
    items = []
    for block in re.findall(r"\{\s*id:.*?\},", text, re.DOTALL):
        def field(name, quoted=True):
            pattern = rf'{name}:\s*"([^"]*)"' if quoted else rf"{name}:\s*([\d.]+)"
            m = re.search(pattern, block)
            return m.group(1) if m else None

        items.append(
            {
                "id": field("id"),
                "name": field("name"),
                "inci": field("inci"),
                "smiles": field("smiles"),
                "default_phase": field("defaultPhase"),
                "default_weight_pct": float(field("defaultWeightPct", quoted=False) or 0),
                "role": field("role"),
                "description": field("description"),
            }
        )
    return items


def load_experiments_ingredients() -> dict[str, dict]:
    path = EXPERIMENTS / "seeding" / "ingredients.csv"
    by_inci = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_inci[row["inci_name"]] = row
    return by_inci


def seed_ingredients(db: Session) -> None:
    if db.query(Ingredient).count() > 0:
        print("ingredients: already seeded, skipping")
        return

    catalog = parse_frontend_catalog()
    molecular = load_experiments_ingredients()

    for item in catalog:
        extra = molecular.get(item["inci"], {})
        db.add(
            Ingredient(
                inci=item["inci"],
                synonyms=[],
                name=item["name"],
                smiles=item["smiles"] or "",
                cas_number=extra.get("cas_number") or None,
                default_phase=item["default_phase"],
                default_role=item["role"],
                hlb=parse_float(extra.get("hlb")),
                default_weight_pct=item["default_weight_pct"],
                cost_per_kg_idr=0.0,
                tkdn_pct=0.0,
                halal_status="HALAL",
                description=item["description"],
                entity_type=extra.get("entity_type") or None,
                identity_source=extra.get("identity_source") or None,
                identity_confidence=parse_float(extra.get("identity_confidence")),
                structure_representation_type=extra.get("structure_representation_type") or None,
                molecular_weight=parse_float(extra.get("molecular_weight")),
                logp=parse_float(extra.get("logp")),
                tpsa=parse_float(extra.get("tpsa")),
                hbd=parse_int(extra.get("hbd")),
                hba=parse_int(extra.get("hba")),
            )
        )
    db.commit()
    print(f"ingredients: seeded {len(catalog)} rows from frontend catalog "
          f"(enriched {sum(1 for i in catalog if i['inci'] in molecular)} with molecular descriptors)")


def seed_suppliers(db: Session) -> None:
    if db.query(Supplier).count() > 0:
        print("suppliers: already seeded, skipping")
        return

    path = SUPPLIER_SEARCH / "synthetic_data" / "suppliers_synthetic_flat.csv"
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.add(
                Supplier(
                    name=row["supplier_name"],
                    ingredient_inci=row["ingredient_inci"] or None,
                    grade=row["grade"] or None,
                    halal_certified=parse_bool(row["halal_cert"]),
                    lead_time_days=parse_int(row["lead_time_days"]),
                    price_per_kg_idr=parse_float(row["price_per_kg_idr"]),
                    city=row["city"] or None,
                    province=row["province"] or None,
                    lat=parse_float(row["lat"]),
                    lon=parse_float(row["lon"]),
                    moq_kg=parse_float(row["moq_kg"]),
                    is_synthetic=parse_bool(row["is_synthetic"]),
                    external_ref=row["offering_id"] or None,
                    notes=f"tkdn_pct={row.get('tkdn_pct', '')}; source={row.get('source', '')}",
                )
            )
            count += 1
    db.commit()
    print(f"suppliers: seeded {count} rows from supplier-search synthetic data")


def seed_knowledge_chunks(db: Session) -> list[dict]:
    path = SCRAPE_COMPLIANCE / "data" / "final" / "regulatory_knowledge_chunks.json"
    chunks = json.loads(path.read_text(encoding="utf-8"))

    if db.query(KnowledgeChunk).count() > 0:
        print("knowledge_chunks: already seeded, skipping")
        return chunks

    for c in chunks:
        db.add(
            KnowledgeChunk(
                id=c["chunk_id"],
                title=c["content"]["title"],
                regulation=c["regulation"]["name"],
                appendix=c["regulation"].get("appendix", ""),
                clause_entry=c["regulation"].get("clause_entry", ""),
                category=c["substance"]["category"],
                substance_name=c["substance"]["substance_name"],
                inci_name=c["substance"].get("inci_name"),
                synonyms=c["substance"].get("synonyms", []),
                cas_number=c["substance"].get("cas_number"),
                acd_number=c["substance"].get("acd_number"),
                max_concentration_pct=c["limits"].get("max_concentration_pct"),
                concentration_note_raw=c["limits"].get("concentration_note_raw"),
                extraction_confidence=c["retrieval"].get("extraction_confidence"),
                chunk_type=c["retrieval"].get("chunk_type"),
                allowed_product_types=c["limits"].get("allowed_product_types", []),
                conditions_of_use=c["limits"].get("conditions_of_use", ""),
                mandatory_warnings=c["limits"].get("mandatory_warnings", []),
                tags=c["retrieval"].get("tags", []),
                raw_text=c["content"].get("raw_text", ""),
                halal_critical_point=c["halal"].get("critical_point"),
                source_url=c["regulation"].get("source_url"),
            )
        )
    db.commit()
    print(f"knowledge_chunks: seeded {len(chunks)} rows from scrape-compliance")
    return chunks


def seed_bpom_limits(db: Session, chunks: list[dict]) -> None:
    if db.query(BpomLimit).count() > 0:
        print("bpom_limits: already seeded, skipping")
        return

    seen = set()
    count = 0
    for c in chunks:
        inci = c["substance"].get("inci_name")
        max_pct = c["limits"].get("max_concentration_pct")
        if not inci or max_pct is None or inci in seen:
            continue
        seen.add(inci)
        db.add(
            BpomLimit(
                inci=inci,
                max_pct=max_pct,
                category=c["substance"]["category"],
                regulation_ref=c["regulation"]["name"],
            )
        )
        count += 1
    db.commit()
    print(f"bpom_limits: seeded {count} rows derived from knowledge_chunks numeric limits "
          f"(source of the original 6-row Neon seed could not be traced to any script/file in "
          f"the repos; this is a broader, reproducible replacement covering all chunks with a "
          f"numeric max_concentration_pct)")


def seed_prohibited_substances(db: Session) -> None:
    if db.query(ProhibitedSubstance).count() > 0:
        print("prohibited_substances: already seeded, skipping")
        return

    path = SCRAPE_COMPLIANCE / "data" / "raw" / "lampiran_V_raw.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    for e in entries:
        name = re.sub(r"\s+", " ", e.get("nama_bahan", "")).strip()
        if not name:
            continue
        db.add(
            ProhibitedSubstance(
                name=name,
                cas_number=e.get("no_cas") or None,
                entry_no=e.get("entry_no") or None,
            )
        )
    db.commit()
    print(f"prohibited_substances: seeded {len(entries)} rows from Lampiran V raw extraction")


def seed_competitor_products(db: Session) -> None:
    if db.query(CompetitorProduct).count() > 0:
        print("competitor_products: already seeded, skipping")
        return

    path = SCRAPE_EXTERNAL / "inci_scraper" / "out" / "products.csv"
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            inci_list = [x.strip() for x in row["inci_list"].split("|") if x.strip()]
            db.add(
                CompetitorProduct(
                    brand=row["brand"],
                    slug=row["product_slug"],
                    name=row["product_name"],
                    url=row["url"],
                    inci_list=inci_list,
                    ingredient_count=parse_int(row["ingredient_count"]) or len(inci_list),
                )
            )
            count += 1
    db.commit()
    print(f"competitor_products: seeded {count} rows from scrape-external-products")


def seed_formulas(db: Session) -> None:
    """Import the experiments/seeding formulation history straight into the
    app's own formulas/formula_ingredients tables (owner_id=NULL), as if
    they were produced through the workbench/editor, per user direction.
    """
    if db.query(Formula).count() > 0:
        print("formulas: already seeded, skipping")
        return

    ingredients_by_id = {}
    with open(EXPERIMENTS / "seeding" / "ingredients.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ingredients_by_id[row["ingredient_id"]] = row

    formulations = {}
    with open(EXPERIMENTS / "seeding" / "formulations.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            formulations[row["formulation_id"]] = row

    formulation_ingredient_rows = {}
    with open(EXPERIMENTS / "seeding" / "formulation_ingredients.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            formulation_ingredient_rows.setdefault(row["formulation_id"], []).append(row)

    formula_count = 0
    ingredient_count = 0
    for formulation_id, formulation in formulations.items():
        rows = formulation_ingredient_rows.get(formulation_id, [])
        if not rows:
            continue

        formula = Formula(
            id=formulation_id,
            name=f"{formulation.get('product_family', 'formula').replace('_', ' ').title()} ({formulation_id})",
            category=formulation.get("domain") or None,
            owner_id=None,
            project_id=None,
            notes=f"source_id={formulation.get('source_id', '')}; "
            f"{formulation.get('provenance_note', '')}",
        )
        db.add(formula)
        formula_count += 1

        for ing_row in rows:
            ref = ingredients_by_id.get(ing_row["ingredient_id"], {})
            name = ref.get("canonical_name") or ing_row.get("raw_name") or ing_row["ingredient_id"]
            inci = ref.get("inci_name") or ing_row.get("raw_name") or ing_row["ingredient_id"]
            db.add(
                FormulaIngredient(
                    formula_id=formulation_id,
                    phase=PHASE_MAP.get(ing_row.get("phase", ""), "D"),
                    inci=inci,
                    name=name,
                    smiles=ref.get("smiles") or None,
                    weight_pct=parse_float(ing_row.get("percentage")) or 0.0,
                    role=ing_row.get("role") or None,
                )
            )
            ingredient_count += 1

    db.commit()
    print(f"formulas: seeded {formula_count} formulas / {ingredient_count} ingredient rows "
          f"from experiments/seeding (formulations.csv + formulation_ingredients.csv), owner_id=NULL")


def main() -> None:
    with Session(engine) as db:
        seed_ingredients(db)
        seed_suppliers(db)
        chunks = seed_knowledge_chunks(db)
        if chunks is None:
            chunks = json.loads(
                (SCRAPE_COMPLIANCE / "data" / "final" / "regulatory_knowledge_chunks.json").read_text(
                    encoding="utf-8"
                )
            )
        seed_bpom_limits(db, chunks)
        seed_prohibited_substances(db)
        seed_competitor_products(db)
        seed_formulas(db)


if __name__ == "__main__":
    main()
