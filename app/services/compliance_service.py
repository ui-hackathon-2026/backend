"""Hybrid regulatory audit: deterministic guard plus retrieval plus LLM.

Tier 1 verifies numbers against bpom_limits and the ingredients catalog,
retrieval grounds every per-ingredient citation in knowledge_chunks,
Tier 3 synthesizes toxicology narrative and label warnings through the
LLM gateway with a deterministic fallback when the engine is down.
"""

import re
import secrets
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.llm import GroqGateway, get_groq_gateway
from app.models.compliance import BpomLimit, ProhibitedSubstance
from app.models.ingredient import Ingredient
from app.models.knowledge import KnowledgeChunk
from app.schemas.compliance import (
    AskRagCitation,
    AskRagRequest,
    AskRagResponse,
    ComplianceAuditRequest,
    ComplianceAuditResponse,
    IngredientAudit,
    LlmReasoning,
    RagCitation,
    SubstitutionRecommendation,
)

TKDN_THRESHOLD_PCT = 40.0

REASONING_SYSTEM = (
    "You are a cosmetic regulatory assistant. Given audit findings as JSON, "
    "respond with JSON keys: toxicology_evaluation (string, Bahasa Indonesia), "
    "mandatory_label_warnings (array of strings), "
    "local_substitution_recommendations (array of {current_ingredient, "
    "recommended_local, tkdn_impact, rationale}; empty array when nothing "
    "needs substitution). Return valid JSON only."
)

RAG_SYSTEM = (
    "Answer the regulatory question in Bahasa Indonesia using only the "
    "provided excerpts. Respond with JSON keys: answer (string), "
    "confidence (number 0-1). Return valid JSON only."
)


def tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2}


def blocklist_head(name: str) -> str:
    cleaned = " ".join(name.split()).lower()
    cleaned = re.sub(r"\s+dan (garamnya|garam-garamnya|sediaannya|senyawanya)\s*$", "", cleaned)
    cleaned = re.split(r",?\s+bila\s+|\s+kecuali\s+", cleaned)[0]
    return cleaned.strip()


def blocklist_aliases(name: str) -> set[str]:
    found = {blocklist_head(name)}
    for group in re.findall(r"\(([A-Za-z][A-Za-z0-9\- ]{2,})\)", name):
        cleaned = group.strip().lower()
        if cleaned not in ("inci", "iso", "ci"):
            found.add(cleaned)
    return found


def xref_group(tag: str) -> str | None:
    if not tag.startswith("cross-ref-"):
        return None
    return re.sub(r"-\d+$", "", tag)


def load_reference(db: Session):
    try:
        limits = {row.inci: row for row in db.query(BpomLimit).all()}
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
        chunks = db.query(KnowledgeChunk).all()
        blocked = set()
        for row in db.query(ProhibitedSubstance).all():
            blocked |= blocklist_aliases(row.name)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return limits, catalog, chunks, blocked


def clean_names(*values) -> list[str]:
    return [v for v in values if isinstance(v, str) and v.strip()]


def normalize_inci(raw: str, catalog: dict, chunks: list) -> str | None:
    lowered = raw.strip().lower()
    for inci in catalog:
        if inci.lower() == lowered:
            return inci
    for inci, row in catalog.items():
        if lowered in [s.lower() for s in (row.synonyms or [])]:
            return inci
    for chunk in chunks:
        names = clean_names(
            chunk.inci_name, chunk.substance_name, *(chunk.synonyms or [])
        )
        if lowered in [n.lower() for n in names]:
            if chunk.inci_name in catalog:
                return chunk.inci_name
            return chunk.inci_name
    return None


def score_chunk(chunk: KnowledgeChunk, query_tokens: set[str]) -> int:
    haystack = " ".join(
        clean_names(
            chunk.title,
            chunk.substance_name,
            chunk.inci_name,
            chunk.category,
            chunk.raw_text,
        )
        + [" ".join(chunk.synonyms or []), " ".join(chunk.tags or [])]
    )
    return len(tokens(haystack) & query_tokens)


def retrieve(chunks: list, text: str, top_k: int = 3):
    scored = [(score_chunk(c, tokens(text)), c) for c in chunks]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    hits = [c for _, c in scored[:top_k]]
    groups = {
        xref_group(tag)
        for _, c in scored[:top_k]
        for tag in (c.tags or [])
        if xref_group(tag)
    }
    if groups:
        seen = {c.id for c in hits}
        for c in chunks:
            own = {xref_group(t) for t in (c.tags or []) if xref_group(t)}
            if c.id not in seen and groups & own:
                hits.append(c)
                seen.add(c.id)
    return hits


def citation_of(chunk: KnowledgeChunk | None) -> RagCitation | None:
    if chunk is None:
        return None
    return RagCitation(
        regulation=chunk.regulation,
        appendix=chunk.appendix,
        clause_number=chunk.clause_entry,
        excerpt=chunk.raw_text[:500],
    )


def audit_compliance(
    db: Session,
    body: ComplianceAuditRequest,
    gateway: GroqGateway | None = None,
) -> ComplianceAuditResponse:
    limits, catalog, chunks, blocked = load_reference(db)
    audits: list[IngredientAudit] = []
    violations = 0
    unverified: list[str] = []
    non_halal: list[str] = []
    tkdn_weighted = 0.0
    for position, item in enumerate(body.ingredients):
        canonical = normalize_inci(item.inci, catalog, chunks)
        known = catalog.get(canonical) if canonical else None
        limit = limits.get(canonical) if canonical else None
        chunk = None
        if canonical:
            hits = retrieve(chunks, f"{canonical} {item.name}", top_k=1)
            chunk = hits[0] if hits else None
        banned = blocklist_head(item.inci) in blocked or (
            canonical is not None
            and blocklist_head(canonical) in blocked
        )
        over_limit = (
            limit is not None and item.weight_pct > limit.max_pct
        )
        if banned or over_limit:
            violations += 1
        if known is None:
            unverified.append(item.inci)
            halal = "UNVERIFIED"
            tkdn = 0.0
        else:
            halal = "PASSED" if known.halal_status == "HALAL" else "FAILED"
            if halal == "FAILED":
                non_halal.append(item.inci)
            tkdn = known.tkdn_pct or 0.0
            tkdn_weighted += item.weight_pct * tkdn
        if banned:
            notes = "Bahan dilarang dalam kosmetika (Lampiran V)."
        elif over_limit:
            notes = (
                f"Konsentrasi {item.weight_pct}% melebihi batas "
                f"{limit.max_pct}%."
            )
        elif limit is not None:
            notes = (
                f"Konsentrasi {item.weight_pct}% dalam batas aman "
                f"{limit.max_pct}%."
            )
        else:
            notes = "Tidak ada batas BPOM spesifik yang tercatat."
        audits.append(
            IngredientAudit(
                ingredient_id=f"ing-{position}",
                name=item.name,
                inci=item.inci,
                weight_pct=item.weight_pct,
                phase=item.phase,
                role=item.role,
                status="FAILED" if banned or over_limit or halal == "FAILED" else "PASSED",
                bpom_limit_pct=limit.max_pct if limit else None,
                halal_status=halal,
                tkdn_pct=tkdn,
                rag_citation=citation_of(chunk),
                audit_notes=notes,
            )
        )
    score = round(max(0.0, 1.0 - 0.3 * violations - 0.1 * len(unverified)), 2)
    if non_halal:
        halal_status = "NON_HALAL_RISK"
    elif unverified:
        halal_status = "NEEDS_REVIEW"
    else:
        halal_status = "HALAL_CERTIFIED"
    overall = "COMPLIANT" if violations == 0 and not non_halal else "NON_COMPLIANT"
    tkdn_score = round(tkdn_weighted / 100.0, 1)
    verdict = (
        f"Formula {overall_status_word(overall)} terhadap Perka BPOM No. 25/2025 "
        f"dan standar Halal HAS 23000. Skor TKDN {tkdn_score}% "
        f"({'memenuhi' if tkdn_score >= TKDN_THRESHOLD_PCT else 'belum memenuhi'} "
        f"target nasional 40%)."
    )
    reasoning = build_reasoning(
        gateway,
        {
            "overall_status": overall,
            "violations": violations,
            "unverified": unverified,
            "tkdn_score": tkdn_score,
            "ingredients": [
                {"inci": a.inci, "pct": a.weight_pct, "status": a.status}
                for a in audits
            ],
        },
        chunks,
    )
    return ComplianceAuditResponse(
        audit_id=f"audit_rag_{int(time.time())}_{secrets.token_hex(3)}",
        formula_name=body.formula_name,
        overall_status=overall,
        compliance_score=score,
        halal_status=halal_status,
        total_tkdn_pct=tkdn_score,
        summary_verdict=verdict,
        ingredients_audit=audits,
        llm_reasoning=reasoning,
    )


def overall_status_word(overall: str) -> str:
    return "mematuhi" if overall == "COMPLIANT" else "belum mematuhi"


def build_reasoning(
    gateway: GroqGateway | None, findings: dict, chunks: list
) -> LlmReasoning:
    import json as jsonlib

    active = gateway or get_groq_gateway()
    grounded = jsonlib.dumps(findings, ensure_ascii=False)
    try:
        parsed = active.chat_json(
            [
                {
                    "role": "user",
                    "content": f"{REASONING_SYSTEM}\nTemuan audit: {grounded}",
                }
            ],
            model=settings.groq_model_fast,
            max_tokens=1024,
        )
        subs = [
            SubstitutionRecommendation(
                current_ingredient=s.get("current_ingredient", ""),
                recommended_local=s.get("recommended_local", ""),
                tkdn_impact=s.get("tkdn_impact"),
                rationale=s.get("rationale", ""),
            )
            for s in parsed.get("local_substitution_recommendations", [])
        ]
        return LlmReasoning(
            toxicology_evaluation=parsed.get("toxicology_evaluation", ""),
            mandatory_label_warnings=list(
                parsed.get("mandatory_label_warnings", [])
            ),
            local_substitution_recommendations=subs,
        )
    except Exception:
        warnings: list[str] = []
        for chunk in chunks:
            for warning in chunk.mandatory_warnings or []:
                if warning not in warnings:
                    warnings.append(warning)
        return LlmReasoning(
            toxicology_evaluation=(
                "Evaluasi toksikologi otomatis tidak tersedia, gunakan hasil "
                "audit deterministik di atas sebagai acuan."
            ),
            mandatory_label_warnings=warnings[:5],
            local_substitution_recommendations=[],
        )


def ask_rag(
    db: Session, body: AskRagRequest, gateway: GroqGateway | None = None
) -> AskRagResponse:
    import json as jsonlib

    _, _, chunks, _ = load_reference(db)
    query_text = body.query + " " + (body.category_context or "")
    hits = retrieve(chunks, query_text, top_k=3)
    excerpts = "\n".join(
        f"[{c.regulation} {c.appendix} {c.clause_entry}] {c.raw_text[:800]}"
        for c in hits
    )
    active = gateway or get_groq_gateway()
    try:
        parsed = active.chat_json(
            [
                {
                    "role": "user",
                    "content": f"{RAG_SYSTEM}\nKutipan:\n{excerpts}\nPertanyaan: {body.query}",
                }
            ],
            model=settings.groq_model_fast,
            max_tokens=1024,
        )
        answer = parsed.get("answer", "")
        confidence = float(parsed.get("confidence", 0.9))
    except Exception:
        answer = (
            "Mesin penalaran tidak tersedia. Gunakan kutipan regulasi di bawah "
            "sebagai acuan langsung."
        )
        confidence = 0.4
    return AskRagResponse(
        answer=answer,
        citations=[
            AskRagCitation(
                document=c.regulation,
                clause=f"{c.appendix} {c.clause_entry}",
                text=c.raw_text[:500],
            )
            for c in hits
        ],
        confidence_score=confidence,
    )
