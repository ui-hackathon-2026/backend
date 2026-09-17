"""Project workspace and marketing-brief ingestion.

Projects are loose containers, creation order is never enforced.
PDF text extraction is deterministic, semantic parsing arrives later.
"""

import secrets
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.project import Brief, Project
from app.schemas.project import (
    BriefResponse,
    ProjectCreate,
    ProjectResponse,
)

MAX_BRIEF_BYTES = 10 * 1024 * 1024


class BriefRejectedError(ValueError):
    pass


def new_project_id() -> str:
    return f"proj_{secrets.token_hex(6)}"


def new_brief_id() -> str:
    return f"brief_{secrets.token_hex(6)}"


def to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.id,
        name=project.name,
        mode=project.mode,
        brief_text=project.brief_text,
        brief_id=project.brief_id,
        ref_formula_id=project.ref_formula_id,
        instruction=project.instruction,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def create_project(db: Session, body: ProjectCreate) -> ProjectResponse:
    try:
        project = Project(
            id=new_project_id(),
            name=body.name,
            mode=body.mode.value,
            brief_text=body.brief_text,
            brief_id=body.brief_id,
            ref_formula_id=body.ref_formula_id,
            instruction=body.instruction,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return to_response(project)


def list_projects(db: Session, limit: int = 50) -> list[ProjectResponse]:
    try:
        rows = (
            db.query(Project).order_by(Project.updated_at.desc()).limit(limit).all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [to_response(r) for r in rows]


def get_project(db: Session, project_id: str) -> ProjectResponse | None:
    try:
        project = db.get(Project, project_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if project is None:
        return None
    return to_response(project)


def extract_text(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:
        raise BriefRejectedError("unreadable pdf") from exc


def ingest_brief(db: Session, filename: str, data: bytes) -> BriefResponse:
    if not filename.lower().endswith(".pdf"):
        raise BriefRejectedError("only pdf briefs accepted")
    if len(data) > MAX_BRIEF_BYTES:
        raise BriefRejectedError("brief exceeds 10 MB")
    text = extract_text(data)
    if not text:
        raise BriefRejectedError("no extractable text found")
    try:
        brief = Brief(
            id=new_brief_id(), filename=filename, content_text=text
        )
        db.add(brief)
        db.commit()
        db.refresh(brief)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return BriefResponse(
        brief_id=brief.id,
        filename=brief.filename,
        char_count=len(text),
        preview=text[:500],
        created_at=brief.created_at,
    )
