from fastapi import APIRouter

from app.api.v1 import auth, db, health, simulate

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(db.router)
api_router.include_router(auth.router)
api_router.include_router(simulate.router)
