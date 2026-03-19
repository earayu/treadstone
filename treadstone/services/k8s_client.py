"""K8s client for agent-sandbox CRD operations.

Treadstone interacts with 3 CRD types from kubernetes-sigs/agent-sandbox:
- SandboxClaim (extensions.agents.x-k8s.io) — Treadstone creates/deletes these
- Sandbox (agents.x-k8s.io) — Created by Claim Controller, Treadstone watches + scales
- SandboxTemplate (extensions.agents.x-k8s.io) — Read-only, pre-deployed by admin

Provides a Protocol for dependency injection and a FakeK8sClient for testing.
Real K8s integration will use kr8s or kubernetes-asyncio.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class K8sClientProtocol(Protocol):
    # ── SandboxClaim (extensions.agents.x-k8s.io) ──
    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: str | None = None
    ) -> dict[str, Any]: ...

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool: ...

    async def get_sandbox_claim(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    # ── Sandbox (agents.x-k8s.io) — read + scale only ──
    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]: ...

    async def scale_sandbox(self, name: str, namespace: str, replicas: int) -> bool: ...

    # ── SandboxTemplate (extensions.agents.x-k8s.io) — read only ──
    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]: ...


def _make_ready_condition(status: str = "False", reason: str = "DependenciesNotReady", message: str = "") -> dict:
    return {"type": "Ready", "status": status, "reason": reason, "message": message}


class FakeK8sClient:
    """In-memory stub for testing — simulates the agent-sandbox controller behavior."""

    _DEFAULT_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "name": "python-dev",
            "display_name": "Python Development",
            "description": "Python 3.12 with common data science libraries",
            "runtime_type": "aio",
            "resource_spec": {"cpu": "2", "memory": "2Gi"},
        },
        {
            "name": "nodejs-dev",
            "display_name": "Node.js Development",
            "description": "Node.js 20 with npm/yarn/pnpm",
            "runtime_type": "aio",
            "resource_spec": {"cpu": "2", "memory": "2Gi"},
        },
    )

    def __init__(self) -> None:
        self._templates: list[dict[str, Any]] = list(self._DEFAULT_TEMPLATES)
        self._claims: dict[str, dict[str, Any]] = {}
        self._sandboxes: dict[str, dict[str, Any]] = {}

    # ── SandboxClaim ──

    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: str | None = None
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        lifecycle = {}
        if shutdown_time:
            lifecycle["shutdownTime"] = shutdown_time

        sandbox_name = name

        claim: dict[str, Any] = {
            "apiVersion": "extensions.agents.x-k8s.io/v1alpha1",
            "kind": "SandboxClaim",
            "metadata": {"name": name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
            "status": {"conditions": [], "sandbox": {"Name": sandbox_name}},
        }
        if lifecycle:
            claim["spec"]["lifecycle"] = lifecycle
        self._claims[key] = claim

        self._sandboxes[key] = {
            "apiVersion": "agents.x-k8s.io/v1alpha1",
            "kind": "Sandbox",
            "metadata": {"name": sandbox_name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {"replicas": 1, "podTemplate": {"spec": {}}},
            "status": {
                "conditions": [_make_ready_condition("False", "DependenciesNotReady", "Pod does not exist")],
                "serviceFQDN": f"{sandbox_name}.{namespace}.svc.cluster.local",
                "service": sandbox_name,
                "replicas": 0,
            },
        }
        return claim

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool:
        key = f"{namespace}/{name}"
        self._claims.pop(key, None)
        self._sandboxes.pop(key, None)
        return True

    async def get_sandbox_claim(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._claims.get(f"{namespace}/{name}")

    # ── Sandbox ──

    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._sandboxes.get(f"{namespace}/{name}")

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]:
        return [sb for key, sb in self._sandboxes.items() if key.startswith(f"{namespace}/")]

    async def scale_sandbox(self, name: str, namespace: str, replicas: int) -> bool:
        key = f"{namespace}/{name}"
        sb = self._sandboxes.get(key)
        if sb is None:
            return False
        sb["spec"]["replicas"] = replicas
        sb["status"]["replicas"] = replicas
        if replicas == 0:
            sb["status"]["conditions"] = [
                _make_ready_condition("True", "DependenciesReady", "Pod does not exist, replicas is 0")
            ]
        else:
            sb["status"]["conditions"] = [
                _make_ready_condition("True", "DependenciesReady", "Pod is Ready; Service Exists")
            ]
        rv = str(int(sb["metadata"].get("resourceVersion", "1")) + 1)
        sb["metadata"]["resourceVersion"] = rv
        return True

    # ── SandboxTemplate ──

    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]:
        return list(self._templates)

    # ── Test helpers ──

    def simulate_sandbox_ready(self, name: str, namespace: str) -> None:
        """Simulate the controller making a Sandbox ready (for testing)."""
        key = f"{namespace}/{name}"
        sb = self._sandboxes.get(key)
        if sb:
            sb["status"]["conditions"] = [
                _make_ready_condition("True", "DependenciesReady", "Pod is Ready; Service Exists")
            ]
            sb["status"]["replicas"] = 1
            rv = str(int(sb["metadata"].get("resourceVersion", "1")) + 1)
            sb["metadata"]["resourceVersion"] = rv


_k8s_client: K8sClientProtocol | None = None


def get_k8s_client() -> K8sClientProtocol:
    global _k8s_client
    if _k8s_client is None:
        _k8s_client = FakeK8sClient()
    return _k8s_client


def set_k8s_client(client: K8sClientProtocol) -> None:
    global _k8s_client
    _k8s_client = client
