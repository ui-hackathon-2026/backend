"""Deterministic regulatory audit, no ML and no LLM involved.

BPOM limits come from the bpom_limits table, halal and TKDN data from
the ingredients catalog. Unknown ingredients are reported, never guessed.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.compliance import BpomLimit
from app.models.ingredient import Ingredient
from app.schemas.compliance import (
    BpomAudit,
    BpomViolation,
    ComplianceRequest,
    ComplianceResponse,
    HalalAudit,
    TkdnAudit,
)

TKDN_THRESHOLD_PCT = 40.0


def audit_compliance(db: Session, request: ComplianceRequest) -> ComplianceResponse:
    try:
        limits = {row.inci: row for row in db.query(BpomLimit).all()}
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    violations: list[BpomViolation] = []
    non_halal: list[str] = []
    unverified: list[str] = []
    tkdn_weighted = 0.0
    local_components: list[str] = []
    for item in request.formula_ingredients:
        limit = limits.get(item.inci)
        if limit is not None and item.percentage > limit.max_pct:
            violations.append(
                BpomViolation(
                    inci=item.inci,
                    percentage=item.percentage,
                    max_allowed_pct=limit.max_pct,
                )
            )
        known = catalog.get(item.inci)
        if known is None:
            unverified.append(item.inci)
        else:
            if known.halal_status != "HALAL":
                non_halal.append(item.inci)
            tkdn_weighted += item.percentage * (known.tkdn_pct or 0.0)
            if (known.tkdn_pct or 0.0) > 0:
                local_components.append(known.name)
    bpom_ok = len(violations) == 0
    halal_ok = len(non_halal) == 0
    porcine_risk = "ZERO" if halal_ok else "FLAGGED"
    if unverified and halal_ok:
        porcine_risk = "UNKNOWN"
    score = round(tkdn_weighted / 100.0, 1)
    overall = "COMPLIANT" if bpom_ok and halal_ok else "NON_COMPLIANT"
    return ComplianceResponse(
        overall_status=overall,
        bpom_audit=BpomAudit(
            status="PASSED" if bpom_ok else "FAILED", violations=violations
        ),
        halal_audit=HalalAudit(
            status="PASSED" if halal_ok else "FAILED",
            porcine_risk=porcine_risk,
            non_halal=non_halal,
            unverified=unverified,
        ),
        tkdn_audit=TkdnAudit(
            score_pct=score,
            meets_threshold=score >= TKDN_THRESHOLD_PCT,
            local_components=sorted(set(local_components)),
        ),
    )
