from fastapi import APIRouter

from app.api.v1 import (
    auth,
    batch,
    compliance,
    copilot,
    db,
    formulas,
    health,
    knowledge,
    optimize,
    projects,
    simulate,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(db.router)
api_router.include_router(auth.router)
api_router.include_router(simulate.router)
api_router.include_router(formulas.router)
api_router.include_router(compliance.router)
api_router.include_router(projects.router)
api_router.include_router(projects.uploads_router)
api_router.include_router(copilot.router)
api_router.include_router(optimize.router)
api_router.include_router(batch.router)
api_router.include_router(knowledge.router)
