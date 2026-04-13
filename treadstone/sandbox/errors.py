"""Sandbox domain errors — lifecycle, provisioning, connectivity."""

from treadstone.core.errors import TreadstoneError

__all__ = [
    "SandboxNotFoundError",
    "TemplateNotFoundError",
    "SandboxNotReadyError",
    "SandboxUnreachableError",
    "SandboxTimeoutError",
    "SandboxNameConflictError",
    "SandboxTemplateCatalogUnavailableError",
    "InvalidTransitionError",
]


class SandboxNotFoundError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_not_found",
            message=f"Sandbox {sandbox_id} does not exist or you don't have access to it.",
            status=404,
        )


class TemplateNotFoundError(TreadstoneError):
    def __init__(self, template_name: str):
        super().__init__(
            code="template_not_found",
            message=f"Template '{template_name}' not found.",
            status=404,
        )


class SandboxNotReadyError(TreadstoneError):
    def __init__(self, sandbox_id: str, current_status: str):
        super().__init__(
            code="sandbox_not_ready",
            message=f"Sandbox {sandbox_id} is {current_status}, not ready for this operation.",
            status=409,
        )


class SandboxUnreachableError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_unreachable",
            message=f"Could not connect to sandbox {sandbox_id}.",
            status=502,
        )


class SandboxTimeoutError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_timeout",
            message=f"Sandbox {sandbox_id} did not respond in time.",
            status=504,
        )


class SandboxNameConflictError(TreadstoneError):
    def __init__(self, name: str):
        super().__init__(
            code="sandbox_name_conflict",
            message=f"A sandbox named '{name}' already exists for the current user.",
            status=409,
        )


class SandboxTemplateCatalogUnavailableError(TreadstoneError):
    def __init__(self, message: str = "Sandbox template catalog is temporarily unavailable."):
        super().__init__(
            code="sandbox_template_catalog_unavailable",
            message=message,
            status=503,
        )


class InvalidTransitionError(TreadstoneError):
    def __init__(self, sandbox_id: str, from_status: str, to_status: str):
        super().__init__(
            code="invalid_transition",
            message=f"Cannot transition sandbox {sandbox_id} from {from_status} to {to_status}.",
            status=409,
        )
