import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app
from treadstone.services.k8s_client import FakeK8sClient, set_k8s_client


@pytest.fixture(autouse=True)
def _use_fake_k8s_client():
    """Inject FakeK8sClient for all tests so no real K8s cluster is needed."""
    set_k8s_client(FakeK8sClient())
    yield
    set_k8s_client(None)  # type: ignore[arg-type]


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
