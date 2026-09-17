from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class DbHealthResponse(BaseModel):
    status: str = "ok"
    db: str = "connected"
