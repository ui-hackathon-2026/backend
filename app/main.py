import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    DatabaseUnavailableError,
    FormulaWeightError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=settings.log_level.upper())
    logger.info("starting %s v%s", settings.app_name, settings.app_version)
    yield
    logger.info("shutting down, disposing engine")
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DatabaseUnavailableError)
    async def db_unavailable_handler(request: Request, exc: DatabaseUnavailableError):
        logger.error("database unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "database unavailable"})

    @app.exception_handler(FormulaWeightError)
    async def formula_weight_handler(request: Request, exc: FormulaWeightError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
        logger.error("llm unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "ai engine unavailable"})

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["root"])
    def root():
        return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}

    return app


app = create_app()
