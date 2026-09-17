from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.compliance import ComplianceRequest, ComplianceResponse
from app.services.compliance_service import audit_compliance

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/audit", response_model=ComplianceResponse)
def audit(body: ComplianceRequest, db: SessionDep) -> ComplianceResponse:
    return audit_compliance(db, body)
