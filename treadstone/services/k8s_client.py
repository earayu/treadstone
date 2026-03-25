"""K8s client for agent-sandbox CRD operations.

Treadstone uses dual-path sandbox provisioning:
- SandboxClaim path (extensions.agents.x-k8s.io) — ephemeral sandboxes, WarmPool-eligible
- Direct Sandbox path (agents.x-k8s.io) — persistent storage via volumeClaimTemplates
- SandboxTemplate (extensions.agents.x-k8s.io) — Read-only config catalog

Two implementations:
- FakeK8sClient: In-memory stub for testing
- Kr8sClient: Real K8s API calls via kr8s (async), used in production
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

CLAIM_API_GROUP = "extensions.agents.x-k8s.io"
CLAIM_API_VERSION = "v1alpha1"
SANDBOX_API_GROUP = "agents.x-k8s.io"
SANDBOX_API_VERSION = "v1alpha1"
TEMPLATE_API_GROUP = "extensions.agents.x-k8s.io"
TEMPLATE_API_VERSION = "v1alpha1"

WATCH_TIMEOUT_SECONDS = 300


class WatchExpiredError(Exception):
    """Raised when the K8s API returns 410 Gone for an expired resourceVersion."""


def format_shutdown_time(dt: datetime) -> str:
    """Format a datetime as RFC3339 for K8s shutdownTime field."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@runtime_checkable
class K8sClientProtocol(Protocol):
    # ── SandboxClaim (extensions.agents.x-k8s.io) ──
    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: datetime | None = None
    ) -> dict[str, Any]: ...

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool: ...

    async def get_sandbox_claim(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    # ── Sandbox (agents.x-k8s.io) — direct create + read + scale ──
    async def create_sandbox(
        self,
        name: str,
        namespace: str,
        image: str,
        container_port: int,
        resources: dict[str, Any],
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
    ) -> dict[str, Any]: ...

    async def delete_sandbox(self, name: str, namespace: str) -> bool: ...

    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]: ...

    async def list_sandboxes_with_metadata(self, namespace: str) -> dict[str, Any]: ...

    async def watch_sandboxes(
        self, namespace: str, resource_version: str = ""
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]: ...

    async def scale_sandbox(self, name: str, namespace: str, replicas: int) -> bool: ...

    async def get_storage_class(self, name: str) -> dict[str, Any] | None: ...

    # ── SandboxTemplate (extensions.agents.x-k8s.io) — read only ──
    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]: ...


# ──────────────────────────────────────────────────────────────────────────────
# Real K8s client via kr8s
# ──────────────────────────────────────────────────────────────────────────────


class Kr8sClient:
    """Production K8s client using kr8s (async). Uses in-cluster config automatically."""

    def __init__(self) -> None:
        self._api = None
        self._lock = asyncio.Lock()

    async def _get_api(self):
        async with self._lock:
            if self._api is None:
                import kr8s

                self._api = await kr8s.asyncio.api()
        return self._api

    # ── SandboxClaim ──

    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: datetime | None = None
    ) -> dict[str, Any]:
        api = await self._get_api()
        manifest: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
        }
        if shutdown_time:
            manifest["spec"]["lifecycle"] = {"shutdownTime": format_shutdown_time(shutdown_time)}

        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims"
        logger.info("K8s POST %s (name=%s)", url, name)
        async with api.call_api("POST", base=url, version="", json=manifest) as resp:
            return resp.json()

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims/{name}"
        logger.info("K8s DELETE %s", url)
        async with api.call_api("DELETE", base=url, version="") as resp:
            return resp.status_code < 400

    async def get_sandbox_claim(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    # ── Sandbox (direct create) ──

    async def create_sandbox(
        self,
        name: str,
        namespace: str,
        image: str,
        container_port: int,
        resources: dict[str, Any],
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
    ) -> dict[str, Any]:
        api = await self._get_api()
        container: dict[str, Any] = {
            "name": "sandbox",
            "image": image,
            "ports": [{"containerPort": container_port}],
            "resources": resources,
        }
        if volume_claim_templates:
            container["volumeMounts"] = [
                {"name": vct["metadata"]["name"], "mountPath": "/home/gem/workspace"} for vct in volume_claim_templates
            ]

        manifest: dict[str, Any] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
            "kind": "Sandbox",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "replicas": 1,
                "podTemplate": {"spec": {"containers": [container], "restartPolicy": "OnFailure"}},
            },
        }
        if volume_claim_templates:
            manifest["spec"]["volumeClaimTemplates"] = volume_claim_templates
        if shutdown_time:
            manifest["spec"]["shutdownTime"] = format_shutdown_time(shutdown_time)

        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        logger.info("K8s POST %s (name=%s, direct=true)", url, name)
        async with api.call_api("POST", base=url, version="", json=manifest) as resp:
            return resp.json()

    async def delete_sandbox(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}"
        logger.info("K8s DELETE %s", url)
        async with api.call_api("DELETE", base=url, version="") as resp:
            return resp.status_code < 400

    # ── Sandbox (read + scale) ──

    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        async with api.call_api("GET", base=url, version="") as resp:
            data = resp.json()
            return data.get("items", [])

    async def list_sandboxes_with_metadata(self, namespace: str) -> dict[str, Any]:
        """List sandboxes and return the full response including list-level metadata."""
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        async with api.call_api("GET", base=url, version="") as resp:
            return resp.json()

    async def watch_sandboxes(
        self, namespace: str, resource_version: str = ""
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Stream Watch events for Sandbox CRs. Raises WatchExpiredError on 410 Gone."""
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        params = {"watch": "true", "timeoutSeconds": str(WATCH_TIMEOUT_SECONDS)}
        if resource_version:
            params["resourceVersion"] = resource_version

        logger.info("Starting K8s Watch on %s (rv=%s)", url, resource_version or "<latest>")
        async with api.call_api("GET", base=url, version="", params=params, stream=True) as resp:
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Malformed Watch event line, skipping: %s", line[:200])
                    continue

                event_type = event.get("type", "")
                obj = event.get("object", {})

                if event_type == "ERROR":
                    code = obj.get("code", 0)
                    if code == 410:
                        raise WatchExpiredError(obj.get("message", "resourceVersion expired"))
                    logger.error("Watch ERROR event: %s", obj.get("message", event))
                    continue

                if event_type in ("ADDED", "MODIFIED", "DELETED"):
                    yield event_type, obj

    async def scale_sandbox(self, name: str, namespace: str, replicas: int) -> bool:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}/scale"
        logger.info("K8s PATCH %s (replicas=%d)", url, replicas)
        scale_body = {"spec": {"replicas": replicas}}
        async with api.call_api(
            "PATCH",
            base=url,
            version="",
            json=scale_body,
            headers={"Content-Type": "application/merge-patch+json"},
        ) as resp:
            return resp.status_code < 400

    async def get_storage_class(self, name: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/storage.k8s.io/v1/storageclasses/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    # ── SandboxTemplate ──

    async def list_sandbox_templates(self, namespace: str) -> list[dict[str, Any]]:
        api = await self._get_api()
        url = f"/apis/{TEMPLATE_API_GROUP}/{TEMPLATE_API_VERSION}/namespaces/{namespace}/sandboxtemplates"
        async with api.call_api("GET", base=url, version="") as resp:
            data = resp.json()
            items = data.get("items", [])
            return [_parse_sandbox_template(t) for t in items]


def _parse_sandbox_template(template: dict) -> dict:
    containers = template.get("spec", {}).get("podTemplate", {}).get("spec", {}).get("containers", [])
    image = ""
    resource_spec: dict[str, str] = {}
    if containers:
        image = containers[0].get("image", "")
        resources = containers[0].get("resources", {})
        requests = resources.get("requests", {})
        resource_spec = {"cpu": requests.get("cpu", ""), "memory": requests.get("memory", "")}
    return {
        "name": template["metadata"]["name"],
        "display_name": template["metadata"].get("annotations", {}).get("display-name", template["metadata"]["name"]),
        "description": template["metadata"].get("annotations", {}).get("description", ""),
        "image": image,
        "resource_spec": resource_spec,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Fake K8s client for testing
# ──────────────────────────────────────────────────────────────────────────────


def _make_ready_condition(status: str = "False", reason: str = "DependenciesNotReady", message: str = "") -> dict:
    return {"type": "Ready", "status": status, "reason": reason, "message": message}


class FakeK8sClient:
    """In-memory stub for testing — simulates the agent-sandbox controller behavior."""

    _DEFAULT_IMAGE = "ghcr.io/agent-infra/sandbox:latest"

    _DEFAULT_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "name": "aio-sandbox-tiny",
            "display_name": "AIO Sandbox Tiny",
            "description": "Lightweight sandbox for code execution and scripting",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "250m", "memory": "512Mi"},
        },
        {
            "name": "aio-sandbox-small",
            "display_name": "AIO Sandbox Small",
            "description": "Small sandbox for simple development tasks",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "500m", "memory": "1Gi"},
        },
        {
            "name": "aio-sandbox-medium",
            "display_name": "AIO Sandbox Medium",
            "description": "General-purpose development environment",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "1", "memory": "2Gi"},
        },
        {
            "name": "aio-sandbox-large",
            "display_name": "AIO Sandbox Large",
            "description": "Full-featured sandbox with browser automation",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "2", "memory": "4Gi"},
        },
        {
            "name": "aio-sandbox-xlarge",
            "display_name": "AIO Sandbox XLarge",
            "description": "Heavy workloads with maximum resources",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "4", "memory": "8Gi"},
        },
    )

    def __init__(self) -> None:
        self._templates: list[dict[str, Any]] = list(self._DEFAULT_TEMPLATES)
        self._claims: dict[str, dict[str, Any]] = {}
        self._sandboxes: dict[str, dict[str, Any]] = {}
        self._storage_classes: dict[str, dict[str, Any]] = {
            "treadstone-workspace": {
                "apiVersion": "storage.k8s.io/v1",
                "kind": "StorageClass",
                "metadata": {"name": "treadstone-workspace"},
                "provisioner": "test.fake.provisioner",
            }
        }
        self._watch_queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def create_sandbox_claim(
        self, name: str, template_ref: str, namespace: str, shutdown_time: datetime | None = None
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        sandbox_name = name
        claim: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": {"name": name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
            "status": {"conditions": [], "sandbox": {"Name": sandbox_name}},
        }
        if shutdown_time:
            claim["spec"]["lifecycle"] = {"shutdownTime": format_shutdown_time(shutdown_time)}
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

    # ── Sandbox (direct create) ──

    async def create_sandbox(
        self,
        name: str,
        namespace: str,
        image: str,
        container_port: int,
        resources: dict[str, Any],
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        sandbox: dict[str, Any] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
            "kind": "Sandbox",
            "metadata": {"name": name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {
                "replicas": 1,
                "podTemplate": {
                    "spec": {
                        "containers": [{"name": "sandbox", "image": image, "resources": resources}],
                    },
                },
            },
            "status": {
                "conditions": [_make_ready_condition("False", "DependenciesNotReady", "Pod does not exist")],
                "serviceFQDN": f"{name}.{namespace}.svc.cluster.local",
                "service": name,
                "replicas": 0,
            },
        }
        if volume_claim_templates:
            sandbox["spec"]["volumeClaimTemplates"] = volume_claim_templates
        if shutdown_time:
            sandbox["spec"]["shutdownTime"] = format_shutdown_time(shutdown_time)
        self._sandboxes[key] = sandbox
        return sandbox

    async def delete_sandbox(self, name: str, namespace: str) -> bool:
        key = f"{namespace}/{name}"
        self._sandboxes.pop(key, None)
        return True

    async def get_sandbox(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._sandboxes.get(f"{namespace}/{name}")

    async def list_sandboxes(self, namespace: str) -> list[dict[str, Any]]:
        return [sb for key, sb in self._sandboxes.items() if key.startswith(f"{namespace}/")]

    async def list_sandboxes_with_metadata(self, namespace: str) -> dict[str, Any]:
        items = await self.list_sandboxes(namespace)
        max_rv = "0"
        for item in items:
            rv = item.get("metadata", {}).get("resourceVersion", "0")
            if int(rv) > int(max_rv):
                max_rv = rv
        return {"metadata": {"resourceVersion": max_rv}, "items": items}

    async def watch_sandboxes(
        self, namespace: str, resource_version: str = ""
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield events from the test queue. Send None to stop the stream."""
        while True:
            event = await self._watch_queue.get()
            if event is None:
                return
            yield event

    def enqueue_watch_event(self, event_type: str, cr_object: dict[str, Any]) -> None:
        """Inject a Watch event for testing."""
        self._watch_queue.put_nowait((event_type, cr_object))

    def stop_watch(self) -> None:
        """Signal the fake watch stream to stop."""
        self._watch_queue.put_nowait(None)

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

    async def get_storage_class(self, name: str) -> dict[str, Any] | None:
        return self._storage_classes.get(name)

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

    def remove_storage_class(self, name: str) -> None:
        self._storage_classes.pop(name, None)


# ──────────────────────────────────────────────────────────────────────────────
# Singleton management
# ──────────────────────────────────────────────────────────────────────────────

_k8s_client: K8sClientProtocol | None = None


def get_k8s_client() -> K8sClientProtocol:
    global _k8s_client
    if _k8s_client is None:
        logger.info("Using Kr8sClient")
        _k8s_client = Kr8sClient()
    return _k8s_client


def set_k8s_client(client: K8sClientProtocol) -> None:
    global _k8s_client
    _k8s_client = client
