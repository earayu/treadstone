"""K8s client for agent-sandbox CRD operations.

Treadstone interacts with 3 CRD types from kubernetes-sigs/agent-sandbox:
- SandboxClaim (extensions.agents.x-k8s.io) — Treadstone creates/deletes these
- Sandbox (agents.x-k8s.io) — Created by Claim Controller, Treadstone watches + scales
- SandboxTemplate (extensions.agents.x-k8s.io) — Read-only, pre-deployed by admin

Two implementations:
- FakeK8sClient: In-memory stub for testing
- Kr8sClient: Real K8s API calls via kr8s (async), used in production
"""

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

CLAIM_API_GROUP = "extensions.agents.x-k8s.io"
CLAIM_API_VERSION = "v1alpha1"
SANDBOX_API_GROUP = "agents.x-k8s.io"
SANDBOX_API_VERSION = "v1alpha1"
TEMPLATE_API_GROUP = "extensions.agents.x-k8s.io"
TEMPLATE_API_VERSION = "v1alpha1"


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


# ──────────────────────────────────────────────────────────────────────────────
# Real K8s client via kr8s
# ──────────────────────────────────────────────────────────────────────────────


class Kr8sClient:
    """Production K8s client using kr8s (async). Uses in-cluster config automatically."""

    def __init__(self) -> None:
        self._api = None

    async def _get_api(self):
        if self._api is None:
            import kr8s

            self._api = await kr8s.asyncio.api()
        return self._api

    # ── SandboxClaim ──

    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: str | None = None
    ) -> dict[str, Any]:
        api = await self._get_api()
        manifest: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
        }
        if shutdown_time:
            manifest["spec"]["lifecycle"] = {"shutdownTime": shutdown_time}

        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims"
        logger.info("K8s POST %s (name=%s)", url, name)
        async with api.call_api("POST", url=url, data=manifest) as resp:
            return resp.json()

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims/{name}"
        logger.info("K8s DELETE %s", url)
        async with api.call_api("DELETE", url=url) as resp:
            return resp.status_code < 400

    async def get_sandbox_claim(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims/{name}"
        async with api.call_api("GET", url=url) as resp:
            if resp.status_code == 404:
                return None
            return resp.json()

    # ── Sandbox ──

    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}"
        async with api.call_api("GET", url=url) as resp:
            if resp.status_code == 404:
                return None
            return resp.json()

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        async with api.call_api("GET", url=url) as resp:
            data = resp.json()
            return data.get("items", [])

    async def scale_sandbox(self, name: str, namespace: str, replicas: int) -> bool:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}/scale"
        logger.info("K8s PATCH %s (replicas=%d)", url, replicas)
        scale_body = {"spec": {"replicas": replicas}}
        async with api.call_api(
            "PATCH",
            url=url,
            data=scale_body,
            headers={"Content-Type": "application/merge-patch+json"},
        ) as resp:
            return resp.status_code < 400

    # ── SandboxTemplate ──

    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]:
        api = await self._get_api()
        url = f"/apis/{TEMPLATE_API_GROUP}/{TEMPLATE_API_VERSION}/namespaces/{namespace}/sandboxtemplates"
        async with api.call_api("GET", url=url) as resp:
            data = resp.json()
            items = data.get("items", [])
            return [
                {
                    "name": t["metadata"]["name"],
                    "display_name": t["metadata"].get("annotations", {}).get("display-name", t["metadata"]["name"]),
                    "description": t["metadata"].get("annotations", {}).get("description", ""),
                    "runtime_type": "aio",
                    "resource_spec": _extract_resource_spec(t),
                }
                for t in items
            ]


def _extract_resource_spec(template: dict) -> dict:
    containers = template.get("spec", {}).get("podTemplate", {}).get("spec", {}).get("containers", [])
    if containers:
        resources = containers[0].get("resources", {})
        requests = resources.get("requests", {})
        return {"cpu": requests.get("cpu", ""), "memory": requests.get("memory", "")}
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Fake K8s client for testing
# ──────────────────────────────────────────────────────────────────────────────


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

    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: str | None = None
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        lifecycle = {}
        if shutdown_time:
            lifecycle["shutdownTime"] = shutdown_time

        sandbox_name = name
        claim: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": {"name": name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
            "status": {"conditions": [], "sandbox": {"Name": sandbox_name}},
        }
        if lifecycle:
            claim["spec"]["lifecycle"] = lifecycle
        self._claims[key] = claim

        self._sandboxes[key] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
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

    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]:
        return list(self._templates)

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


# ──────────────────────────────────────────────────────────────────────────────
# Singleton management
# ──────────────────────────────────────────────────────────────────────────────

_k8s_client: K8sClientProtocol | None = None


def get_k8s_client() -> K8sClientProtocol:
    global _k8s_client
    if _k8s_client is None:
        from treadstone.config import settings

        if settings.debug:
            logger.info("Using FakeK8sClient (debug mode)")
            _k8s_client = FakeK8sClient()
        else:
            logger.info("Using Kr8sClient (production mode)")
            _k8s_client = Kr8sClient()
    return _k8s_client


def set_k8s_client(client: K8sClientProtocol) -> None:
    global _k8s_client
    _k8s_client = client
