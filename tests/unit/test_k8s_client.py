"""Unit tests for K8s clients — fake flow behavior and real client request wiring."""

from datetime import UTC, datetime, timedelta

from treadstone.services.k8s_client import (
    SANDBOX_GID,
    SANDBOX_HOME_DIR,
    SANDBOX_UID,
    WATCH_TIMEOUT_SECONDS,
    FakeK8sClient,
    Kr8sClient,
    format_shutdown_time,
)


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


async def test_create_and_get_sandbox_claim():
    client = FakeK8sClient()
    claim = await client.create_sandbox_claim("my-sb", "aio-sandbox-tiny", "treadstone-local")
    assert claim["kind"] == "SandboxClaim"
    assert claim["spec"]["sandboxTemplateRef"]["name"] == "aio-sandbox-tiny"
    assert claim["status"]["sandbox"]["Name"] == "my-sb"

    fetched = await client.get_sandbox_claim("my-sb", "treadstone-local")
    assert fetched is not None


async def test_create_claim_also_creates_sandbox():
    client = FakeK8sClient()
    await client.create_sandbox_claim("my-sb", "aio-sandbox-tiny", "treadstone-local")
    sb = await client.get_sandbox("my-sb", "treadstone-local")
    assert sb is not None
    assert sb["kind"] == "Sandbox"
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
        image="ghcr.io/agent-infra/sandbox:latest",
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
    assert sb["kind"] == "Sandbox"
    assert sb["metadata"]["name"] == "direct-sb"
    assert sb["spec"]["volumeClaimTemplates"] is not None
    assert sb["status"]["serviceFQDN"] == "direct-sb.treadstone-local.svc.cluster.local"

    fetched = await client.get_sandbox("direct-sb", "treadstone-local")
    assert fetched is not None


async def test_create_sandbox_direct_without_storage():
    client = FakeK8sClient()
    sb = await client.create_sandbox(
        name="no-storage-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:latest",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )
    assert sb["kind"] == "Sandbox"
    assert "volumeClaimTemplates" not in sb["spec"]


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
        image="ghcr.io/agent-infra/sandbox:latest",
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
        image="ghcr.io/agent-infra/sandbox:latest",
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


# ── Kr8sClient manifest structure (persist=true) ──


async def test_create_sandbox_manifest_mounts_pvc_at_home_dir():
    """Persistent sandbox must mount PVC at SANDBOX_HOME_DIR with correct
    securityContext and an initContainer that seeds the volume on first boot."""
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    image = "ghcr.io/agent-infra/sandbox:latest"
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

    # Main container mounts PVC at the image's home directory
    main = pod_spec["containers"][0]
    assert main["volumeMounts"] == [{"name": "workspace", "mountPath": SANDBOX_HOME_DIR}]

    # Pod-level security context lets the gem user write to the volume
    sc = pod_spec["securityContext"]
    assert sc["fsGroup"] == SANDBOX_GID
    assert sc["fsGroupChangePolicy"] == "OnRootMismatch"

    # initContainer seeds home contents on first boot using a sentinel file
    # (not ls -A empty-check, which breaks on ext4 volumes with lost+found)
    init = pod_spec["initContainers"][0]
    assert init["name"] == "init-home"
    assert init["image"] == image
    assert init["securityContext"] == {"runAsUser": 0}
    assert init["volumeMounts"] == [{"name": "workspace", "mountPath": "/mnt/home"}]
    script = init["command"][2]
    assert ".treadstone-home-initialized" in script
    assert f"chown {SANDBOX_UID}:{SANDBOX_GID}" in script


async def test_create_sandbox_manifest_without_pvc_has_no_init_or_security_context():
    """Ephemeral sandbox (no PVC) must not add securityContext or initContainers."""
    client = Kr8sClient()
    api = _RecordingAPI()

    async def fake_get_api():
        return api

    client._get_api = fake_get_api  # type: ignore[method-assign]

    await client.create_sandbox(
        name="ephemeral-sb",
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:latest",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "512Mi"}},
    )

    manifest = api.calls[0]["json"]
    pod_spec = manifest["spec"]["podTemplate"]["spec"]

    assert "securityContext" not in pod_spec
    assert "initContainers" not in pod_spec
    assert "volumeMounts" not in pod_spec["containers"][0]
    assert "volumeClaimTemplates" not in manifest["spec"]
