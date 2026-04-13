"""Protocols for observing sandbox state transitions and running reconciliation hooks.

These protocols decouple the K8s sync loop (infra) from side-effect providers
(metering, audit, etc.).  The infra module owns the Protocol definitions; other
modules provide concrete implementations that are wired up at startup in main.py.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

__all__ = [
    "ReconcileHook",
    "SandboxStateObserver",
    "register_observer",
    "register_reconcile_hook",
    "get_observers",
    "get_reconcile_hooks",
    "clear_observers",
    "clear_reconcile_hooks",
]


class SandboxStateObserver(Protocol):
    """Observer for sandbox lifecycle events fired by the K8s sync loop.

    Implementations must be best-effort: exceptions are caught by the caller
    and logged but never block the sync pipeline.  Reconciliation hooks repair
    any missed operations.
    """

    async def on_sandbox_ready(
        self,
        session: AsyncSession,
        sandbox_id: str,
        owner_id: str,
        template: str,
    ) -> None:
        """Called when a sandbox transitions *to* READY from a non-READY state."""
        ...

    async def on_sandbox_stopped(
        self,
        session: AsyncSession,
        sandbox_id: str,
    ) -> None:
        """Called when a READY sandbox transitions to STOPPED, COLD, ERROR, or DELETING."""
        ...

    async def on_sandbox_deleted(
        self,
        session: AsyncSession,
        sandbox_id: str,
        persist: bool,
    ) -> None:
        """Called when a sandbox CR is deleted (Watch DELETED or reconcile finalizes DELETING).

        *persist* indicates whether the sandbox had persistent storage that may
        need ledger release.
        """
        ...


class ReconcileHook(Protocol):
    """Hook called during periodic reconciliation to repair domain-specific drift.

    Each hook receives the session factory and runs its own session scope.
    Exceptions are caught and logged by the caller.
    """

    async def __call__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None: ...


# ── Module-level registries ──────────────────────────────────────────────────

_observers: list[SandboxStateObserver] = []
_reconcile_hooks: list[ReconcileHook] = []


def register_observer(observer: SandboxStateObserver) -> None:
    """Register a SandboxStateObserver to receive lifecycle events."""
    _observers.append(observer)


def register_reconcile_hook(hook: ReconcileHook) -> None:
    """Register a ReconcileHook to run during periodic reconciliation."""
    _reconcile_hooks.append(hook)


def get_observers() -> list[SandboxStateObserver]:
    """Return all registered observers (read-only snapshot)."""
    return list(_observers)


def get_reconcile_hooks() -> list[ReconcileHook]:
    """Return all registered reconcile hooks (read-only snapshot)."""
    return list(_reconcile_hooks)


def clear_observers() -> None:
    """Remove all registered observers.  Useful for testing."""
    _observers.clear()


def clear_reconcile_hooks() -> None:
    """Remove all registered reconcile hooks.  Useful for testing."""
    _reconcile_hooks.clear()
