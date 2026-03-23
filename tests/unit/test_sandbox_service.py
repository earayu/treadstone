"""Unit tests for SandboxService with mocked DB and K8s client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from treadstone.core.errors import InvalidTransitionError, TemplateNotFoundError
from treadstone.models.sandbox import Sandbox, SandboxStatus


def _make_sandbox(**overrides) -> Sandbox:
    defaults = {
        "id": "sb1234567890abcdef",
        "name": "test-sandbox",
        "owner_id": "user1234567890abcd",
        "template": "aio-sandbox-tiny",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.CREATING,
        "version": 1,
        "endpoints": {},
        "k8s_sandbox_claim_name": "test-sandbox",
        "k8s_sandbox_name": "test-sandbox",
        "k8s_namespace": "treadstone-local",
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
    k8s.create_sandbox_claim = AsyncMock(
        return_value={"metadata": {"name": "test-sb"}, "status": {"sandbox": {"Name": "test-sb"}}}
    )
    k8s.delete_sandbox_claim = AsyncMock(return_value=True)
    k8s.create_sandbox = AsyncMock(return_value={"metadata": {"name": "test-sb"}, "kind": "Sandbox"})
    k8s.delete_sandbox = AsyncMock(return_value=True)
    k8s.scale_sandbox = AsyncMock(return_value=True)
    k8s.get_sandbox_claim = AsyncMock(return_value=None)
    k8s.list_sandbox_templates = AsyncMock(
        return_value=[
            {
                "name": "aio-sandbox-tiny",
                "image": "ghcr.io/agent-infra/sandbox:latest",
                "resource_spec": {"cpu": "250m", "memory": "512Mi"},
            },
        ]
    )
    return k8s


class TestSandboxServiceCreate:
    async def test_create_returns_sandbox_with_creating_status(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-tiny",
            name="my-sandbox",
        )

        assert result.status == SandboxStatus.CREATING
        assert result.owner_id == "user1234567890abcd"
        assert result.template == "aio-sandbox-tiny"
        assert result.k8s_sandbox_claim_name == "my-sandbox"
        session.add.assert_called_once()
        session.commit.assert_called()

    async def test_create_calls_k8s_create_sandbox_claim(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-tiny",
        )

        k8s.create_sandbox_claim.assert_called_once()
        call_kwargs = k8s.create_sandbox_claim.call_args
        assert call_kwargs.kwargs["template_ref"] == "aio-sandbox-tiny"


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
    async def test_delete_calls_delete_sandbox_claim(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert sb.status == SandboxStatus.DELETING
        k8s.delete_sandbox_claim.assert_called_once()

    async def test_delete_from_creating_succeeds(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.CREATING)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert sb.status == SandboxStatus.DELETING
        k8s.delete_sandbox_claim.assert_called_once()

    async def test_delete_from_deleted_raises(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.DELETED)
        session = _mock_session(sb)
        service = SandboxService(session=session, k8s_client=_mock_k8s_client())

        with pytest.raises(InvalidTransitionError):
            await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")


class TestSandboxServiceStartStop:
    async def test_start_calls_scale_sandbox_1(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.STOPPED)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.start(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert result.status == SandboxStatus.CREATING
        k8s.scale_sandbox.assert_called_once_with(name="test-sandbox", namespace="treadstone-local", replicas=1)

    async def test_stop_calls_scale_sandbox_0(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.stop(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        assert result.status == SandboxStatus.STOPPED
        k8s.scale_sandbox.assert_called_once_with(name="test-sandbox", namespace="treadstone-local", replicas=0)

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


class TestDualPathProvisioning:
    async def test_create_without_persist_uses_claim_path(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-tiny",
            persist=False,
        )

        assert result.provision_mode == "claim"
        assert result.persist is False
        k8s.create_sandbox_claim.assert_called_once()
        k8s.create_sandbox.assert_not_called()

    async def test_create_with_persist_uses_direct_path(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-tiny",
            persist=True,
            storage_size="20Gi",
        )

        assert result.provision_mode == "direct"
        assert result.persist is True
        assert result.storage_size == "20Gi"
        k8s.create_sandbox.assert_called_once()
        k8s.create_sandbox_claim.assert_not_called()
        call_kwargs = k8s.create_sandbox.call_args.kwargs
        assert call_kwargs["volume_claim_templates"] is not None
        assert call_kwargs["volume_claim_templates"][0]["spec"]["resources"]["requests"]["storage"] == "20Gi"

    async def test_delete_claim_path_calls_delete_sandbox_claim(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, provision_mode="claim")
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        k8s.delete_sandbox_claim.assert_called_once()
        k8s.delete_sandbox.assert_not_called()

    async def test_delete_direct_path_calls_delete_sandbox(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, provision_mode="direct")
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        await service.delete(sandbox_id="sb1234567890abcdef", owner_id="user1234567890abcd")
        k8s.delete_sandbox.assert_called_once()
        k8s.delete_sandbox_claim.assert_not_called()


class TestTemplateValidation:
    async def test_claim_path_rejects_invalid_template(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        session.delete = AsyncMock()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        with pytest.raises(TemplateNotFoundError):
            await service.create(
                owner_id="user1234567890abcd",
                template="nonexistent-template",
                persist=False,
            )

        k8s.create_sandbox_claim.assert_not_called()

    async def test_direct_path_rejects_invalid_template(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        session.delete = AsyncMock()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        with pytest.raises(TemplateNotFoundError):
            await service.create(
                owner_id="user1234567890abcd",
                template="nonexistent-template",
                persist=True,
            )

        k8s.create_sandbox.assert_not_called()

    async def test_invalid_template_cleans_up_db_record(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        session.delete = AsyncMock()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s)

        with pytest.raises(TemplateNotFoundError):
            await service.create(
                owner_id="user1234567890abcd",
                template="nonexistent-template",
                persist=False,
            )

        session.delete.assert_called_once()
