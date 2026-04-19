from __future__ import annotations

from pydantic import BaseModel, Field


class SkillRegisterRequest(BaseModel):
    path: str = Field(..., description='Path to a skill directory or container')
