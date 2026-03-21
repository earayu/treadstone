"""Pydantic response schemas for Treadstone API.

Centralised here so every router can share them and FastAPI can
generate rich OpenAPI specs with examples.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Sandbox ──────────────────────────────────────────────────────────────────


class CreateSandboxRequest(BaseModel):
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    name: str | None = Field(default=None, examples=["my-sandbox"])
    runtime_type: str = Field(default="aio", examples=["aio"])
    labels: dict = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(default=15, examples=[15])
    auto_delete_interval: int = Field(default=-1, examples=[-1])
    persist: bool = Field(default=False, examples=[False])
    storage_size: str = Field(default="10Gi", examples=["10Gi"])


class SandboxResponse(BaseModel):
    id: str = Field(..., examples=["sb-abc123def456"])
    name: str = Field(..., examples=["my-sandbox"])
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    runtime_type: str = Field(..., examples=["aio"])
    status: str = Field(..., examples=["creating"])
    labels: dict = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(..., examples=[15])
    auto_delete_interval: int = Field(..., examples=[-1])
    created_at: str = Field(..., examples=["2026-03-21 12:00:00+00:00"])

    model_config = {"from_attributes": True}


class SandboxDetailResponse(SandboxResponse):
    image: str | None = Field(default=None, examples=["ghcr.io/agent-infra/sandbox:latest"])
    status_message: str | None = Field(default=None, examples=[None])
    endpoints: dict = Field(default_factory=dict, examples=[{"http": "http://my-sandbox.treadstone.svc:8080"}])
    proxy_url: str = Field(..., examples=["/v1/sandboxes/sb-abc123def456/proxy"])
    persist: bool = Field(default=False, examples=[False])
    storage_size: str | None = Field(default=None, examples=["10Gi"])
    started_at: str | None = Field(default=None, examples=["2026-03-21 12:01:00+00:00"])
    stopped_at: str | None = Field(default=None, examples=[None])


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int = Field(..., examples=[1])


class CreateSandboxTokenRequest(BaseModel):
    expires_in: int = Field(default=3600, examples=[3600])


class SandboxTokenResponse(BaseModel):
    token: str = Field(..., examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    sandbox_id: str = Field(..., examples=["sb-abc123def456"])
    expires_at: str = Field(..., examples=["2026-03-21 13:00:00+00:00"])


# ── Sandbox Templates ────────────────────────────────────────────────────────


class ResourceSpec(BaseModel):
    cpu: str = Field(..., examples=["250m"])
    memory: str = Field(..., examples=["512Mi"])


class SandboxTemplateResponse(BaseModel):
    name: str = Field(..., examples=["aio-sandbox-tiny"])
    display_name: str = Field(..., examples=["AIO Sandbox Tiny"])
    description: str = Field(..., examples=["Lightweight sandbox for code execution and scripting"])
    runtime_type: str = Field(..., examples=["aio"])
    image: str = Field(..., examples=["ghcr.io/agent-infra/sandbox:latest"])
    resource_spec: ResourceSpec


class SandboxTemplateListResponse(BaseModel):
    items: list[SandboxTemplateResponse]


# ── Auth ─────────────────────────────────────────────────────────────────────


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


class InviteRequest(BaseModel):
    email: str = Field(..., examples=["invitee@example.com"])
    role: str = Field(default="ro", examples=["ro"])


class InviteResponse(BaseModel):
    token: str = Field(..., examples=["dGhpcyBpcyBhIHRva2VuLi4u"])
    email: str = Field(..., examples=["invitee@example.com"])
    expires_at: str = Field(..., examples=["2026-03-28 12:00:00+00:00"])


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., examples=["OldPass123!"])
    new_password: str = Field(..., examples=["NewPass456!"])


class MessageResponse(BaseModel):
    detail: str = Field(..., examples=["Password changed"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(default="default", examples=["my-api-key"])
    expires_in: int | None = Field(default=None, examples=[86400])


class ApiKeyResponse(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    key: str = Field(..., examples=["sk-0123456789abcdef0123456789abcdef01234567"])
    created_at: str = Field(..., examples=["2026-03-21 12:00:00+00:00"])
    expires_at: str | None = Field(default=None, examples=[None])


class ApiKeySummary(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    key_prefix: str = Field(..., examples=["sk-0123...cdef"])
    created_at: str = Field(..., examples=["2026-03-21 12:00:00+00:00"])
    expires_at: str | None = Field(default=None, examples=[None])


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


class MeResponse(BaseModel):
    id: str = Field(..., examples=["usr-abc123def456"])
    email: str = Field(..., examples=["user@example.com"])
    role: str = Field(..., examples=["admin"])
