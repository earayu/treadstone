"""Pydantic response schemas for Treadstone API.

Centralised here so every router can share them and FastAPI can
generate rich OpenAPI specs with examples.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from treadstone.models.user import Role

SANDBOX_NAME_MAX_LENGTH = 55
SANDBOX_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?$")
SANDBOX_NAME_RULE = (
    "Sandbox name must be 1-55 characters of lowercase letters, numbers, or hyphens, "
    "and must start and end with a letter or number."
)
SANDBOX_NAME_DESCRIPTION = (
    "Optional custom sandbox name. "
    f"{SANDBOX_NAME_RULE} "
    "This keeps browser URLs like `sandbox-{name}.treadstone-ai.dev` within DNS label limits."
)
STORAGE_SIZE_PATTERN = re.compile(r"^[1-9]\d*(?:Ei|Pi|Ti|Gi|Mi|Ki)$")
STORAGE_SIZE_RULE = "storage_size must be a valid Kubernetes quantity like 5Gi, 500Mi, or 1Ti."

# ── Sandbox ──────────────────────────────────────────────────────────────────


class CreateSandboxRequest(BaseModel):
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    name: str | None = Field(default=None, examples=["my-sandbox"], description=SANDBOX_NAME_DESCRIPTION)
    labels: dict[str, str] = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(
        default=15, examples=[15], description="Minutes of inactivity before the sandbox is automatically stopped."
    )
    auto_delete_interval: int = Field(
        default=-1,
        examples=[-1],
        description="Minutes after stop before the sandbox is automatically deleted. -1 disables auto-delete.",
    )
    persist: bool = Field(default=False, examples=[False])
    storage_size: str | None = Field(default=None, examples=["10Gi"], description="Persistent volume size.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not SANDBOX_NAME_PATTERN.fullmatch(value):
            raise ValueError(SANDBOX_NAME_RULE)
        return value

    @field_validator("auto_stop_interval")
    @classmethod
    def validate_auto_stop_interval(cls, value: int) -> int:
        if value < 1:
            raise ValueError("auto_stop_interval must be at least 1 minute.")
        return value

    @field_validator("auto_delete_interval")
    @classmethod
    def validate_auto_delete_interval(cls, value: int) -> int:
        if value != -1 and value < 1:
            raise ValueError("auto_delete_interval must be -1 or at least 1 minute.")
        return value

    @field_validator("storage_size")
    @classmethod
    def validate_storage_size(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not STORAGE_SIZE_PATTERN.fullmatch(value):
            raise ValueError(STORAGE_SIZE_RULE)
        return value

    @model_validator(mode="after")
    def validate_storage_config(self) -> CreateSandboxRequest:
        if self.persist:
            if self.storage_size is None:
                self.storage_size = "10Gi"
            return self

        if self.storage_size is not None:
            raise ValueError("storage_size is only allowed when persist=true.")
        return self


class SandboxUrls(BaseModel):
    proxy: str = Field(..., examples=["http://localhost:8000/v1/sandboxes/sb-abc123def456/proxy"])
    web: str | None = Field(default=None, examples=["http://my-sandbox.sandbox.localhost:8000"])


class SandboxResponse(BaseModel):
    id: str = Field(..., examples=["sb-abc123def456"])
    name: str = Field(..., examples=["my-sandbox"])
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    status: str = Field(..., examples=["creating"])
    labels: dict = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(
        ..., examples=[15], description="Minutes of inactivity before the sandbox is automatically stopped."
    )
    auto_delete_interval: int = Field(
        ..., examples=[-1], description="Minutes after stop before auto-delete. -1 means disabled."
    )
    urls: SandboxUrls
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])

    model_config = {"from_attributes": True}


class SandboxDetailResponse(SandboxResponse):
    image: str | None = Field(default=None, examples=["ghcr.io/agent-infra/sandbox:latest"])
    status_message: str | None = Field(default=None, examples=[None])
    persist: bool = Field(default=False, examples=[False])
    storage_size: str | None = Field(
        default=None, examples=["10Gi"], description="Persistent volume size (only present when persist=true)."
    )
    started_at: datetime | None = Field(default=None, examples=["2026-03-21T12:01:00+00:00"])
    stopped_at: datetime | None = Field(default=None, examples=[None])


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int = Field(..., examples=[1])


class CreateSandboxTokenRequest(BaseModel):
    expires_in: int = Field(default=3600, ge=1, le=86400, examples=[3600], description="Token lifetime in seconds.")


class SandboxTokenResponse(BaseModel):
    token: str = Field(..., examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    sandbox_id: str = Field(..., examples=["sb-abc123def456"])
    expires_at: datetime = Field(..., examples=["2026-03-21T13:00:00+00:00"])


# ── Sandbox Templates ────────────────────────────────────────────────────────


class ResourceSpec(BaseModel):
    cpu: str = Field(..., examples=["250m"])
    memory: str = Field(..., examples=["512Mi"])


class SandboxTemplateResponse(BaseModel):
    name: str = Field(..., examples=["aio-sandbox-tiny"])
    display_name: str = Field(..., examples=["AIO Sandbox Tiny"])
    description: str = Field(..., examples=["Lightweight sandbox for code execution and scripting"])
    image: str = Field(..., examples=["ghcr.io/agent-infra/sandbox:latest"])
    resource_spec: ResourceSpec


class SandboxTemplateListResponse(BaseModel):
    items: list[SandboxTemplateResponse]


# ── Auth ─────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["MySecretPass123!"])


class LoginResponse(BaseModel):
    detail: str = Field(..., examples=["Login successful"])


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["MySecretPass123!"])
    invitation_token: str | None = Field(default=None, examples=[None])


class UserResponse(BaseModel):
    id: str = Field(..., examples=["usr-abc123def456"])
    email: EmailStr = Field(..., examples=["user@example.com"])
    role: Role = Field(..., examples=["admin"])


class RegisterResponse(UserResponse):
    pass


class UserDetailResponse(UserResponse):
    username: str | None = Field(default=None, examples=["alice"])
    is_active: bool = Field(..., examples=[True])


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(..., examples=[1])


class InviteRequest(BaseModel):
    email: EmailStr = Field(..., examples=["invitee@example.com"])
    role: Role = Field(default=Role.RO, examples=["ro"])


class InviteResponse(BaseModel):
    token: str = Field(..., examples=["dGhpcyBpcyBhIHRva2VuLi4u"])
    email: str = Field(..., examples=["invitee@example.com"])
    expires_at: datetime = Field(..., examples=["2026-03-28T12:00:00+00:00"])


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., examples=["OldPass123!"])
    new_password: str = Field(..., examples=["NewPass456!"])


class MessageResponse(BaseModel):
    detail: str = Field(..., examples=["Password changed"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(default="default", examples=["my-api-key"])
    expires_in: int | None = Field(
        default=None,
        ge=1,
        le=31536000,
        examples=[86400],
        description="Key lifetime in seconds.",
    )


class ApiKeyResponse(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    key: str = Field(..., examples=["sk-0123456789abcdef0123456789abcdef01234567"])
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    expires_at: datetime | None = Field(default=None, examples=[None])


class ApiKeySummary(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    key_prefix: str = Field(..., examples=["sk-0123...cdef"])
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    expires_at: datetime | None = Field(default=None, examples=[None])


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeySummary]


# ── Config ───────────────────────────────────────────────────────────────────


class Auth0Config(BaseModel):
    domain: str = Field(..., examples=["myapp.auth0.com"])
    client_id: str = Field(..., examples=["abc123"])


class AuthingConfig(BaseModel):
    domain: str = Field(..., examples=["myapp.authing.cn"])
    app_id: str = Field(..., examples=["abc123"])


class LogtoConfig(BaseModel):
    domain: str = Field(..., examples=["myapp.logto.io"])
    app_id: str = Field(..., examples=["abc123"])


class AuthConfig(BaseModel):
    type: str = Field(..., examples=["builtin"])
    login_methods: list[str] = Field(..., examples=[["email", "google"]])
    auth0: Auth0Config | None = None
    authing: AuthingConfig | None = None
    logto: LogtoConfig | None = None


class ConfigResponse(BaseModel):
    auth: AuthConfig


# ── System ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
