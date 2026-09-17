from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import SessionDep
from app.schemas.project import (
    BriefResponse,
    ProjectCreate,
    ProjectResponse,
)
from app.services.project_service import (
    BriefRejectedError,
    create_project,
    get_project,
    ingest_brief,
    list_projects,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create(body: ProjectCreate, db: SessionDep) -> ProjectResponse:
    return create_project(db, body)


@router.get("", response_model=list[ProjectResponse])
def list_all(db: SessionDep, limit: int = 50) -> list[ProjectResponse]:
    return list_projects(db, limit=min(limit, 200))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_one(project_id: str, db: SessionDep) -> ProjectResponse:
    result = get_project(db, project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return result


uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])


@uploads_router.post("/brief", response_model=BriefResponse, status_code=201)
async def upload_brief(
    db: SessionDep, file: UploadFile = File(...)
) -> BriefResponse:
    data = await file.read()
    try:
        return ingest_brief(db, file.filename or "brief.pdf", data)
    except BriefRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
