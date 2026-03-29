"""Pydantic response schemas for Treadstone API.

Centralised here so every router can share them and FastAPI can
generate rich OpenAPI specs with examples.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from treadstone.config import settings
from treadstone.models.api_key import ApiKeyDataPlaneMode
from treadstone.models.user import Role

SANDBOX_NAME_MAX_LENGTH = 55
SANDBOX_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?$")
SANDBOX_NAME_RULE = (
    "Sandbox name must be 1-55 characters of lowercase letters, numbers, or hyphens, "
    "and must start and end with a letter or number."
)
SANDBOX_NAME_DESCRIPTION = (
    f"Optional custom sandbox name. {SANDBOX_NAME_RULE} Sandbox names only need to be unique for the current user."
)
STORAGE_SIZE_PATTERN = re.compile(r"^\d+(?:Gi|Ti)$")
STORAGE_SIZE_RULE = "storage_size must match format '<number>Gi' or '<number>Ti' (e.g. 5Gi, 10Gi, 20Gi, 1Ti)."

# ── Sandbox ──────────────────────────────────────────────────────────────────


class CreateSandboxRequest(BaseModel):
    template: str = Field(..., examples=["aio-sandbox-tiny"])
    name: str | None = Field(default=None, examples=["my-sandbox"], description=SANDBOX_NAME_DESCRIPTION)
    labels: dict[str, str] = Field(default_factory=dict, examples=[{"env": "dev"}])
    auto_stop_interval: int = Field(
        default=60, examples=[60], description="Minutes of inactivity before the sandbox is automatically stopped."
    )
    auto_delete_interval: int = Field(
        default=-1,
        examples=[-1],
        description="Minutes after stop before the sandbox is automatically deleted. -1 disables auto-delete.",
    )
    persist: bool = Field(default=False, examples=[False])
    storage_size: str | None = Field(
        default=None,
        examples=["5Gi"],
        description="Persistent volume size (e.g. 5Gi, 10Gi, 20Gi). "
        "Allowed values depend on the sandbox template's annotation.",
    )

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
                self.storage_size = settings.sandbox_default_storage_size
            return self

        if self.storage_size is not None:
            raise ValueError("storage_size is only allowed when persist=true.")
        return self


class SandboxUrls(BaseModel):
    proxy: str = Field(..., examples=["http://localhost/v1/sandboxes/sb-abc123def456/proxy"])
    web: str | None = Field(
        default=None,
        examples=["http://sandbox-sbabc123def456.sandbox.localhost/_treadstone/open?token=swlabc123"],
        description=(
            "Recommended browser entry URL. When a sandbox web link is enabled, this is the shareable hand-off URL."
        ),
    )


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
    persist: bool = Field(default=False, examples=[False], description="Whether persistent storage is attached.")
    storage_size: str | None = Field(
        default=None,
        examples=["5Gi"],
        description="Persistent volume size when persist=true.",
    )
    urls: SandboxUrls
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])

    model_config = {"from_attributes": True}


class SandboxDetailResponse(SandboxResponse):
    image: str | None = Field(default=None, examples=["ghcr.io/agent-infra/sandbox:latest"])
    status_message: str | None = Field(default=None, examples=[None])
    started_at: datetime | None = Field(default=None, examples=["2026-03-21T12:01:00+00:00"])
    stopped_at: datetime | None = Field(default=None, examples=[None])


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int = Field(..., examples=[1])


class SandboxWebLinkResponse(BaseModel):
    web_url: str = Field(..., examples=["https://sandbox-sbabc123def456.treadstone-ai.dev/"])
    open_link: str = Field(
        ...,
        examples=["https://sandbox-sbabc123def456.treadstone-ai.dev/_treadstone/open?token=swlabc123"],
    )
    expires_at: datetime | None = Field(default=None, examples=["2026-03-31T12:00:00+00:00"])


class SandboxWebLinkStatusResponse(BaseModel):
    web_url: str = Field(..., examples=["https://sandbox-sbabc123def456.treadstone-ai.dev/"])
    enabled: bool = Field(..., examples=[True])
    expires_at: datetime | None = Field(default=None, examples=["2026-03-31T12:00:00+00:00"])
    last_used_at: datetime | None = Field(default=None, examples=[None])


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
    allowed_storage_sizes: list[str] = Field(default_factory=list, examples=[["5Gi", "10Gi", "20Gi"]])


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


class UserResponse(BaseModel):
    id: str = Field(..., examples=["usr-abc123def456"])
    email: EmailStr = Field(..., examples=["user@example.com"])
    role: Role = Field(..., examples=["admin"])
    is_active: bool = Field(..., examples=[True])


class RegisterResponse(UserResponse):
    is_verified: bool = Field(..., examples=[True])
    verification_email_sent: bool = Field(..., examples=[True])


class UserDetailResponse(UserResponse):
    username: str | None = Field(default=None, examples=["alice"])
    is_verified: bool = Field(..., examples=[True])
    has_local_password: bool = Field(..., examples=[True])


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(..., examples=[1])


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(..., examples=[False], description="Set to false to disable the user account.")


class VerificationConfirmRequest(BaseModel):
    token: str = Field(..., examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., examples=["OldPass123!"])
    new_password: str = Field(..., examples=["NewPass456!"])


class SetPasswordRequest(BaseModel):
    new_password: str = Field(..., examples=["NewPass456!"])


class MessageResponse(BaseModel):
    detail: str = Field(..., examples=["Password changed"])


class ApiKeyDataPlaneScope(BaseModel):
    mode: ApiKeyDataPlaneMode = Field(default=ApiKeyDataPlaneMode.ALL, examples=["all"])
    sandbox_ids: list[str] = Field(default_factory=list, examples=[["sb-abc123def456", "sb-def456ghi789"]])

    @model_validator(mode="after")
    def validate_mode_and_sandbox_ids(self) -> ApiKeyDataPlaneScope:
        self.sandbox_ids = list(dict.fromkeys(self.sandbox_ids))
        if self.mode == ApiKeyDataPlaneMode.SELECTED:
            if not self.sandbox_ids:
                raise ValueError("sandbox_ids must be provided when data_plane.mode=selected.")
            return self

        if self.sandbox_ids:
            raise ValueError("sandbox_ids is only allowed when data_plane.mode=selected.")
        return self


class ApiKeyScope(BaseModel):
    control_plane: bool = Field(default=True, examples=[True])
    data_plane: ApiKeyDataPlaneScope = Field(default_factory=ApiKeyDataPlaneScope)


class ApiKeyDataPlaneScopeResponse(BaseModel):
    mode: ApiKeyDataPlaneMode = Field(..., examples=["all"])
    sandbox_ids: list[str] = Field(default_factory=list, examples=[["sb-abc123def456", "sb-def456ghi789"]])


class ApiKeyScopeResponse(BaseModel):
    control_plane: bool = Field(..., examples=[True])
    data_plane: ApiKeyDataPlaneScopeResponse


class CreateApiKeyRequest(BaseModel):
    name: str = Field(default="default", examples=["my-api-key"])
    expires_in: int | None = Field(
        default=None,
        ge=1,
        le=31536000,
        examples=[86400],
        description="Key lifetime in seconds.",
    )
    scope: ApiKeyScope | None = Field(default=None)


class UpdateApiKeyRequest(BaseModel):
    name: str | None = Field(default=None, examples=["renamed-key"])
    is_enabled: bool | None = Field(default=None, examples=[True], description="Enable or disable the API key.")
    expires_in: int | None = Field(
        default=None,
        ge=1,
        le=31536000,
        examples=[86400],
        description="Reset the key lifetime from now in seconds.",
    )
    clear_expiration: bool = Field(default=False, examples=[False])
    scope: ApiKeyScope | None = Field(default=None)

    @model_validator(mode="after")
    def validate_patch_request(self) -> UpdateApiKeyRequest:
        if self.expires_in is not None and self.clear_expiration:
            raise ValueError("expires_in and clear_expiration cannot be used together.")
        if (
            self.name is None
            and self.is_enabled is None
            and self.expires_in is None
            and not self.clear_expiration
            and self.scope is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class ApiKeyResponse(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    is_enabled: bool = Field(..., examples=[True])
    key: str = Field(..., examples=["sk-0123456789abcdef0123456789abcdef01234567"])
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    updated_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    expires_at: datetime | None = Field(default=None, examples=[None])
    scope: ApiKeyScopeResponse


class ApiKeySummary(BaseModel):
    id: str = Field(..., examples=["key-abc123def456"])
    name: str = Field(..., examples=["my-api-key"])
    is_enabled: bool = Field(..., examples=[True])
    key_prefix: str = Field(..., examples=["sk-0123...cdef"])
    created_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    updated_at: datetime = Field(..., examples=["2026-03-21T12:00:00+00:00"])
    expires_at: datetime | None = Field(default=None, examples=[None])
    scope: ApiKeyScopeResponse


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


class AuditEventResponse(BaseModel):
    id: str = Field(..., examples=["audabc123def456"])
    created_at: datetime = Field(..., examples=["2026-03-26T12:00:00+00:00"])
    actor_type: str = Field(..., examples=["user"])
    actor_user_id: str | None = Field(default=None, examples=["userabc123def456"])
    actor_api_key_id: str | None = Field(default=None, examples=["keyabc123def456"])
    credential_type: str | None = Field(default=None, examples=["cookie"])
    action: str = Field(..., examples=["sandbox.create"])
    target_type: str = Field(..., examples=["sandbox"])
    target_id: str | None = Field(default=None, examples=["sbabc123def456"])
    result: str = Field(..., examples=["success"])
    error_code: str | None = Field(default=None, examples=[None])
    request_id: str | None = Field(default=None, examples=["req_0123456789abcdef"])
    ip: str | None = Field(default=None, examples=["203.0.113.10"])
    user_agent: str | None = Field(default=None, examples=["python-httpx/0.28.1"])
    metadata: dict[str, Any] = Field(default_factory=dict, examples=[{"template": "aio-sandbox-tiny"}])


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int = Field(..., examples=[1])


# ── Metering — Usage ─────────────────────────────────────────────────────────


class BillingPeriod(BaseModel):
    start: str = Field(..., examples=["2026-03-01T00:00:00+00:00"])
    end: str = Field(..., examples=["2026-04-01T00:00:00+00:00"])


class ComputeUsage(BaseModel):
    compute_unit_hours: float = Field(..., examples=[12.5])
    monthly_limit: float = Field(..., examples=[100.0])
    monthly_used: float = Field(..., examples=[45.5])
    monthly_remaining: float = Field(..., examples=[54.5])
    extra_remaining: float = Field(..., examples=[50.0])
    total_remaining: float = Field(..., examples=[104.5])
    unit: str = Field(default="CU-hours", examples=["CU-hours"])


class StorageUsage(BaseModel):
    gib_hours: float = Field(..., examples=[120.0])
    current_used_gib: int = Field(..., examples=[5])
    total_quota_gib: int = Field(..., examples=[10])
    available_gib: int = Field(..., examples=[5])
    unit: str = Field(default="GiB", examples=["GiB"])


class UsageLimits(BaseModel):
    max_concurrent_running: int = Field(..., examples=[3])
    current_running: int = Field(..., examples=[1])
    max_sandbox_duration_seconds: int = Field(..., examples=[7200])
    allowed_templates: list[str] = Field(
        ..., examples=[["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"]]
    )


class GracePeriodStatus(BaseModel):
    active: bool = Field(..., examples=[False])
    started_at: str | None = Field(default=None, examples=[None])
    expires_at: str | None = Field(default=None, examples=[None])
    grace_period_seconds: int = Field(..., examples=[1800])


class UsageSummaryResponse(BaseModel):
    tier: str = Field(..., examples=["pro"])
    billing_period: BillingPeriod
    compute: ComputeUsage
    storage: StorageUsage
    limits: UsageLimits
    grace_period: GracePeriodStatus


class UserPlanResponse(BaseModel):
    id: str = Field(..., examples=["planabc123def456"])
    user_id: str = Field(..., examples=["userabc123def456"])
    tier: str = Field(..., examples=["pro"])
    compute_units_monthly_limit: float = Field(..., examples=[100.0])
    compute_units_monthly_used: float = Field(..., examples=[45.5])
    storage_capacity_limit_gib: int = Field(..., examples=[10])
    max_concurrent_running: int = Field(..., examples=[3])
    max_sandbox_duration_seconds: int = Field(..., examples=[7200])
    allowed_templates: list[str] = Field(
        ..., examples=[["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"]]
    )
    grace_period_seconds: int = Field(..., examples=[1800])
    overrides: dict[str, Any] | None = Field(default=None)
    billing_period_start: str = Field(..., examples=["2026-03-01T00:00:00+00:00"])
    billing_period_end: str = Field(..., examples=["2026-04-01T00:00:00+00:00"])
    grace_period_started_at: str | None = Field(default=None)
    warning_80_notified_at: str | None = Field(default=None)
    warning_100_notified_at: str | None = Field(default=None)
    created_at: str = Field(..., examples=["2026-01-15T08:00:00+00:00"])
    updated_at: str = Field(..., examples=["2026-03-01T00:00:00+00:00"])


class ComputeSessionItem(BaseModel):
    id: str = Field(..., examples=["csabc123def456"])
    sandbox_id: str = Field(..., examples=["sbabc123def456"])
    template: str = Field(..., examples=["aio-sandbox-small"])
    vcpu_request: float = Field(..., examples=[0.5])
    memory_gib_request: float = Field(..., examples=[1.0])
    started_at: str = Field(..., examples=["2026-03-26T08:00:00+00:00"])
    ended_at: str | None = Field(default=None)
    duration_seconds: float = Field(..., examples=[7200])
    compute_unit_hours: float = Field(..., examples=[1.0])
    vcpu_hours: float = Field(..., examples=[1.0])
    memory_gib_hours: float = Field(..., examples=[2.0])
    status: str = Field(..., examples=["active"])


class ComputeSessionListResponse(BaseModel):
    items: list[ComputeSessionItem]
    total: int = Field(..., examples=[42])
    limit: int = Field(..., examples=[20])
    offset: int = Field(..., examples=[0])


class StorageLedgerItem(BaseModel):
    id: str = Field(..., examples=["slabc123def456"])
    sandbox_id: str | None = Field(default=None, examples=["sbabc123def456"])
    size_gib: int = Field(..., examples=[10])
    storage_state: str = Field(..., examples=["active"])
    allocated_at: str = Field(..., examples=["2026-03-26T08:00:00+00:00"])
    released_at: str | None = Field(default=None)
    gib_hours_consumed: float = Field(..., examples=[120.0])
    last_metered_at: str = Field(..., examples=["2026-03-26T09:00:00+00:00"])


class StorageLedgerListResponse(BaseModel):
    items: list[StorageLedgerItem]
    total: int = Field(..., examples=[5])
    limit: int = Field(..., examples=[20])
    offset: int = Field(..., examples=[0])


class ComputeGrantItem(BaseModel):
    id: str = Field(..., examples=["cgabc123def456"])
    grant_type: str = Field(..., examples=["admin_grant"])
    original_amount: float = Field(..., examples=[100.0])
    remaining_amount: float = Field(..., examples=[50.0])
    reason: str | None = Field(default=None, examples=["Special support"])
    granted_by: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    status: str = Field(..., examples=["active"])
    granted_at: str = Field(..., examples=["2026-03-01T00:00:00+00:00"])
    expires_at: str | None = Field(default=None, examples=["2026-06-01T00:00:00+00:00"])


class StorageQuotaGrantItem(BaseModel):
    id: str = Field(..., examples=["sqgabc123def456"])
    grant_type: str = Field(..., examples=["admin_grant"])
    size_gib: int = Field(..., examples=[20])
    reason: str | None = Field(default=None, examples=["Storage addon"])
    granted_by: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    status: str = Field(..., examples=["active"])
    granted_at: str = Field(..., examples=["2026-03-01T00:00:00+00:00"])
    expires_at: str | None = Field(default=None, examples=["2026-06-01T00:00:00+00:00"])


class GrantsResponse(BaseModel):
    compute_grants: list[ComputeGrantItem]
    storage_quota_grants: list[StorageQuotaGrantItem]


# ── Metering — Admin ─────────────────────────────────────────────────────────


class UpdatePlanRequest(BaseModel):
    tier: str | None = Field(default=None, examples=["ultra"])
    overrides: dict[str, Any] | None = Field(default=None, examples=[{"compute_units_monthly_limit": 500}])

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdatePlanRequest:
        if self.tier is None and self.overrides is None:
            raise ValueError("At least one of 'tier' or 'overrides' must be provided.")
        return self


class CreateComputeGrantRequest(BaseModel):
    amount: float = Field(..., gt=0, examples=[100])
    grant_type: str = Field(..., examples=["admin_grant"])
    reason: str | None = Field(default=None, examples=["Special support"])
    campaign_id: str | None = Field(default=None)
    expires_at: datetime | None = Field(default=None, examples=["2026-06-01T00:00:00Z"])


class CreateStorageQuotaGrantRequest(BaseModel):
    size_gib: int = Field(..., gt=0, examples=[20])
    grant_type: str = Field(..., examples=["admin_grant"])
    reason: str | None = Field(default=None, examples=["Storage addon"])
    campaign_id: str | None = Field(default=None)
    expires_at: datetime | None = Field(default=None, examples=["2026-06-01T00:00:00Z"])


class CreateComputeGrantResponse(BaseModel):
    id: str = Field(..., examples=["cgabc123def456"])
    user_id: str = Field(..., examples=["userabc123def456"])
    original_amount: float = Field(..., examples=[100.0])
    remaining_amount: float = Field(..., examples=[100.0])
    grant_type: str = Field(..., examples=["admin_grant"])
    reason: str | None = Field(default=None)
    granted_by: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    granted_at: str = Field(..., examples=["2026-03-26T12:00:00+00:00"])
    expires_at: str | None = Field(default=None)


class CreateStorageQuotaGrantResponse(BaseModel):
    id: str = Field(..., examples=["sqgabc123def456"])
    user_id: str = Field(..., examples=["userabc123def456"])
    size_gib: int = Field(..., examples=[20])
    grant_type: str = Field(..., examples=["admin_grant"])
    reason: str | None = Field(default=None)
    granted_by: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    granted_at: str = Field(..., examples=["2026-03-26T12:00:00+00:00"])
    expires_at: str | None = Field(default=None)


class TierTemplateItem(BaseModel):
    tier: str = Field(..., examples=["pro"])
    compute_units_monthly: float = Field(..., examples=[100.0])
    storage_capacity_gib: int = Field(..., examples=[10])
    max_concurrent_running: int = Field(..., examples=[3])
    max_sandbox_duration_seconds: int = Field(..., examples=[7200])
    allowed_templates: list[str] = Field(
        ..., examples=[["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"]]
    )
    grace_period_seconds: int = Field(..., examples=[1800])
    is_active: bool = Field(..., examples=[True])
    created_at: str = Field(..., examples=["2026-01-01T00:00:00+00:00"])
    updated_at: str = Field(..., examples=["2026-01-01T00:00:00+00:00"])


class TierTemplateListResponse(BaseModel):
    items: list[TierTemplateItem]


class UpdateTierTemplateRequest(BaseModel):
    compute_units_monthly: float | None = Field(default=None, examples=[150])
    storage_capacity_gib: int | None = Field(default=None, examples=[15])
    max_concurrent_running: int | None = Field(default=None, examples=[5])
    max_sandbox_duration_seconds: int | None = Field(default=None, examples=[14400])
    allowed_templates: list[str] | None = Field(
        default=None,
        examples=[["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium", "aio-sandbox-large"]],
    )
    grace_period_seconds: int | None = Field(default=None, examples=[3600])
    apply_to_existing: bool = Field(default=False)

    @model_validator(mode="after")
    def at_least_one_update(self) -> UpdateTierTemplateRequest:
        updatable = (
            self.compute_units_monthly,
            self.storage_capacity_gib,
            self.max_concurrent_running,
            self.max_sandbox_duration_seconds,
            self.grace_period_seconds,
        )
        has_update = any(v is not None for v in updatable) or self.allowed_templates is not None
        if not has_update:
            raise ValueError("At least one field to update must be provided.")
        return self


class UpdateTierTemplateResponse(TierTemplateItem):
    users_affected: int = Field(..., examples=[0])


class BatchComputeGrantRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=1000)
    amount: float = Field(..., gt=0, examples=[50])
    grant_type: str = Field(..., examples=["campaign"])
    campaign_id: str | None = Field(default=None, examples=["spring_2026_promo"])
    reason: str | None = Field(default=None, examples=["Spring promotion"])
    expires_at: datetime | None = Field(default=None, examples=["2026-06-01T00:00:00Z"])


class BatchStorageQuotaGrantRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=1000)
    size_gib: int = Field(..., gt=0, examples=[10])
    grant_type: str = Field(..., examples=["campaign"])
    campaign_id: str | None = Field(default=None, examples=["spring_2026_promo"])
    reason: str | None = Field(default=None, examples=["Spring promotion"])
    expires_at: datetime | None = Field(default=None, examples=["2026-06-01T00:00:00Z"])


class BatchGrantResultItem(BaseModel):
    user_id: str = Field(..., examples=["userabc123"])
    grant_id: str | None = Field(default=None, examples=["cgabc123"])
    status: str = Field(..., examples=["success"])
    error: str | None = Field(default=None)


class BatchGrantResponse(BaseModel):
    total_requested: int = Field(..., examples=[3])
    succeeded: int = Field(..., examples=[2])
    failed: int = Field(..., examples=[1])
    results: list[BatchGrantResultItem]


class UserLookupResponse(BaseModel):
    user_id: str = Field(..., examples=["userabc123def456"])
    email: str = Field(..., examples=["alice@example.com"])


class ResolveEmailsRequest(BaseModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=1000, examples=[["alice@example.com"]])


class ResolveEmailsResultItem(BaseModel):
    email: str = Field(..., examples=["alice@example.com"])
    user_id: str | None = Field(default=None, examples=["userabc123def456"])
    error: str | None = Field(default=None)


class ResolveEmailsResponse(BaseModel):
    results: list[ResolveEmailsResultItem]


class AuditFilterOptionsResponse(BaseModel):
    actions: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)
    results: list[str] = Field(default_factory=list)
