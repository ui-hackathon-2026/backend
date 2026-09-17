from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.compliance import (
    AskRagRequest,
    AskRagResponse,
    ComplianceAuditRequest,
    ComplianceAuditResponse,
)
from app.services.compliance_service import ask_rag, audit_compliance

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/audit", response_model=ComplianceAuditResponse)
def audit(body: ComplianceAuditRequest, db: SessionDep) -> ComplianceAuditResponse:
    return audit_compliance(db, body)


@router.post("/ask-rag", response_model=AskRagResponse)
def ask(body: AskRagRequest, db: SessionDep) -> AskRagResponse:
    return ask_rag(db, body)
