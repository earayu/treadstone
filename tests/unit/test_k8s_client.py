"""Unit tests for K8s client (FakeK8sClient)."""

from treadstone.services.k8s_client import FakeK8sClient


async def test_list_sandbox_templates():
    client = FakeK8sClient()
    templates = await client.list_sandbox_templates("treadstone")
    assert len(templates) >= 2
    names = [t["name"] for t in templates]
    assert "python-dev" in names
    assert "nodejs-dev" in names


async def test_create_and_get_sandbox_cr():
    client = FakeK8sClient()
    cr = await client.create_sandbox_cr("sb-test", "python-dev", "treadstone", "img:latest")
    assert cr["metadata"]["name"] == "sb-test"

    fetched = await client.get_sandbox_cr("sb-test", "treadstone")
    assert fetched is not None
    assert fetched["spec"]["template"] == "python-dev"


async def test_delete_sandbox_cr():
    client = FakeK8sClient()
    await client.create_sandbox_cr("sb-del", "python-dev", "treadstone", "img:latest")
    result = await client.delete_sandbox_cr("sb-del", "treadstone")
    assert result is True
    assert await client.get_sandbox_cr("sb-del", "treadstone") is None


async def test_list_sandbox_crs():
    client = FakeK8sClient()
    await client.create_sandbox_cr("sb-1", "python-dev", "treadstone", "img:latest")
    await client.create_sandbox_cr("sb-2", "python-dev", "treadstone", "img:latest")
    crs = await client.list_sandbox_crs("treadstone")
    assert len(crs) == 2


async def test_start_stop_sandbox_cr():
    client = FakeK8sClient()
    await client.create_sandbox_cr("sb-ss", "python-dev", "treadstone", "img:latest")
    await client.start_sandbox_cr("sb-ss", "treadstone")
    cr = await client.get_sandbox_cr("sb-ss", "treadstone")
    assert cr["status"]["phase"] == "Ready"

    await client.stop_sandbox_cr("sb-ss", "treadstone")
    cr = await client.get_sandbox_cr("sb-ss", "treadstone")
    assert cr["status"]["phase"] == "Stopped"
