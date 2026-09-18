from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1 import (
    auth,
    batch,
    compliance,
    copilot,
    db,
    formulas,
    health,
    ingredients,
    knowledge,
    nsga,
    optimize,
    orchestrator,
    projects,
    simulate,
    workbench,
)

require_auth = [Depends(get_current_user)]

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(db.router)
api_router.include_router(auth.router)
api_router.include_router(ingredients.router, dependencies=require_auth)
api_router.include_router(simulate.router)
api_router.include_router(formulas.router)
api_router.include_router(compliance.router)
api_router.include_router(projects.router, dependencies=require_auth)
api_router.include_router(projects.uploads_router, dependencies=require_auth)
api_router.include_router(copilot.router, dependencies=require_auth)
api_router.include_router(optimize.router)
api_router.include_router(batch.router, dependencies=require_auth)
api_router.include_router(knowledge.router, dependencies=require_auth)
api_router.include_router(nsga.router)
api_router.include_router(orchestrator.router, dependencies=require_auth)
api_router.include_router(workbench.router, dependencies=require_auth)
