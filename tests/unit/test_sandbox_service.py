"""Unit tests for SandboxService with mocked DB and K8s client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from treadstone.core.errors import InvalidTransitionError
from treadstone.models.sandbox import Sandbox, SandboxStatus


def _make_sandbox(**overrides) -> Sandbox:
    defaults = {
        "id": "sb1234567890abcdef",
        "name": "test-sandbox",
        "owner_id": "user1234567890abcd",
        "template": "python-dev",
        "runtime_type": "aio",
        "image": "ghcr.io/earayu/sandbox-runtime:latest",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.CREATING,
        "version": 1,
        "endpoints": {},
    }
    defaults.update(overrides)
    sb = Sandbox()
    for k, v in defaults.items():
        setattr(sb, k, v)
    return sb


def _mock_session(sandbox: Sandbox | None = None):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sandbox
    session.execute.return_value = mock_result
    session.get.return_value = sandbox
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _mock_k8s_client():
    k8s = AsyncMock()
    k8s.create_sandbox_cr = AsyncMock(return_value={"metadata": {"name": "sb-test"}})
    k8s.delete_sandbox_cr = AsyncMock(return_value=True)
    k8s.start_sandbox_cr = AsyncMock(return_value=True)
    k8s.stop_sandbox_cr = AsyncMock(return_value=True)
    return k8s


class TestSandboxServiceCreate:
    async def test_create_returns_sandbox_with_creating_status(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="python-dev",
            image="ghcr.io/earayu/sandbox-runtime:latest",
            name="my-sandbox",
        )

        assert result.status == SandboxStatus.CREATING
        assert result.owner_id == "user1234567890abcd"
        assert result.template == "python-dev"
        session.add.assert_called_once()
        session.commit.assert_called()

    async def test_create_calls_k8s_client(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.create(
            owner_id="user1234567890abcd",
            template="python-dev",
            image="ghcr.io/earayu/sandbox-runtime:latest",
        )

        k8s.create_sandbox_cr.assert_called_once()


class TestSandboxServiceGet:
    async def test_get_returns_sandbox(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox()
        session = _mock_session(sb)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        result = await service.get(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert result is not None
        assert result.id == "sb1234567890abcdef"

    async def test_get_returns_none_for_wrong_owner(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session(None)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        result = await service.get(sandbox_id="sb1234567890abcdef", owner_id="wrong-owner")
        assert result is None


class TestSandboxServiceDelete:
    async def test_delete_sets_deleting_status(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert sb.status == SandboxStatus.DELETING
        k8s.delete_sandbox_cr.assert_called_once()

    async def test_delete_invalid_transition_raises(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.CREATING)
        session = _mock_session(sb)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        with pytest.raises(InvalidTransitionError):
            await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")


class TestSandboxServiceStartStop:
    async def test_start_from_stopped(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.STOPPED)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.start(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert result.status == SandboxStatus.READY
        k8s.start_sandbox_cr.assert_called_once()

    async def test_stop_from_ready(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.stop(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert result.status == SandboxStatus.STOPPED
        k8s.stop_sandbox_cr.assert_called_once()

    async def test_start_from_ready_raises(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY)
        session = _mock_session(sb)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        with pytest.raises(InvalidTransitionError):
            await service.start(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")

    async def test_start_from_creating_raises(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.CREATING)
        session = _mock_session(sb)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        with pytest.raises(InvalidTransitionError):
            await service.start(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
