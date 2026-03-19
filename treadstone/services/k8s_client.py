"""K8s client for Sandbox CR and SandboxTemplate CR operations.

Provides a Protocol for dependency injection and a FakeK8sClient for testing.
Real K8s integration will use kr8s or kubernetes-asyncio.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class K8sClientProtocol(Protocol):
    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]: ...
    async def create_sandbox_cr(self, name: str, template: str, namespace: str, image: str) -> dict[str, Any]: ...
    async def delete_sandbox_cr(self, name: str, namespace: str) -> bool: ...
    async def get_sandbox_cr(self, name: str, namespace: str) -> dict[str, Any] | None: ...
    async def list_sandbox_crs(self, namespace: str) -> list[dict[str, Any]]: ...
    async def start_sandbox_cr(self, name: str, namespace: str) -> bool: ...
    async def stop_sandbox_cr(self, name: str, namespace: str) -> bool: ...


class FakeK8sClient:
    """In-memory stub for testing — returns sample templates and succeeds all operations."""

    _templates: list[dict[str, Any]] = [
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
    ]

    _sandbox_crs: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self._sandbox_crs = {}

    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]:
        return list(self._templates)

    async def create_sandbox_cr(self, name: str, template: str, namespace: str, image: str) -> dict[str, Any]:
        cr = {
            "metadata": {"name": name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {"template": template, "image": image},
            "status": {"phase": "Creating"},
        }
        self._sandbox_crs[f"{namespace}/{name}"] = cr
        return cr

    async def delete_sandbox_cr(self, name: str, namespace: str) -> bool:
        self._sandbox_crs.pop(f"{namespace}/{name}", None)
        return True

    async def get_sandbox_cr(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._sandbox_crs.get(f"{namespace}/{name}")

    async def list_sandbox_crs(self, namespace: str) -> list[dict[str, Any]]:
        return [cr for key, cr in self._sandbox_crs.items() if key.startswith(f"{namespace}/")]

    async def start_sandbox_cr(self, name: str, namespace: str) -> bool:
        cr = self._sandbox_crs.get(f"{namespace}/{name}")
        if cr:
            cr["status"]["phase"] = "Ready"
        return True

    async def stop_sandbox_cr(self, name: str, namespace: str) -> bool:
        cr = self._sandbox_crs.get(f"{namespace}/{name}")
        if cr:
            cr["status"]["phase"] = "Stopped"
        return True


_k8s_client: K8sClientProtocol | None = None


def get_k8s_client() -> K8sClientProtocol:
    global _k8s_client
    if _k8s_client is None:
        _k8s_client = FakeK8sClient()
    return _k8s_client


def set_k8s_client(client: K8sClientProtocol) -> None:
    global _k8s_client
    _k8s_client = client
