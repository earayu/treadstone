"""Unit tests for K8s clients — fake flow behavior and real client request wiring."""

from datetime import UTC, datetime, timedelta

import treadstone.infra.services.k8s_client as k8s_client_module
from treadstone.services.k8s_client import (
    SANDBOX_HOME_DIR,
    WATCH_TIMEOUT_SECONDS,
    FakeK8sClient,
    Kr8sClient,
    _parse_sandbox_template,
    _sandbox_init_container_security_context,
    _sandbox_main_container_security_context,
    _sandbox_pod_security_context,
    format_shutdown_time,
)

EXPECTED_MAIN_SECURITY_CONTEXT = {
    "allowPrivilegeEscalation": False,
    "readOnlyRootFilesystem": False,
    "seccompProfile": {"type": "RuntimeDefault"},
}
EXPECTED_INIT_SECURITY_CONTEXT = {
    "allowPrivilegeEscalation": False,
    "capabilities": {"drop": ["ALL"]},
    "runAsNonRoot": True,
    "runAsUser": 1000,
    "runAsGroup": 1000,
    "seccompProfile": {"type": "RuntimeDefault"},
}


class _EmptyStreamResponse:
    def __init__(self, payload: dict | None = None):
        self._payload = payload or {}

    async def aiter_lines(self):
        for line in ():
            yield line

    def json(self):
        return self._payload


class _RecordedCall:
    def __init__(self, recorder: list[dict], payload: dict, response_payload: dict | None = None):
        self._recorder = recorder
        self._payload = payload
        self._response_payload = response_payload

    async def __aenter__(self):
        self._recorder.append(self._payload)
        return _EmptyStreamResponse(self._response_payload)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _RecordingAPI:
    def __init__(self):
        self.calls: list[dict] = []

    def call_api(self, method: str, **kwargs):
        response_payload = None
        if method == "GET" and kwargs.get("base", "").startswith("/apis/storage.k8s.io/v1/storageclasses/"):
            name = kwargs["base"].rsplit("/", 1)[-1]
            response_payload = {"metadata": {"name": name}}
        return _RecordedCall(self.calls, {"method": method, **kwargs}, response_payload=response_payload)


async def test_list_sandbox_templates():
    client = FakeK8sClient()
    templates = await client.list_sandbox_templates("treadstone-local")
    assert len(templates) == 5
    names = [t["name"] for t in templates]
    assert "aio-sandbox-tiny" in names
    assert "aio-sandbox-xlarge" in names
    assert templates[0]["startup_probe"]["httpGet"]["path"] == "/v1/sandbox"
    assert templates[0]["readiness_probe"]["httpGet"]["path"] == "/v1/sandbox"
    assert templates[0]["liveness_probe"] is None


def test_parse_sandbox_template_extracts_probes():
    parsed = _parse_sandbox_template(
        {
            "metadata": {
                "name": "aio-sandbox-tiny",
                "annotations": {
                    "display-name": "AIO Sandbox Tiny",
                    "description": "Lightweight sandbox for code execution and scripting",
                    "treadstone-ai.dev/allowed-storage-sizes": "5Gi,10Gi",
                },
            },
            "spec": {
                "podTemplate": {
                    "spec": {
                        "containers": [
                            {
                                "image": "ghcr.io/agent-infra/sandbox:1.0.0.152",
                                "resources": {
                                    "requests": {"cpu": "250m", "memory": "1Gi"},
                                    "limits": {"cpu": "250m", "memory": "1Gi"},
                                },
                                "startupProbe": {
                                    "httpGet": {"path": "/v1/sandbox", "port": 8080},
                                    "periodSeconds": 5,
                                    "timeoutSeconds": 3,
                                    "failureThreshold": 36,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/v1/sandbox", "port": 8080},
                                    "periodSeconds": 5,
                                    "timeoutSeconds": 3,
                                    "failureThreshold": 3,
                                },
                            }
                        ]
                    }
                }
            },
        }
    )

    assert parsed["startup_probe"]["httpGet"]["path"] == "/v1/sandbox"
    assert parsed["readiness_probe"]["failureThreshold"] == 3
    assert parsed["liveness_probe"] is None


async def test_create_and_get_sandbox_claim():
    client = FakeK8sClient()
    claim = await client.create_sandbox_claim("my-sb", "aio-sandbox-tiny", "treadstone-local")
    assert claim["kind"] == "SandboxClaim"
    assert claim["spec"]["sandboxTemplateRef"]["name"] == "aio-sandbox-tiny"
    assert claim["status"]["sandbox"]["name"] == "my-sb"

    fetched = await client.get_sandbox_claim("my-sb", "treadstone-local")
    assert fetched is not None


async def test_simulate_claim_adoption_rekeys_sandbox_and_sets_owner_reference():
    client = FakeK8sClient()
    await client.create_sandbox_claim("my-sb", "aio-sandbox-tiny", "treadstone-local")

    client.simulate_claim_adoption("my-sb", "treadstone-local", "aio-sandbox-tiny-pool-7dpvv")

    claim = await client.get_sandbox_claim("my-sb", "treadstone-local")
    sandbox = await client.get_sandbox("aio-sandbox-tiny-pool-7dpvv", "treadstone-local")

    assert claim["status"]["sandbox"]["name"] == "aio-sandbox-tiny-pool-7dpvv"
    assert sandbox["metadata"]["name"] == "aio-sandbox-tiny-pool-7dpvv"
    assert sandbox["metadata"]["ownerReferences"][0]["kind"] == "SandboxClaim"
    assert sandbox["metadata"]["ownerReferences"][0]["name"] == "my-sb"


async def test_create_claim_also_creates_sandbox():
    client = FakeK8sClient()
    await client.create_sandbox_claim("my-sb", "aio-sandbox-tiny", "treadstone-local")
    sb = await client.get_sandbox("my-sb", "treadstone-local")
    assert sb is not None
    assert sb["kind"] == "Sandbox"
    ps = sb["spec"]["podTemplate"]["spec"]
    assert ps["automountServiceAccountToken"] is False
    assert ps["enableServiceLinks"] is False
    assert ps["securityContext"] == _sandbox_pod_security_context(with_pvc=False)
    assert ps["containers"][0]["securityContext"] == _sandbox_main_container_security_context()
    assert ps["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}
    assert ps["containers"][0]["securityContext"] == EXPECTED_MAIN_SECURITY_CONTEXT
    assert sb["status"]["serviceFQDN"] == "my-sb.treadstone-local.svc.cluster.local"


async def test_delete_sandbox_claim_removes_sandbox():
    client = FakeK8sClient()
    await client.create_sandbox_claim("del-sb", "aio-sandbox-tiny", "treadstone-local")
    result = await client.delete_sandbox_claim("del-sb", "treadstone-local")
    assert result is True
    assert await client.get_sandbox_claim("del-sb", "treadstone-local") is None
    assert await client.get_sandbox("del-sb", "treadstone-local") is None


async def test_list_sandboxes():
    client = FakeK8sClient()
    await client.create_sandbox_claim("sb-1", "aio-sandbox-tiny", "treadstone-local")
    await client.create_sandbox_claim("sb-2", "aio-sandbox-tiny", "treadstone-local")
    sbs = await client.list_sandboxes("treadstone-local")
    assert len(sbs) == 2


async def test_scale_sandbox_stop_and_start():
    client = FakeK8sClient()
    await client.create_sandbox_claim("sb-scale", "aio-sandbox-tiny", "treadstone-local")
    client.simulate_sandbox_ready("sb-scale", "treadstone-local")

    await client.scale_sandbox("sb-scale", "treadstone-local", 0)
    sb = await client.get_sandbox("sb-scale", "treadstone-local")
    assert sb["spec"]["replicas"] == 0
    assert sb["status"]["replicas"] == 0

    await client.scale_sandbox("sb-scale", "treadstone-local", 1)
    sb = await client.get_sandbox("sb-scale", "treadstone-local")
    assert sb["spec"]["replicas"] == 1


async def test_create_with_shutdown_time():
    client = FakeK8sClient()
    dt = datetime.now(UTC) + timedelta(hours=1)
    claim = await client.create_sandbox_claim("sb-expiry", "aio-sandbox-tiny", "treadstone-local", shutdown_time=dt)
    assert "lifecycle" in claim["spec"]
    assert claim["spec"]["lifecycle"]["shutdownTime"] == format_shutdown_time(dt)


def test_format_shutdown_time():
    dt = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    assert format_shutdown_time(dt) == "2026-03-19T12:00:00Z"


async def test_simulate_sandbox_ready():
    client = FakeK8sClient()
    await client.create_sandbox_claim("sb-ready", "aio-sandbox-tiny", "treadstone-local")
    sb = await client.get_sandbox("sb-ready", "treadstone-local")
    ready_cond = [c for c in sb["status"]["conditions"] if c["type"] == "Ready"][0]
    assert ready_cond["status"] == "False"

    client.simulate_sandbox_ready("sb-ready", "treadstone-local")
    sb = await client.get_sandbox("sb-ready", "treadstone-local")
    ready_cond = [c for c in sb["status"]["conditions"] if c["type"] == "Ready"][0]
    assert ready_cond["status"] == "True"


# ── Direct Sandbox creation (persist=true path) ──


async def test_create_sandbox_direct():
    client = FakeK8sClient()
    sb = await client.create_sandbox(
        name="direct-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
        startup_probe={
            "httpGet": {"path": "/v1/sandbox", "port": 8080},
            "periodSeconds": 5,
            "timeoutSeconds": 3,
            "failureThreshold": 36,
        },
        readiness_probe={
            "httpGet": {"path": "/v1/sandbox", "port": 8080},
            "periodSeconds": 5,
            "timeoutSeconds": 3,
            "failureThreshold": 3,
        },
        volume_claim_templates=[
            {
                "metadata": {"name": "workspace"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": "treadstone-workspace",
                    "resources": {"requests": {"storage": "10Gi"}},
                },
            }
        ],
    )
    assert sb["kind"] == "Sandbox"
    assert sb["metadata"]["name"] == "direct-sb"
    assert sb["spec"]["volumeClaimTemplates"] is not None
    assert sb["status"]["serviceFQDN"] == "direct-sb.treadstone-local.svc.cluster.local"
    container = sb["spec"]["podTemplate"]["spec"]["containers"][0]
    assert container["startupProbe"]["httpGet"]["path"] == "/v1/sandbox"
    assert container["readinessProbe"]["httpGet"]["path"] == "/v1/sandbox"
    assert "livenessProbe" not in container

    fetched = await client.get_sandbox("direct-sb", "treadstone-local")
    assert fetched is not None


async def test_create_sandbox_direct_without_storage():
    client = FakeK8sClient()
    sb = await client.create_sandbox(
        name="no-storage-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )
    assert sb["kind"] == "Sandbox"
    assert "volumeClaimTemplates" not in sb["spec"]
    ps = sb["spec"]["podTemplate"]["spec"]
    assert ps["automountServiceAccountToken"] is False
    assert ps["enableServiceLinks"] is False
    assert ps["securityContext"] == _sandbox_pod_security_context(with_pvc=False)
    assert ps["containers"][0]["securityContext"] == _sandbox_main_container_security_context()


async def test_get_storage_class():
    client = FakeK8sClient()
    storage_class = await client.get_storage_class("treadstone-workspace")
    assert storage_class is not None
    assert storage_class["metadata"]["name"] == "treadstone-workspace"


async def test_delete_sandbox_direct():
    client = FakeK8sClient()
    await client.create_sandbox(
        name="del-direct",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )
    result = await client.delete_sandbox("del-direct", "treadstone-local")
    assert result is True
    assert await client.get_sandbox("del-direct", "treadstone-local") is None


async def test_direct_sandbox_in_list():
    client = FakeK8sClient()
    await client.create_sandbox_claim("claim-sb", "aio-sandbox-tiny", "treadstone-local")
    await client.create_sandbox(
        name="direct-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "1", "memory": "2Gi"}},
    )
    sbs = await client.list_sandboxes("treadstone-local")
    assert len(sbs) == 2


async def test_watch_sandboxes_passes_query_params_separately():
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    events = [event async for event in client.watch_sandboxes("treadstone-prod", resource_version="123")]

    assert events == []
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["method"] == "GET"
    assert call["base"] == "/apis/agents.x-k8s.io/v1alpha1/namespaces/treadstone-prod/sandboxes"
    assert call["version"] == ""
    assert call["stream"] is True
    assert call["params"] == {
        "watch": "true",
        "timeoutSeconds": str(WATCH_TIMEOUT_SECONDS),
        "resourceVersion": "123",
    }


async def test_get_storage_class_requests_expected_endpoint():
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    storage_class = await client.get_storage_class("treadstone-workspace")

    assert storage_class == {"metadata": {"name": "treadstone-workspace"}}
    call = api.calls[0]
    assert call["method"] == "GET"
    assert call["base"] == "/apis/storage.k8s.io/v1/storageclasses/treadstone-workspace"
    assert call["version"] == ""


async def test_create_sandbox_requests_expected_manifest_with_probes():
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    await client.create_sandbox(
        name="direct-sb",
        namespace="treadstone-prod",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "1Gi"}},
        startup_probe={
            "httpGet": {"path": "/v1/sandbox", "port": 8080},
            "periodSeconds": 5,
            "timeoutSeconds": 3,
            "failureThreshold": 36,
        },
        readiness_probe={
            "httpGet": {"path": "/v1/sandbox", "port": 8080},
            "periodSeconds": 5,
            "timeoutSeconds": 3,
            "failureThreshold": 3,
        },
        liveness_probe=None,
    )

    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["method"] == "POST"
    assert call["base"] == "/apis/agents.x-k8s.io/v1alpha1/namespaces/treadstone-prod/sandboxes"
    pod_spec = call["json"]["spec"]["podTemplate"]["spec"]
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["enableServiceLinks"] is False
    assert pod_spec["securityContext"] == _sandbox_pod_security_context(with_pvc=False)
    assert pod_spec["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}
    container = pod_spec["containers"][0]
    assert container["securityContext"] == _sandbox_main_container_security_context()
    assert container["securityContext"] == EXPECTED_MAIN_SECURITY_CONTEXT
    assert "runAsNonRoot" not in container["securityContext"]
    assert "runAsUser" not in container["securityContext"]
    assert "runAsGroup" not in container["securityContext"]
    assert container["startupProbe"]["httpGet"]["path"] == "/v1/sandbox"
    assert container["readinessProbe"]["failureThreshold"] == 3
    assert "livenessProbe" not in container


async def test_create_sandbox_uses_configured_sandbox_service_account(monkeypatch):
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]
    monkeypatch.setattr(k8s_client_module.settings, "sandbox_service_account_name", "sandbox-runtime")

    await client.create_sandbox(
        name="direct-sb",
        namespace="treadstone-prod",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "1Gi"}},
    )

    pod_spec = api.calls[0]["json"]["spec"]["podTemplate"]["spec"]
    assert pod_spec["serviceAccountName"] == "sandbox-runtime"


# ── Kr8sClient manifest structure (persist=true) ──


async def test_create_sandbox_manifest_mounts_pvc_at_home_dir():
    """Persistent sandbox must mount PVC at SANDBOX_HOME_DIR with correct
    securityContext and an initContainer that seeds the volume on first boot."""
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    image = "ghcr.io/agent-infra/sandbox:1.0.0.152"
    await client.create_sandbox(
        name="persist-sb",
        namespace="treadstone-local",
        image=image,
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
        volume_claim_templates=[
            {
                "metadata": {"name": "workspace"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": "treadstone-workspace",
                    "resources": {"requests": {"storage": "10Gi"}},
                },
            }
        ],
    )

    assert len(api.calls) == 1
    manifest = api.calls[0]["json"]
    pod_spec = manifest["spec"]["podTemplate"]["spec"]
    assert pod_spec["automountServiceAccountToken"] is False

    # Main container mounts PVC at the image's home directory
    main = pod_spec["containers"][0]
    assert main["volumeMounts"] == [{"name": "workspace", "mountPath": SANDBOX_HOME_DIR}]
    assert main["securityContext"] == _sandbox_main_container_security_context()
    assert main["securityContext"] == EXPECTED_MAIN_SECURITY_CONTEXT
    assert "runAsNonRoot" not in main["securityContext"]
    assert "runAsUser" not in main["securityContext"]
    assert "runAsGroup" not in main["securityContext"]

    assert pod_spec["securityContext"] == _sandbox_pod_security_context(with_pvc=True)
    assert pod_spec["securityContext"] == {
        "seccompProfile": {"type": "RuntimeDefault"},
        "fsGroup": 1000,
        "fsGroupChangePolicy": "OnRootMismatch",
    }

    # initContainer seeds home contents on first boot using a sentinel file
    # (not ls -A empty-check, which breaks on ext4 volumes with lost+found)
    init = pod_spec["initContainers"][0]
    assert init["name"] == "init-home"
    assert init["image"] == image
    assert init["securityContext"] == _sandbox_init_container_security_context()
    assert init["securityContext"] == EXPECTED_INIT_SECURITY_CONTEXT
    assert init["volumeMounts"] == [{"name": "workspace", "mountPath": "/mnt/home"}]
    script = init["command"][2]
    assert ".treadstone-home-initialized" in script
    assert "chown" not in script


async def test_create_sandbox_manifest_without_pvc_has_baseline_security_no_init():
    """Ephemeral sandbox (no PVC): compatible baseline on pod/main container; no init or PVC mounts."""
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    await client.create_sandbox(
        name="ephemeral-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )

    manifest = api.calls[0]["json"]
    pod_spec = manifest["spec"]["podTemplate"]["spec"]

    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"] == _sandbox_pod_security_context(with_pvc=False)
    assert pod_spec["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}
    assert pod_spec["containers"][0]["securityContext"] == _sandbox_main_container_security_context()
    assert pod_spec["containers"][0]["securityContext"] == EXPECTED_MAIN_SECURITY_CONTEXT
    assert "initContainers" not in pod_spec
    assert "volumeMounts" not in pod_spec["containers"][0]
    assert "volumeClaimTemplates" not in manifest["spec"]


# ── Direct sandbox pod labels ──


async def test_create_sandbox_preserves_explicit_pod_labels() -> None:
    client = FakeK8sClient()
    sb = await client.create_sandbox(
        name="labeled-sb",
        namespace="treadstone-prod",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "500m", "memory": "2Gi"}},
        pod_labels={
            "treadstone-ai.dev/sandbox-id": "sb123",
            "treadstone-ai.dev/workload": "sandbox",
            "treadstone-ai.dev/provision-mode": "direct",
        },
    )

    pod_template = sb["spec"]["podTemplate"]
    labels = pod_template["metadata"]["labels"]
    assert labels["treadstone-ai.dev/sandbox-id"] == "sb123"
    assert labels["treadstone-ai.dev/workload"] == "sandbox"
    assert labels["treadstone-ai.dev/provision-mode"] == "direct"


async def test_create_sandbox_has_no_extra_labels_without_pod_labels() -> None:
    client = FakeK8sClient()
    sb = await client.create_sandbox(
        name="plain-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )

    pod_spec = sb["spec"]["podTemplate"]["spec"]
    assert "tolerations" not in pod_spec
    assert "metadata" not in sb["spec"]["podTemplate"]


async def test_kr8s_client_preserves_explicit_pod_labels() -> None:
    api = _RecordingAPI()
    client = Kr8sClient()
    client._api = api  # type: ignore[attr-defined]

    await client.create_sandbox(
        name="kr8s-labeled-sb",
        namespace="treadstone-prod",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "500m"}},
        pod_labels={
            "treadstone-ai.dev/workload": "sandbox",
            "treadstone-ai.dev/provision-mode": "direct",
        },
    )

    manifest = api.calls[0]["json"]
    pod_spec = manifest["spec"]["podTemplate"]["spec"]
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"] == _sandbox_pod_security_context(with_pvc=False)
    assert pod_spec["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}
    assert "tolerations" not in pod_spec
    labels = manifest["spec"]["podTemplate"]["metadata"]["labels"]
    assert labels["treadstone-ai.dev/workload"] == "sandbox"
    assert labels["treadstone-ai.dev/provision-mode"] == "direct"
