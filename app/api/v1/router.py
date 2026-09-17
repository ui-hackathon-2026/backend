from fastapi import APIRouter

from app.api.v1 import auth, compliance, copilot, db, formulas, health, projects, simulate

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
