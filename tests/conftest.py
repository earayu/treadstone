import os

import pytest
from httpx import ASGITransport, AsyncClient

_original_debug = os.environ.get("TREADSTONE_DEBUG")
_original_jwt_secret = os.environ.get("TREADSTONE_JWT_SECRET")

if _original_debug is None:
    os.environ["TREADSTONE_DEBUG"] = "true"
if _original_jwt_secret is None:
    os.environ["TREADSTONE_JWT_SECRET"] = "test-jwt-secret-should-be-32-bytes!"

from treadstone.main import app  # noqa: E402
from treadstone.services.k8s_client import FakeK8sClient, set_k8s_client  # noqa: E402

if _original_debug is None:
    os.environ.pop("TREADSTONE_DEBUG", None)
if _original_jwt_secret is None:
    os.environ.pop("TREADSTONE_JWT_SECRET", None)


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
