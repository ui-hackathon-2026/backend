"""Ingest compliance data from 'scrape-compliance' into Neon Postgres.

Loads:
1. regulatory_knowledge_chunks.json -> knowledge_chunks table (118 chunks)
2. lampiran_V_raw.json -> prohibited_substances table (1,706 entries)
3. Deterministic BPOM limits from chunks -> bpom_limits table
4. Curated high-risk banned substances (Hydroquinone, Deoxyarbutin, Mercury, etc.)
"""

import json
import os
import re
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.compliance import BpomLimit, ProhibitedSubstance
from app.models.knowledge import KnowledgeChunk

SCRAPE_DIR = Path("D:/Projects/Web Shi/UI Hackathon scrape-compliance")
FINAL_CHUNKS_PATH = SCRAPE_DIR / "data" / "final" / "regulatory_knowledge_chunks.json"
RAW_LAMPIRAN_V_PATH = SCRAPE_DIR / "data" / "raw" / "lampiran_V_raw.json"


def ingest_knowledge_chunks(db):
    print(f"Reading chunks from: {FINAL_CHUNKS_PATH}")
    if not FINAL_CHUNKS_PATH.exists():
        raise FileNotFoundError(f"Missing chunks file: {FINAL_CHUNKS_PATH}")

    with open(FINAL_CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)

    print(f"Found {len(chunks_data)} chunks to ingest.")

    count = 0
    for item in chunks_data:
        chunk_id = item["chunk_id"]
        content = item.get("content", {})
        regulation = item.get("regulation", {})
        substance = item.get("substance", {})
        limits = item.get("limits", {})
        halal = item.get("halal", {})
        retrieval = item.get("retrieval", {})

        existing = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
        if existing:
            chunk = existing
        else:
            chunk = KnowledgeChunk(id=chunk_id)
            db.add(chunk)

        chunk.title = content.get("title", "")[:512]
        chunk.raw_text = content.get("raw_text", "")
        chunk.regulation = regulation.get("name", "Peraturan BPOM No. 25 Tahun 2025")[:255]
        chunk.appendix = regulation.get("appendix", "")[:255]
        chunk.clause_entry = regulation.get("clause_entry", "")[:128]
        chunk.source_url = regulation.get("source_url")

        chunk.category = substance.get("category", "restricted_use")[:64]
        chunk.substance_name = substance.get("substance_name", "")[:255]
        chunk.inci_name = substance.get("inci_name")[:255] if substance.get("inci_name") else None
        chunk.synonyms = substance.get("synonyms", [])
        chunk.cas_number = substance.get("cas_number")[:64] if substance.get("cas_number") else None
        chunk.acd_number = str(substance.get("acd_number"))[:32] if substance.get("acd_number") else None

        chunk.max_concentration_pct = limits.get("max_concentration_pct")
        chunk.concentration_note_raw = limits.get("concentration_note_raw")
        chunk.allowed_product_types = limits.get("allowed_product_types", [])
        chunk.conditions_of_use = limits.get("conditions_of_use", "")
        chunk.mandatory_warnings = limits.get("mandatory_warnings", [])

        chunk.halal_critical_point = halal.get("critical_point")

        chunk.tags = retrieval.get("tags", [])
        chunk.chunk_type = retrieval.get("chunk_type")
        chunk.extraction_confidence = retrieval.get("extraction_confidence")

        count += 1

    db.commit()
    print(f"Successfully upserted {count} KnowledgeChunk records.")
    return chunks_data


def ingest_prohibited_substances(db):
    print(f"Reading prohibited substances from: {RAW_LAMPIRAN_V_PATH}")
    if not RAW_LAMPIRAN_V_PATH.exists():
        print("Warning: lampiran_V_raw.json not found, falling back to curated list.")
        raw_items = []
    else:
        with open(RAW_LAMPIRAN_V_PATH, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

    print(f"Found {len(raw_items)} raw prohibited items.")

    # Wipe existing table to avoid duplicate appends
    db.query(ProhibitedSubstance).delete()
    db.commit()

    count = 0
    # Add raw table items
    for item in raw_items:
        name = item.get("nama_bahan", "").strip()
        if not name:
            continue
        entry_no = str(item.get("entry_no", ""))
        cas = item.get("no_cas")
        db.add(ProhibitedSubstance(
            name=name,
            cas_number=cas[:255] if cas else None,
            entry_no=entry_no[:32] if entry_no else None,
        ))
        count += 1

    # Ensure curated prohibited substances and aliases are explicitly present
    curated_banned = [
        ("Hydroquinone", "123-31-9", "384"),
        ("1,4-Dihydroxybenzene (Hydroquinone)", "123-31-9", "384"),
        ("Deoxyarbutin", "53936-56-4", "1375"),
        ("Deoxyarbutin, Tetrahydropyranyloxy Phenol", "53936-56-4", "1375"),
        ("Mercury and its compounds", "7439-97-6", "221"),
        ("Air raksa dan senyawanya (Mercury)", "7439-97-6", "221"),
        ("Retinoic acid and its salts (Tretinoin)", "302-79-4", "375"),
        ("Asam retinoat dan garamnya (Tretinoin)", "302-79-4", "375"),
        ("Betamethasone", "378-44-9", "300"),
        ("Dexamethasone", "50-02-2", "301"),
        ("Chloroform", "67-66-3", "366"),
        ("Bithionol", "97-18-7", "283"),
    ]

    for name, cas, entry in curated_banned:
        db.add(ProhibitedSubstance(
            name=name,
            cas_number=cas,
            entry_no=entry,
        ))
        count += 1

    db.commit()
    print(f"Successfully inserted {count} ProhibitedSubstance records.")


def ingest_bpom_limits(db, chunks_data):
    print("Extracting BPOM limits from knowledge chunks...")
    db.query(BpomLimit).delete()
    db.commit()

    count = 0
    seen_inci = set()

    # Common hard limits in cosmetics under BPOM 25/2025
    standard_limits = [
        ("Phenoxyethanol", 1.0, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 29"),
        ("Salicylic Acid", 2.0, "restricted_use", "Peraturan BPOM No. 25 Tahun 2025 Lampiran I No. 124"),
        ("Ethylhexyl Methoxycinnamate", 10.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 12"),
        ("Zinc Oxide", 25.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 33"),
        ("Titanium Dioxide", 25.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 27"),
        ("Chlorphenesin", 0.3, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 34"),
        ("Dehydroacetic acid", 0.6, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 1"),
        ("Methylparaben", 0.4, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 12"),
        ("Propylparaben", 0.14, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 12"),
        ("Sodium Benzoate", 0.5, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 1"),
        ("Potassium Sorbate", 0.6, "preservative", "Peraturan BPOM No. 25 Tahun 2025 Lampiran III No. 4"),
        ("Benzophenone-3", 6.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 4"),
        ("Octocrylene", 10.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 10"),
        ("Homosalate", 10.0, "uv_filter", "Peraturan BPOM No. 25 Tahun 2025 Lampiran IV No. 3"),
    ]

    for inci, max_pct, cat, reg_ref in standard_limits:
        db.add(BpomLimit(
            inci=inci,
            max_pct=max_pct,
            category=cat,
            regulation_ref=reg_ref,
        ))
        seen_inci.add(inci.lower())
        count += 1

    # Now add limits from chunks data
    for item in chunks_data:
        substance = item.get("substance", {})
        limits = item.get("limits", {})
        inci = substance.get("inci_name")
        max_pct = limits.get("max_concentration_pct")
        cat = substance.get("category", "preservative")
        clause = item.get("regulation", {}).get("clause_entry", "")
        appendix = item.get("regulation", {}).get("appendix", "")

        if inci and max_pct is not None and max_pct > 0 and inci.lower() not in seen_inci:
            reg_ref = f"Peraturan BPOM No. 25 Tahun 2025 {appendix} {clause}".strip()
            db.add(BpomLimit(
                inci=inci,
                max_pct=float(max_pct),
                category=cat,
                regulation_ref=reg_ref[:255],
            ))
            seen_inci.add(inci.lower())
            count += 1

    db.commit()
    print(f"Successfully inserted {count} BpomLimit records.")


def main():
    print("=== Starting Compliance Data Ingestion ===")
    db = SessionLocal()
    try:
        chunks_data = ingest_knowledge_chunks(db)
        ingest_prohibited_substances(db)
        ingest_bpom_limits(db, chunks_data)
        print("=== Ingestion Finished Successfully ===")
    except Exception as e:
        db.rollback()
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
