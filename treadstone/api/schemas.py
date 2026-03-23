"""Pydantic response schemas for Treadstone API.

Centralised here so every router can share them and FastAPI can
generate rich OpenAPI specs with examples.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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

# ── Sandbox ──────────────────────────────────────────────────────────────────


class CreateSandboxRequest(BaseModel):
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    name: str | None = Field(default=None, examples=["my-sandbox"], description=SANDBOX_NAME_DESCRIPTION)
    labels: dict = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(
        default=15, examples=[15], description="Minutes of inactivity before the sandbox is automatically stopped."
    )
    auto_delete_interval: int = Field(
        default=-1,
        examples=[-1],
        description="Minutes after stop before the sandbox is automatically deleted. -1 disables auto-delete.",
    )
    persist: bool = Field(default=False, examples=[False])
    storage_size: str = Field(
        default="10Gi",
        examples=["10Gi"],
        description="Persistent volume size (only effective when persist=true).",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not SANDBOX_NAME_PATTERN.fullmatch(value):
            raise ValueError(SANDBOX_NAME_RULE)
        return value


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
    expires_in: int = Field(default=3600, examples=[3600], description="Token lifetime in seconds.")


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
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["MySecretPass123!"])


class LoginResponse(BaseModel):
    detail: str = Field(..., examples=["Login successful"])


class RegisterRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["MySecretPass123!"])
    invitation_token: str | None = Field(default=None, examples=[None])


class UserResponse(BaseModel):
    id: str = Field(..., examples=["usr-abc123def456"])
    email: str = Field(..., examples=["user@example.com"])
    role: str = Field(..., examples=["admin"])


class RegisterResponse(UserResponse):
    pass


class UserDetailResponse(UserResponse):
    username: str | None = Field(default=None, examples=["alice"])
    is_active: bool = Field(..., examples=[True])


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(..., examples=[1])


class InviteRequest(BaseModel):
    email: str = Field(..., examples=["invitee@example.com"])
    role: str = Field(default="ro", examples=["ro"])


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
    expires_in: int | None = Field(default=None, examples=[86400], description="Key lifetime in seconds.")


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
