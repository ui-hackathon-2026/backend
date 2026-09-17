from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ProjectMode(str, Enum):
    NEW = "new"
    ENHANCE = "enhance"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mode: ProjectMode = ProjectMode.NEW
    brief_text: str | None = Field(default=None, max_length=8000)
    brief_id: str | None = Field(default=None, max_length=64)
    ref_formula_id: str | None = Field(default=None, max_length=64)
    instruction: str | None = Field(default=None, max_length=8000)

    @model_validator(mode="after")
    def enhance_needs_reference(self):
        if self.mode == ProjectMode.ENHANCE and not self.ref_formula_id:
            raise ValueError("enhance mode requires ref_formula_id")
        return self


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    mode: str
    brief_text: str | None = None
    brief_id: str | None = None
    ref_formula_id: str | None = None
    instruction: str | None = None
    created_at: datetime
    updated_at: datetime


class BriefResponse(BaseModel):
    brief_id: str
    filename: str
    char_count: int
    preview: str
    created_at: datetime
