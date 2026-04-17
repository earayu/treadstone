from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DependencyCommandResult(BaseModel):
    command: List[str] = Field(..., description='Executed dependency command')
    success: bool = Field(..., description='Whether the command succeeded')
    stdout: str | None = Field(None, description='Standard output from command')
    stderr: str | None = Field(None, description='Standard error from command')


class SkillMetadata(BaseModel):
    name: str = Field(..., description='Skill name')
    path: str = Field(..., description='Absolute path to the skill directory')
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description='Metadata parsed from SKILL.md front matter',
    )
    dependency_commands: List[DependencyCommandResult] = Field(
        default_factory=list,
        description='Dependency commands for the skill',
    )


class SkillRegistrationResult(BaseModel):
    count: int = Field(..., description='Number of registered skills')
    registered: List[SkillMetadata] = Field(
        default_factory=list, description='Registered skills and metadata'
    )


class SkillMetadataCollection(BaseModel):
    skills: List[SkillMetadata] = Field(
        default_factory=list, description='Collection of skill metadata entries'
    )


class SkillContentResult(BaseModel):
    name: str = Field(..., description='Skill name')
    path: str = Field(..., description='Absolute path to the skill directory')
    content: str = Field(..., description='Skill content excluding front matter')
