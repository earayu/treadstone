"""K8s client for agent-sandbox CRD operations.

Treadstone uses dual-path sandbox provisioning:
- SandboxClaim path (extensions.agents.x-k8s.io) — ephemeral sandboxes, WarmPool-eligible.
  Pods come from Helm ``SandboxTemplate`` resources (no PVC in template, no init container).
- Direct Sandbox path (agents.x-k8s.io) — persistent storage via ``volumeClaimTemplates``.
  When PVCs mount ``SANDBOX_HOME_DIR``, the volume hides the image home; ``init-home``
  seeds the PVC from the image layer on first boot (see ``Kr8sClient.create_sandbox``).
- SandboxTemplate (extensions.agents.x-k8s.io) — read-only catalog for the claim path.

Pod/container ``securityContext`` defaults here should stay aligned with
``deploy/sandbox-runtime/values.yaml`` (``sandboxPodSecurityContext``,
``sandboxContainerSecurityContext``).

Security note: the stock ``ghcr.io/agent-infra/sandbox`` image is **not
rootless-compatible**. Its entrypoint bootstraps the ``gem`` user/group and
other runtime state as root on every start. Defaults here therefore target a
**compatible hardening baseline**: keep seccomp and no-new-privilege style
controls, retain a writable root filesystem, and avoid explicit Linux
capability overrides. Some ACS/ECI policies reject any ``capabilities`` stanza
even when the image starts fine with runtime defaults. This is not Kubernetes
Pod Security Standards ``restricted`` compliance.

Two implementations:
- FakeK8sClient: In-memory stub for testing
- Kr8sClient: Real K8s API calls via kr8s (async), used in production
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

__all__ = [
    # API constants
    "CLAIM_API_GROUP",
    "CLAIM_API_VERSION",
    "SANDBOX_API_GROUP",
    "SANDBOX_API_VERSION",
    "TEMPLATE_API_GROUP",
    "TEMPLATE_API_VERSION",
    "SNAPSHOT_API_GROUP",
    "SNAPSHOT_API_VERSION",
    "WATCH_TIMEOUT_SECONDS",
    # Sandbox image / security constants
    "SANDBOX_HOME_DIR",
    "SANDBOX_UID",
    "SANDBOX_GID",
    "SANDBOX_READ_ONLY_ROOT_FILESYSTEM",
    # Probe defaults
    "DEFAULT_STARTUP_PROBE",
    "DEFAULT_READINESS_PROBE",
    # Label / annotation keys
    "ANNOTATION_ALLOWED_STORAGE_SIZES",
    "LABEL_SANDBOX_ID",
    "LABEL_OWNER_ID",
    "LABEL_TEMPLATE",
    "LABEL_PROVISION_MODE",
    "LABEL_WORKLOAD",
    "LABEL_STORAGE_ROLE",
    "WORKLOAD_SANDBOX",
    "PROVISION_MODE_CLAIM",
    "PROVISION_MODE_DIRECT",
    "STORAGE_ROLE_WORKSPACE",
    "ANNOTATION_SANDBOX_NAME",
    "ANNOTATION_CREATED_AT",
    # Classes
    "WatchExpiredError",
    "K8sClientProtocol",
    "Kr8sClient",
    "FakeK8sClient",
    # Public functions
    "format_shutdown_time",
    "get_k8s_client",
    "set_k8s_client",
    # Private helpers re-exported by shim
    "_parse_sandbox_template",
    "_sandbox_init_container_security_context",
    "_sandbox_main_container_security_context",
    "_sandbox_pod_security_context",
]

CLAIM_API_GROUP = "extensions.agents.x-k8s.io"
CLAIM_API_VERSION = "v1alpha1"
SANDBOX_API_GROUP = "agents.x-k8s.io"
SANDBOX_API_VERSION = "v1alpha1"
TEMPLATE_API_GROUP = "extensions.agents.x-k8s.io"
TEMPLATE_API_VERSION = "v1alpha1"
SNAPSHOT_API_GROUP = "snapshot.storage.k8s.io"
SNAPSHOT_API_VERSION = "v1"

WATCH_TIMEOUT_SECONDS = 300

# Sandbox runtime image conventions (default ``ghcr.io/earayu/treadstone-sandbox``, extends agent-infra/sandbox).
# The image creates a non-root user `gem` with this UID/GID.  All internal
# services (code-server, python-server, su - gem) use SANDBOX_HOME_DIR as
# workspace.  Persistent volumes must be mounted here with matching ownership.
SANDBOX_HOME_DIR = "/home/gem"
SANDBOX_UID = 1000
SANDBOX_GID = 1000

# Align default with deploy/sandbox-runtime/values.yaml sandboxContainerSecurityContext.
# False = compatible with the stock opaque image, which writes outside declared
# volumes during bootstrap. True would require image/layout changes first.
SANDBOX_READ_ONLY_ROOT_FILESYSTEM = False

DEFAULT_STARTUP_PROBE: dict[str, Any] = {
    "httpGet": {"path": "/v1/sandbox", "port": 8080},
    "periodSeconds": 5,
    "timeoutSeconds": 3,
    "failureThreshold": 36,
}
DEFAULT_READINESS_PROBE: dict[str, Any] = {
    "httpGet": {"path": "/v1/sandbox", "port": 8080},
    "periodSeconds": 5,
    "timeoutSeconds": 3,
    "failureThreshold": 3,
}


class WatchExpiredError(Exception):
    """Raised when the K8s API returns 410 Gone for an expired resourceVersion."""


def format_shutdown_time(dt: datetime) -> str:
    """Format a datetime as RFC3339 for K8s shutdownTime field."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sandbox_pod_security_context(*, with_pvc: bool) -> dict[str, Any]:
    """Pod-level compatible hardening; direct sandboxes keep fsGroup for PVC-backed home directories."""
    ctx: dict[str, Any] = {"seccompProfile": {"type": "RuntimeDefault"}}
    if with_pvc:
        ctx["fsGroup"] = SANDBOX_GID
        ctx["fsGroupChangePolicy"] = "OnRootMismatch"
    return ctx


def _sandbox_main_container_security_context() -> dict[str, Any]:
    """Main sandbox container: compatible baseline mirrored from Helm defaults."""
    return {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": SANDBOX_READ_ONLY_ROOT_FILESYSTEM,
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def _sandbox_init_container_security_context() -> dict[str, Any]:
    """init-home remains non-root; the incompatibility is in the main image entrypoint bootstrap."""
    return {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "runAsNonRoot": True,
        "runAsUser": SANDBOX_UID,
        "runAsGroup": SANDBOX_GID,
        "seccompProfile": {"type": "RuntimeDefault"},
    }


@runtime_checkable
class K8sClientProtocol(Protocol):
    # ── SandboxClaim (extensions.agents.x-k8s.io) ──
    async def create_sandbox_claim(
        self,
        name: str,
        template_ref: str,
        namespace: str,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
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
        replicas: int = 1,
        startup_probe: dict[str, Any] | None = None,
        readiness_probe: dict[str, Any] | None = None,
        liveness_probe: dict[str, Any] | None = None,
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        pod_labels: dict[str, str] | None = None,
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
    async def get_volume_snapshot_class(self, name: str) -> dict[str, Any] | None: ...

    async def create_volume_snapshot(
        self,
        name: str,
        namespace: str,
        source_pvc_name: str,
        snapshot_class_name: str,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    async def get_volume_snapshot(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    async def delete_volume_snapshot(self, name: str, namespace: str) -> bool: ...

    async def get_volume_snapshot_content(self, name: str) -> dict[str, Any] | None: ...

    async def delete_volume_snapshot_content(self, name: str) -> bool: ...

    async def set_volume_snapshot_content_deletion_policy(self, name: str, deletion_policy: str) -> bool: ...

    async def list_persistent_volume_claims(
        self, namespace: str, labels: dict[str, str] | None = None
    ) -> list[dict[str, Any]]: ...

    async def get_persistent_volume_claim(self, name: str, namespace: str) -> dict[str, Any] | None: ...

    async def delete_persistent_volume_claim(self, name: str, namespace: str) -> bool: ...

    async def get_persistent_volume(self, name: str) -> dict[str, Any] | None: ...

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
        self,
        name: str,
        template_ref: str,
        namespace: str,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        api = await self._get_api()
        metadata: dict[str, Any] = {"name": name, "namespace": namespace}
        if labels:
            metadata["labels"] = labels
        if annotations:
            metadata["annotations"] = annotations
        manifest: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": metadata,
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
        }
        if shutdown_time:
            manifest["spec"]["lifecycle"] = {"shutdownTime": format_shutdown_time(shutdown_time)}

        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims"
        logger.debug("K8s POST %s (name=%s)", url, name)
        async with api.call_api("POST", base=url, version="", json=manifest) as resp:
            return resp.json()

    async def delete_sandbox_claim(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{CLAIM_API_GROUP}/{CLAIM_API_VERSION}/namespaces/{namespace}/sandboxclaims/{name}"
        logger.debug("K8s DELETE %s", url)
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
        replicas: int = 1,
        startup_probe: dict[str, Any] | None = None,
        readiness_probe: dict[str, Any] | None = None,
        liveness_probe: dict[str, Any] | None = None,
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        pod_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        api = await self._get_api()
        container: dict[str, Any] = {
            "name": "sandbox",
            "image": image,
            "ports": [{"containerPort": container_port}],
            "resources": resources,
        }
        _apply_container_probes(
            container,
            startup_probe=startup_probe,
            readiness_probe=readiness_probe,
            liveness_probe=liveness_probe,
        )
        container["securityContext"] = _sandbox_main_container_security_context()

        pod_spec: dict[str, Any] = {
            "automountServiceAccountToken": False,
            "containers": [container],
            "restartPolicy": "OnFailure",
            "securityContext": _sandbox_pod_security_context(with_pvc=bool(volume_claim_templates)),
        }

        if volume_claim_templates:
            vol_names = [vct["metadata"]["name"] for vct in volume_claim_templates]
            container["volumeMounts"] = [{"name": n, "mountPath": SANDBOX_HOME_DIR} for n in vol_names]

            # On first boot the PVC shadows the image's home dir.  Seed the
            # volume with the image-layer skeleton (dotfiles from useradd -m,
            # etc.) so the main container's entrypoint can layer runtime state
            # on top.  A sentinel file tracks whether seeding has happened —
            # `ls -A` empty-checks break on ext4 volumes that ship lost+found.
            # init-home stays non-root and avoids chown; the main opaque image
            # still boots as root to create its runtime user/group.
            _sentinel = "/mnt/home/.treadstone-home-initialized"
            init_script = (
                f"if [ ! -f {_sentinel} ]; then "
                f"cp -a {SANDBOX_HOME_DIR}/. /mnt/home/ 2>/dev/null || true; "
                f"touch {_sentinel}; "
                f"fi"
            )
            pod_spec["initContainers"] = [
                {
                    "name": "init-home",
                    "image": image,
                    "command": ["sh", "-c", init_script],
                    "volumeMounts": [{"name": n, "mountPath": "/mnt/home"} for n in vol_names],
                    "securityContext": _sandbox_init_container_security_context(),
                }
            ]

        cr_metadata: dict[str, Any] = {"name": name, "namespace": namespace}
        if labels:
            cr_metadata["labels"] = labels
        if annotations:
            cr_metadata["annotations"] = annotations

        pod_template: dict[str, Any] = {"spec": pod_spec}
        if pod_labels:
            pod_template["metadata"] = {"labels": pod_labels}

        manifest: dict[str, Any] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
            "kind": "Sandbox",
            "metadata": cr_metadata,
            "spec": {
                "replicas": replicas,
                "podTemplate": pod_template,
            },
        }
        if volume_claim_templates:
            manifest["spec"]["volumeClaimTemplates"] = volume_claim_templates
        if shutdown_time:
            manifest["spec"]["shutdownTime"] = format_shutdown_time(shutdown_time)

        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes"
        logger.debug("K8s POST %s (name=%s, direct=true)", url, name)
        async with api.call_api("POST", base=url, version="", json=manifest) as resp:
            return resp.json()

    async def delete_sandbox(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}/namespaces/{namespace}/sandboxes/{name}"
        logger.debug("K8s DELETE %s", url)
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

        logger.debug("Starting K8s Watch on %s (rv=%s)", url, resource_version or "<latest>")
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
        logger.debug("K8s PATCH %s (replicas=%d)", url, replicas)
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

    async def get_volume_snapshot_class(self, name: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/volumesnapshotclasses/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    async def create_volume_snapshot(
        self,
        name: str,
        namespace: str,
        source_pvc_name: str,
        snapshot_class_name: str,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        api = await self._get_api()
        metadata: dict[str, Any] = {"name": name, "namespace": namespace}
        if labels:
            metadata["labels"] = labels
        if annotations:
            metadata["annotations"] = annotations
        manifest: dict[str, Any] = {
            "apiVersion": f"{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}",
            "kind": "VolumeSnapshot",
            "metadata": metadata,
            "spec": {
                "volumeSnapshotClassName": snapshot_class_name,
                "source": {"persistentVolumeClaimName": source_pvc_name},
            },
        }
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/namespaces/{namespace}/volumesnapshots"
        async with api.call_api("POST", base=url, version="", json=manifest) as resp:
            return resp.json()

    async def get_volume_snapshot(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/namespaces/{namespace}/volumesnapshots/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    async def delete_volume_snapshot(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/namespaces/{namespace}/volumesnapshots/{name}"
        async with api.call_api("DELETE", base=url, version="") as resp:
            return resp.status_code < 400

    async def get_volume_snapshot_content(self, name: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/volumesnapshotcontents/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    async def delete_volume_snapshot_content(self, name: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/volumesnapshotcontents/{name}"
        async with api.call_api("DELETE", base=url, version="") as resp:
            return resp.status_code < 400

    async def set_volume_snapshot_content_deletion_policy(self, name: str, deletion_policy: str) -> bool:
        api = await self._get_api()
        url = f"/apis/{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}/volumesnapshotcontents/{name}"
        body = {"spec": {"deletionPolicy": deletion_policy}}
        async with api.call_api(
            "PATCH",
            base=url,
            version="",
            json=body,
            headers={"Content-Type": "application/merge-patch+json"},
        ) as resp:
            return resp.status_code < 400

    async def list_persistent_volume_claims(
        self, namespace: str, labels: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        api = await self._get_api()
        url = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims"
        params: dict[str, str] = {}
        if labels:
            params["labelSelector"] = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        async with api.call_api("GET", base=url, version="", params=params or None) as resp:
            return resp.json().get("items", [])

    async def get_persistent_volume_claim(self, name: str, namespace: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}"
        try:
            async with api.call_api("GET", base=url, version="") as resp:
                return resp.json()
        except Exception:
            return None

    async def delete_persistent_volume_claim(self, name: str, namespace: str) -> bool:
        api = await self._get_api()
        url = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}"
        async with api.call_api("DELETE", base=url, version="") as resp:
            return resp.status_code < 400

    async def get_persistent_volume(self, name: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/api/v1/persistentvolumes/{name}"
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


ANNOTATION_ALLOWED_STORAGE_SIZES = "treadstone-ai.dev/allowed-storage-sizes"

# Treadstone-managed label / annotation keys written to every SandboxClaim and Sandbox CR.
LABEL_SANDBOX_ID = "treadstone-ai.dev/sandbox-id"
LABEL_OWNER_ID = "treadstone-ai.dev/owner-id"
LABEL_TEMPLATE = "treadstone-ai.dev/template"
LABEL_PROVISION_MODE = "treadstone-ai.dev/provision-mode"
LABEL_WORKLOAD = "treadstone-ai.dev/workload"
LABEL_STORAGE_ROLE = "treadstone-ai.dev/storage-role"
WORKLOAD_SANDBOX = "sandbox"
PROVISION_MODE_CLAIM = "claim"
PROVISION_MODE_DIRECT = "direct"
STORAGE_ROLE_WORKSPACE = "workspace"
ANNOTATION_SANDBOX_NAME = "treadstone-ai.dev/sandbox-name"
ANNOTATION_CREATED_AT = "treadstone-ai.dev/created-at"


def _parse_sandbox_template(template: dict) -> dict:
    containers = template.get("spec", {}).get("podTemplate", {}).get("spec", {}).get("containers", [])
    image = ""
    resource_spec: dict[str, str] = {}
    resource_limits: dict[str, str] = {}
    startup_probe: dict[str, Any] | None = None
    readiness_probe: dict[str, Any] | None = None
    liveness_probe: dict[str, Any] | None = None
    if containers:
        image = containers[0].get("image", "")
        resources = containers[0].get("resources", {})
        requests = resources.get("requests", {})
        resource_spec = {"cpu": requests.get("cpu", ""), "memory": requests.get("memory", "")}
        limits = resources.get("limits", {})
        resource_limits = {"cpu": limits.get("cpu", ""), "memory": limits.get("memory", "")}
        startup_probe = _copy_probe(containers[0].get("startupProbe"))
        readiness_probe = _copy_probe(containers[0].get("readinessProbe"))
        liveness_probe = _copy_probe(containers[0].get("livenessProbe"))
    annotations = template.get("metadata", {}).get("annotations", {})
    raw_sizes = annotations.get(ANNOTATION_ALLOWED_STORAGE_SIZES, "")
    allowed_storage_sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()] if raw_sizes else []
    return {
        "name": template["metadata"]["name"],
        "display_name": annotations.get("display-name", template["metadata"]["name"]),
        "description": annotations.get("description", ""),
        "image": image,
        "resource_spec": resource_spec,
        "resource_limits": resource_limits,
        "startup_probe": startup_probe,
        "readiness_probe": readiness_probe,
        "liveness_probe": liveness_probe,
        "allowed_storage_sizes": allowed_storage_sizes,
    }


def _copy_probe(probe: dict[str, Any] | None) -> dict[str, Any] | None:
    if not probe:
        return None
    return deepcopy(probe)


def _apply_container_probes(
    container: dict[str, Any],
    *,
    startup_probe: dict[str, Any] | None = None,
    readiness_probe: dict[str, Any] | None = None,
    liveness_probe: dict[str, Any] | None = None,
) -> None:
    if startup_probe:
        container["startupProbe"] = deepcopy(startup_probe)
    if readiness_probe:
        container["readinessProbe"] = deepcopy(readiness_probe)
    if liveness_probe:
        container["livenessProbe"] = deepcopy(liveness_probe)


# ──────────────────────────────────────────────────────────────────────────────
# Fake K8s client for testing
# ──────────────────────────────────────────────────────────────────────────────


def _make_ready_condition(status: str = "False", reason: str = "DependenciesNotReady", message: str = "") -> dict:
    return {"type": "Ready", "status": status, "reason": reason, "message": message}


class FakeK8sClient:
    """In-memory stub for testing — simulates the agent-sandbox controller behavior."""

    _DEFAULT_IMAGE = "ghcr.io/earayu/treadstone-sandbox:v0.1.0"

    _DEFAULT_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "name": "aio-sandbox-tiny",
            "display_name": "AIO Sandbox Tiny",
            "description": "Lightweight sandbox for code execution and scripting",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "250m", "memory": "1Gi"},
            "resource_limits": {"cpu": "250m", "memory": "1Gi"},
            "startup_probe": deepcopy(DEFAULT_STARTUP_PROBE),
            "readiness_probe": deepcopy(DEFAULT_READINESS_PROBE),
            "liveness_probe": None,
            "allowed_storage_sizes": ["5Gi", "10Gi", "20Gi"],
        },
        {
            "name": "aio-sandbox-small",
            "display_name": "AIO Sandbox Small",
            "description": "Small sandbox for simple development tasks",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "500m", "memory": "2Gi"},
            "resource_limits": {"cpu": "500m", "memory": "2Gi"},
            "startup_probe": deepcopy(DEFAULT_STARTUP_PROBE),
            "readiness_probe": deepcopy(DEFAULT_READINESS_PROBE),
            "liveness_probe": None,
            "allowed_storage_sizes": ["5Gi", "10Gi", "20Gi"],
        },
        {
            "name": "aio-sandbox-medium",
            "display_name": "AIO Sandbox Medium",
            "description": "General-purpose development environment",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "1", "memory": "4Gi"},
            "resource_limits": {"cpu": "1", "memory": "4Gi"},
            "startup_probe": deepcopy(DEFAULT_STARTUP_PROBE),
            "readiness_probe": deepcopy(DEFAULT_READINESS_PROBE),
            "liveness_probe": None,
            "allowed_storage_sizes": ["5Gi", "10Gi", "20Gi"],
        },
        {
            "name": "aio-sandbox-large",
            "display_name": "AIO Sandbox Large",
            "description": "Full-featured sandbox with browser automation",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "2", "memory": "8Gi"},
            "resource_limits": {"cpu": "2", "memory": "8Gi"},
            "startup_probe": deepcopy(DEFAULT_STARTUP_PROBE),
            "readiness_probe": deepcopy(DEFAULT_READINESS_PROBE),
            "liveness_probe": None,
            "allowed_storage_sizes": ["5Gi", "10Gi", "20Gi"],
        },
        {
            "name": "aio-sandbox-xlarge",
            "display_name": "AIO Sandbox XLarge",
            "description": "Heavy workloads with maximum resources",
            "image": _DEFAULT_IMAGE,
            "resource_spec": {"cpu": "4", "memory": "16Gi"},
            "resource_limits": {"cpu": "4", "memory": "16Gi"},
            "startup_probe": deepcopy(DEFAULT_STARTUP_PROBE),
            "readiness_probe": deepcopy(DEFAULT_READINESS_PROBE),
            "liveness_probe": None,
            "allowed_storage_sizes": ["5Gi", "10Gi", "20Gi"],
        },
    )

    def __init__(self) -> None:
        self._templates: list[dict[str, Any]] = deepcopy(list(self._DEFAULT_TEMPLATES))
        self._claims: dict[str, dict[str, Any]] = {}
        self._sandboxes: dict[str, dict[str, Any]] = {}
        self._pvcs: dict[str, dict[str, Any]] = {}
        self._pvs: dict[str, dict[str, Any]] = {}
        self._volume_snapshots: dict[str, dict[str, Any]] = {}
        self._volume_snapshot_contents: dict[str, dict[str, Any]] = {}
        self._storage_classes: dict[str, dict[str, Any]] = {
            "treadstone-workspace": {
                "apiVersion": "storage.k8s.io/v1",
                "kind": "StorageClass",
                "metadata": {"name": "treadstone-workspace"},
                "provisioner": "test.fake.provisioner",
            }
        }
        self._volume_snapshot_classes: dict[str, dict[str, Any]] = {
            "treadstone-workspace-snapshot": {
                "apiVersion": f"{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}",
                "kind": "VolumeSnapshotClass",
                "metadata": {"name": "treadstone-workspace-snapshot"},
                "driver": "test.fake.provisioner",
                "deletionPolicy": "Retain",
            }
        }
        self._watch_queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def create_sandbox_claim(
        self,
        name: str,
        template_ref: str,
        namespace: str,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        sandbox_name = name
        claim_metadata: dict[str, Any] = {"name": name, "namespace": namespace, "resourceVersion": "1"}
        if labels:
            claim_metadata["labels"] = labels
        if annotations:
            claim_metadata["annotations"] = annotations
        claim: dict[str, Any] = {
            "apiVersion": f"{CLAIM_API_GROUP}/{CLAIM_API_VERSION}",
            "kind": "SandboxClaim",
            "metadata": claim_metadata,
            "spec": {"sandboxTemplateRef": {"name": template_ref}},
            "status": {"conditions": [], "sandbox": {"name": sandbox_name, "podIPs": []}},
        }
        if shutdown_time:
            claim["spec"]["lifecycle"] = {"shutdownTime": format_shutdown_time(shutdown_time)}
        self._claims[key] = claim

        template = next((item for item in self._templates if item["name"] == template_ref), None)
        container: dict[str, Any] = {
            "name": "sandbox",
            "image": template.get("image", self._DEFAULT_IMAGE) if template else self._DEFAULT_IMAGE,
            "resources": {
                "requests": deepcopy(template.get("resource_spec", {})) if template else {},
                "limits": deepcopy(template.get("resource_limits", {})) if template else {},
            },
        }
        if template is not None:
            _apply_container_probes(
                container,
                startup_probe=template.get("startup_probe"),
                readiness_probe=template.get("readiness_probe"),
                liveness_probe=template.get("liveness_probe"),
            )
        container["securityContext"] = _sandbox_main_container_security_context()

        self._sandboxes[key] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
            "kind": "Sandbox",
            "metadata": {"name": sandbox_name, "namespace": namespace, "resourceVersion": "1"},
            "spec": {
                "replicas": 1,
                "podTemplate": {
                    "spec": {
                        "automountServiceAccountToken": False,
                        "restartPolicy": "OnFailure",
                        "securityContext": _sandbox_pod_security_context(with_pvc=False),
                        "containers": [container],
                    },
                },
            },
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
        replicas: int = 1,
        startup_probe: dict[str, Any] | None = None,
        readiness_probe: dict[str, Any] | None = None,
        liveness_probe: dict[str, Any] | None = None,
        volume_claim_templates: list[dict[str, Any]] | None = None,
        shutdown_time: datetime | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        pod_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        key = f"{namespace}/{name}"
        sb_metadata: dict[str, Any] = {"name": name, "namespace": namespace, "resourceVersion": "1"}
        if labels:
            sb_metadata["labels"] = labels
        if annotations:
            sb_metadata["annotations"] = annotations

        main: dict[str, Any] = {
            "name": "sandbox",
            "image": image,
            "resources": resources,
        }
        _apply_container_probes(
            main,
            startup_probe=startup_probe,
            readiness_probe=readiness_probe,
            liveness_probe=liveness_probe,
        )
        main["securityContext"] = _sandbox_main_container_security_context()

        pod_spec: dict[str, Any] = {
            "automountServiceAccountToken": False,
            "containers": [main],
            "restartPolicy": "OnFailure",
            "securityContext": _sandbox_pod_security_context(with_pvc=bool(volume_claim_templates)),
        }

        if volume_claim_templates:
            vol_names = [vct["metadata"]["name"] for vct in volume_claim_templates]
            main["volumeMounts"] = [{"name": n, "mountPath": SANDBOX_HOME_DIR} for n in vol_names]
            _sentinel = "/mnt/home/.treadstone-home-initialized"
            init_script = (
                f"if [ ! -f {_sentinel} ]; then "
                f"cp -a {SANDBOX_HOME_DIR}/. /mnt/home/ 2>/dev/null || true; "
                f"touch {_sentinel}; "
                f"fi"
            )
            pod_spec["initContainers"] = [
                {
                    "name": "init-home",
                    "image": image,
                    "command": ["sh", "-c", init_script],
                    "volumeMounts": [{"name": n, "mountPath": "/mnt/home"} for n in vol_names],
                    "securityContext": _sandbox_init_container_security_context(),
                }
            ]

        pod_template: dict[str, Any] = {"spec": pod_spec}
        if pod_labels:
            pod_template["metadata"] = {"labels": pod_labels}
        sandbox: dict[str, Any] = {
            "apiVersion": f"{SANDBOX_API_GROUP}/{SANDBOX_API_VERSION}",
            "kind": "Sandbox",
            "metadata": sb_metadata,
            "spec": {
                "replicas": replicas,
                "podTemplate": pod_template,
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
            self._materialize_volume_claims(namespace, name, volume_claim_templates)
        if shutdown_time:
            sandbox["spec"]["shutdownTime"] = format_shutdown_time(shutdown_time)
        self._sandboxes[key] = sandbox
        if replicas == 0:
            sandbox["status"]["conditions"] = [
                _make_ready_condition("True", "DependenciesReady", "Pod does not exist, replicas is 0")
            ]
            sandbox["status"]["replicas"] = 0
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

    async def get_volume_snapshot_class(self, name: str) -> dict[str, Any] | None:
        return self._volume_snapshot_classes.get(name)

    async def create_volume_snapshot(
        self,
        name: str,
        namespace: str,
        source_pvc_name: str,
        snapshot_class_name: str,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        pvc = await self.get_persistent_volume_claim(source_pvc_name, namespace)
        if pvc is None:
            raise KeyError(f"PVC {namespace}/{source_pvc_name} not found")

        content_name = f"vsc-{name}"
        snapshot_handle = f"snap-{name}"
        snapshot_metadata: dict[str, Any] = {"name": name, "namespace": namespace, "resourceVersion": "1"}
        if labels:
            snapshot_metadata["labels"] = labels
        if annotations:
            snapshot_metadata["annotations"] = annotations
        snapshot = {
            "apiVersion": f"{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}",
            "kind": "VolumeSnapshot",
            "metadata": snapshot_metadata,
            "spec": {
                "volumeSnapshotClassName": snapshot_class_name,
                "source": {"persistentVolumeClaimName": source_pvc_name},
            },
            "status": {
                "readyToUse": True,
                "boundVolumeSnapshotContentName": content_name,
                "restoreSize": pvc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage"),
            },
        }
        content = {
            "apiVersion": f"{SNAPSHOT_API_GROUP}/{SNAPSHOT_API_VERSION}",
            "kind": "VolumeSnapshotContent",
            "metadata": {"name": content_name, "resourceVersion": "1"},
            "spec": {
                "volumeSnapshotClassName": snapshot_class_name,
                "deletionPolicy": self._volume_snapshot_classes[snapshot_class_name]["deletionPolicy"],
                "source": {"volumeHandle": pvc.get("spec", {}).get("volumeName", "")},
                "volumeSnapshotRef": {"name": name, "namespace": namespace},
            },
            "status": {"readyToUse": True, "snapshotHandle": snapshot_handle},
        }
        self._volume_snapshots[f"{namespace}/{name}"] = snapshot
        self._volume_snapshot_contents[content_name] = content
        return snapshot

    async def get_volume_snapshot(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._volume_snapshots.get(f"{namespace}/{name}")

    async def delete_volume_snapshot(self, name: str, namespace: str) -> bool:
        key = f"{namespace}/{name}"
        snapshot = self._volume_snapshots.pop(key, None)
        if snapshot is None:
            return False
        content_name = snapshot.get("status", {}).get("boundVolumeSnapshotContentName")
        content = self._volume_snapshot_contents.get(content_name)
        if content and content.get("spec", {}).get("deletionPolicy") == "Delete":
            self._volume_snapshot_contents.pop(content_name, None)
        return True

    async def get_volume_snapshot_content(self, name: str) -> dict[str, Any] | None:
        return self._volume_snapshot_contents.get(name)

    async def delete_volume_snapshot_content(self, name: str) -> bool:
        return self._volume_snapshot_contents.pop(name, None) is not None

    async def set_volume_snapshot_content_deletion_policy(self, name: str, deletion_policy: str) -> bool:
        content = self._volume_snapshot_contents.get(name)
        if content is None:
            return False
        content["spec"]["deletionPolicy"] = deletion_policy
        rv = str(int(content["metadata"].get("resourceVersion", "1")) + 1)
        content["metadata"]["resourceVersion"] = rv
        return True

    async def list_persistent_volume_claims(
        self, namespace: str, labels: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        pvcs = [pvc for key, pvc in self._pvcs.items() if key.startswith(f"{namespace}/")]
        if not labels:
            return pvcs
        items: list[dict[str, Any]] = []
        for pvc in pvcs:
            pvc_labels = pvc.get("metadata", {}).get("labels", {})
            if all(pvc_labels.get(k) == v for k, v in labels.items()):
                items.append(pvc)
        return items

    async def get_persistent_volume_claim(self, name: str, namespace: str) -> dict[str, Any] | None:
        return self._pvcs.get(f"{namespace}/{name}")

    async def delete_persistent_volume_claim(self, name: str, namespace: str) -> bool:
        pvc = self._pvcs.pop(f"{namespace}/{name}", None)
        if pvc is None:
            return False
        pv_name = pvc.get("spec", {}).get("volumeName")
        if pv_name:
            self._pvs.pop(pv_name, None)
        return True

    async def get_persistent_volume(self, name: str) -> dict[str, Any] | None:
        return self._pvs.get(name)

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

    def simulate_claim_adoption(self, claim_name: str, namespace: str, adopted_sandbox_name: str) -> None:
        """Simulate warm-pool adoption where claim and Sandbox names diverge.

        The agent-sandbox v0.3.x controller can bind a SandboxClaim to an
        already-existing warm-pool Sandbox. The resulting Sandbox CR keeps the
        warm-pool-derived ``metadata.name`` and points back to the claim via an
        owner reference.
        """
        claim_key = f"{namespace}/{claim_name}"
        sandbox_key = f"{namespace}/{claim_name}"
        claim = self._claims.get(claim_key)
        sandbox = self._sandboxes.pop(sandbox_key, None)
        if claim is None or sandbox is None:
            return

        claim["status"]["sandbox"] = {"name": adopted_sandbox_name, "podIPs": []}

        sandbox["metadata"]["name"] = adopted_sandbox_name
        sandbox["metadata"]["ownerReferences"] = [{"kind": "SandboxClaim", "name": claim_name, "controller": True}]
        sandbox["status"]["service"] = adopted_sandbox_name
        sandbox["status"]["serviceFQDN"] = f"{adopted_sandbox_name}.{namespace}.svc.cluster.local"
        rv = str(int(sandbox["metadata"].get("resourceVersion", "1")) + 1)
        sandbox["metadata"]["resourceVersion"] = rv
        self._sandboxes[f"{namespace}/{adopted_sandbox_name}"] = sandbox

    def remove_storage_class(self, name: str) -> None:
        self._storage_classes.pop(name, None)

    def remove_volume_snapshot_class(self, name: str) -> None:
        self._volume_snapshot_classes.pop(name, None)

    def _materialize_volume_claims(
        self,
        namespace: str,
        sandbox_name: str,
        volume_claim_templates: list[dict[str, Any]],
    ) -> None:
        for index, template in enumerate(volume_claim_templates, start=1):
            claim_name = f"{sandbox_name}-{template['metadata']['name']}"
            pv_name = f"pv-{sandbox_name}-{index}"
            labels = deepcopy(template.get("metadata", {}).get("labels", {}))
            annotations = deepcopy(template.get("metadata", {}).get("annotations", {}))
            storage_request = template.get("spec", {}).get("resources", {}).get("requests", {}).get("storage")
            pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": claim_name,
                    "namespace": namespace,
                    "resourceVersion": "1",
                    "labels": labels,
                    "annotations": annotations,
                },
                "spec": {
                    "accessModes": deepcopy(template.get("spec", {}).get("accessModes", [])),
                    "resources": {"requests": {"storage": storage_request}},
                    "storageClassName": template.get("spec", {}).get("storageClassName"),
                    "volumeName": pv_name,
                    "dataSource": deepcopy(template.get("spec", {}).get("dataSource")),
                },
                "status": {"phase": "Bound"},
            }
            pv = {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "metadata": {
                    "name": pv_name,
                    "resourceVersion": "1",
                    "labels": deepcopy(labels),
                },
                "spec": {
                    "capacity": {"storage": storage_request},
                    "storageClassName": template.get("spec", {}).get("storageClassName"),
                    "csi": {"volumeHandle": f"disk-{sandbox_name}-{index}"},
                    "nodeAffinity": {
                        "required": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "topology.diskplugin.csi.alibabacloud.com/zone",
                                            "operator": "In",
                                            "values": ["fake-zone-a"],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                },
                "status": {"phase": "Bound"},
            }
            self._pvcs[f"{namespace}/{claim_name}"] = pvc
            self._pvs[pv_name] = pv


# ──────────────────────────────────────────────────────────────────────────────
# Singleton management
# ──────────────────────────────────────────────────────────────────────────────

_k8s_client: K8sClientProtocol | None = None


def get_k8s_client() -> K8sClientProtocol:
    global _k8s_client
    if _k8s_client is None:
        logger.debug("Using Kr8sClient")
        _k8s_client = Kr8sClient()
    return _k8s_client


def set_k8s_client(client: K8sClientProtocol) -> None:
    global _k8s_client
    _k8s_client = client
