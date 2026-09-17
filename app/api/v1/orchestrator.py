from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import SessionDep
from app.schemas.orchestrator import (
    ChassisModel,
    FormulationBlueprint,
    HeroIngredient,
    ParseBriefResponse,
    ProjectBriefInput,
)
from app.services.orchestration_service import (
    list_chassis,
    list_heroes,
    parse_brief_pdf,
    synthesize,
)
from app.services.project_service import BriefRejectedError

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post("/synthesize", response_model=FormulationBlueprint, status_code=201)
def synthesize_blueprint(
    body: ProjectBriefInput, db: SessionDep
) -> FormulationBlueprint:
    return synthesize(db, body)


@router.post("/parse-brief-pdf", response_model=ParseBriefResponse)
async def parse_brief(
    db: SessionDep, file: UploadFile = File(...)
) -> ParseBriefResponse:
    data = await file.read()
    try:
        return parse_brief_pdf(file.filename or "brief.pdf", data)
    except BriefRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.get("/chassis", response_model=list[ChassisModel])
def chassis(db: SessionDep) -> list[ChassisModel]:
    return list_chassis(db)


@router.get("/hero-ingredients", response_model=list[HeroIngredient])
def heroes(db: SessionDep) -> list[HeroIngredient]:
    return list_heroes(db)
