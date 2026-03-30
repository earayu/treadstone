"""Unit tests for metering integration in SandboxService (F15), K8s Sync (F16), and reconcile_metering (F17)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from treadstone.core.errors import (
    ComputeQuotaExceededError,
    ConcurrentLimitError,
    SandboxDurationExceededError,
    StorageQuotaExceededError,
    TemplateNotAllowedError,
)
from treadstone.models.metering import ComputeSession, UserPlan
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.services.metering_service import MeteringService

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


# ── Helpers ──────────────────────────────────────────────


def _make_sandbox(**overrides) -> Sandbox:
    defaults = {
        "id": "sb1234567890abcdef",
        "name": "test-sandbox",
        "owner_id": "user1234567890abcd",
        "template": "aio-sandbox-small",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.CREATING,
        "version": 1,
        "endpoints": {},
        "k8s_sandbox_claim_name": "sb1234567890abcdef",
        "k8s_sandbox_name": "sb1234567890abcdef",
        "k8s_namespace": "treadstone-local",
        "persist": False,
        "storage_size": None,
        "provision_mode": "claim",
    }
    defaults.update(overrides)
    sb = Sandbox()
    for k, v in defaults.items():
        setattr(sb, k, v)
    return sb


def _make_plan(tier: str = "pro", **kwargs) -> UserPlan:
    defaults = {
        "user_id": "user1234567890abcd",
        "tier": tier,
        "compute_units_monthly_limit": Decimal("100"),
        "compute_units_monthly_used": Decimal("0"),
        "storage_capacity_limit_gib": 10,
        "max_concurrent_running": 3,
        "max_sandbox_duration_seconds": 7200,
        "allowed_templates": ["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"],
        "grace_period_seconds": 1800,
        "period_start": datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        "period_end": datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return UserPlan(**defaults)


def _mock_session(sandbox: Sandbox | None = None, *extra_scalars):
    session = AsyncMock()
    execute_results = [sandbox, *extra_scalars, None]

    def _make_result(value):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = value
        return mock_result

    session.execute.side_effect = [_make_result(value) for value in execute_results] or [_make_result(None)]
    session.get.return_value = sandbox
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    return session


def _mock_k8s_client():
    k8s = AsyncMock()
    k8s.create_sandbox_claim = AsyncMock(return_value={"metadata": {"name": "test-sb"}})
    k8s.delete_sandbox_claim = AsyncMock(return_value=True)
    k8s.create_sandbox = AsyncMock(return_value={"metadata": {"name": "test-sb"}})
    k8s.delete_sandbox = AsyncMock(return_value=True)
    k8s.scale_sandbox = AsyncMock(return_value=True)
    k8s.get_storage_class = AsyncMock(return_value={"metadata": {"name": "treadstone-workspace"}})
    k8s.list_sandbox_templates = AsyncMock(
        return_value=[
            {
                "name": "aio-sandbox-small",
                "image": "ghcr.io/agent-infra/sandbox:latest",
                "resource_spec": {"cpu": "500m", "memory": "1Gi"},
            },
        ]
    )
    return k8s


def _mock_metering() -> MeteringService:
    m = MagicMock(spec=MeteringService)
    m.check_template_allowed = AsyncMock()
    m.check_compute_quota = AsyncMock()
    m.check_concurrent_limit = AsyncMock()
    m.check_storage_quota = AsyncMock()
    m.check_sandbox_duration = AsyncMock(return_value=7200)
    m.get_user_plan = AsyncMock(return_value=_make_plan())
    m.record_storage_allocation = AsyncMock()
    m.record_storage_release = AsyncMock()
    m.open_compute_session = AsyncMock()
    m.close_compute_session = AsyncMock()
    return m


# ═══════════════════════════════════════════════════════════
#  F15 — SandboxService metering integration
# ═══════════════════════════════════════════════════════════


class TestSandboxServiceCreateWithMetering:
    async def test_create_runs_all_quota_checks(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.create(owner_id="user1234567890abcd", template="aio-sandbox-small")

        metering.check_template_allowed.assert_awaited_once()
        metering.check_compute_quota.assert_awaited_once()
        metering.check_concurrent_limit.assert_awaited_once()
        metering.check_sandbox_duration.assert_awaited_once()

    async def test_create_persist_checks_storage_quota(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.create(
            owner_id="user1234567890abcd", template="aio-sandbox-small", persist=True, storage_size="5Gi"
        )

        metering.check_storage_quota.assert_awaited_once_with(session, "user1234567890abcd", 5)

    async def test_create_non_persist_skips_storage_check(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.create(owner_id="user1234567890abcd", template="aio-sandbox-small", persist=False)

        metering.check_storage_quota.assert_not_awaited()

    async def test_create_persist_records_storage_allocation(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        result = await service.create(
            owner_id="user1234567890abcd", template="aio-sandbox-small", persist=True, storage_size="10Gi"
        )

        metering.record_storage_allocation.assert_awaited_once_with(session, "user1234567890abcd", result.id, 10)

    async def test_create_template_not_allowed_aborts_early(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_template_allowed = AsyncMock(
            side_effect=TemplateNotAllowedError("free", "aio-sandbox-large", ["aio-sandbox-tiny", "aio-sandbox-small"])
        )
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(TemplateNotAllowedError):
            await service.create(owner_id="user1234567890abcd", template="aio-sandbox-large")

        session.add.assert_not_called()
        k8s.create_sandbox_claim.assert_not_called()

    async def test_create_compute_quota_exceeded_aborts_early(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_compute_quota = AsyncMock(side_effect=ComputeQuotaExceededError(100.0, 100.0, 0.0))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(ComputeQuotaExceededError):
            await service.create(owner_id="user1234567890abcd", template="aio-sandbox-small")

        session.add.assert_not_called()

    async def test_create_concurrent_limit_exceeded_aborts_early(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_concurrent_limit = AsyncMock(side_effect=ConcurrentLimitError(3, 3))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(ConcurrentLimitError):
            await service.create(owner_id="user1234567890abcd", template="aio-sandbox-small")

        session.add.assert_not_called()

    async def test_create_storage_quota_exceeded_aborts_early(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_storage_quota = AsyncMock(side_effect=StorageQuotaExceededError(8, 5, 10))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(StorageQuotaExceededError):
            await service.create(
                owner_id="user1234567890abcd", template="aio-sandbox-small", persist=True, storage_size="5Gi"
            )

        session.add.assert_not_called()

    async def test_create_duration_exceeded_raises(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_sandbox_duration = AsyncMock(return_value=1800)
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(SandboxDurationExceededError):
            await service.create(
                owner_id="user1234567890abcd",
                template="aio-sandbox-small",
                auto_stop_interval=60,
            )

    async def test_create_auto_stop_disabled_skips_duration_check(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_sandbox_duration = AsyncMock(return_value=1800)
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-small",
            auto_stop_interval=-1,
        )
        assert result.status == SandboxStatus.CREATING

    async def test_create_never_autostop_blocked_when_tier_has_limit(self, monkeypatch):
        """auto_stop_interval=0 (never) must be rejected if the tier enforces a duration limit."""
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_sandbox_duration = AsyncMock(return_value=1800)
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(SandboxDurationExceededError):
            await service.create(
                owner_id="user1234567890abcd",
                template="aio-sandbox-small",
                auto_stop_interval=0,
            )

    async def test_create_never_autostop_allowed_when_tier_unlimited(self, monkeypatch):
        """auto_stop_interval=0 (never) is allowed when the tier has no duration limit (max_duration=0)."""
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_sandbox_duration = AsyncMock(return_value=0)
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-small",
            auto_stop_interval=0,
        )
        assert result.status == SandboxStatus.CREATING

    async def test_create_any_interval_allowed_when_tier_unlimited(self, monkeypatch):
        """When tier has no duration limit (max_duration=0), any positive interval is allowed."""
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_sandbox_duration = AsyncMock(return_value=0)
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        result = await service.create(
            owner_id="user1234567890abcd",
            template="aio-sandbox-small",
            auto_stop_interval=9999,
        )
        assert result.status == SandboxStatus.CREATING

    async def test_create_without_metering_skips_all_checks(self):
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s, metering=None)

        result = await service.create(owner_id="user1234567890abcd", template="aio-sandbox-small")

        assert result.status == SandboxStatus.CREATING


class TestSandboxServiceStartWithMetering:
    async def test_start_runs_quota_checks(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.STOPPED)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.start(sandbox_id=sb.id, owner_id=sb.owner_id)

        metering.check_compute_quota.assert_awaited_once()
        metering.check_concurrent_limit.assert_awaited_once()

    async def test_start_compute_quota_exceeded_aborts(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.sandbox_service.settings.metering_enforcement_enabled", True)
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.STOPPED)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.check_compute_quota = AsyncMock(side_effect=ComputeQuotaExceededError(100.0, 100.0, 0.0))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        with pytest.raises(ComputeQuotaExceededError):
            await service.start(sandbox_id=sb.id, owner_id=sb.owner_id)

        k8s.scale_sandbox.assert_not_called()

    async def test_start_without_metering_skips_checks(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.STOPPED)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s, metering=None)

        result = await service.start(sandbox_id=sb.id, owner_id=sb.owner_id)
        assert result.status == SandboxStatus.CREATING
        k8s.scale_sandbox.assert_called_once()


class TestSandboxServiceDeleteWithMetering:
    async def test_delete_persist_does_not_release_storage_early(self):
        """Storage release moved to K8s Watch/Reconcile — delete() must NOT call it."""
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, persist=True, provision_mode="direct")
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.delete(sandbox_id=sb.id, owner_id=sb.owner_id)

        metering.record_storage_release.assert_not_awaited()

    async def test_delete_non_persist_skips_storage_release(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, persist=False)
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.delete(sandbox_id=sb.id, owner_id=sb.owner_id)

        metering.record_storage_release.assert_not_awaited()

    async def test_delete_without_metering_succeeds(self):
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, persist=True, provision_mode="direct")
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        service = SandboxService(session=session, k8s_client=k8s, metering=None)

        await service.delete(sandbox_id=sb.id, owner_id=sb.owner_id)
        assert sb.status == SandboxStatus.DELETING

    async def test_delete_persist_metering_failure_still_deletes(self):
        """Metering release failure should not block sandbox deletion."""
        from treadstone.services.sandbox_service import SandboxService

        sb = _make_sandbox(status=SandboxStatus.READY, persist=True, provision_mode="direct")
        session = _mock_session(sb)
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.record_storage_release = AsyncMock(side_effect=RuntimeError("DB error"))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        await service.delete(sandbox_id=sb.id, owner_id=sb.owner_id)

        assert sb.status == SandboxStatus.DELETING
        k8s.delete_sandbox.assert_called_once()

    async def test_create_persist_metering_allocation_failure_still_returns(self):
        """Storage allocation metering failure should not block sandbox creation."""
        from treadstone.services.sandbox_service import SandboxService

        session = _mock_session()
        k8s = _mock_k8s_client()
        metering = _mock_metering()
        metering.record_storage_allocation = AsyncMock(side_effect=RuntimeError("DB error"))
        service = SandboxService(session=session, k8s_client=k8s, metering=metering)

        result = await service.create(
            owner_id="user1234567890abcd", template="aio-sandbox-small", persist=True, storage_size="5Gi"
        )

        assert result.status == SandboxStatus.CREATING
        assert result.persist is True


# ═══════════════════════════════════════════════════════════
#  F16 — K8s Sync metering integration
# ═══════════════════════════════════════════════════════════


class TestApplyMeteringOnTransition:
    async def test_creating_to_ready_opens_session(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.CREATING)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.CREATING, SandboxStatus.READY)

            mock_metering.open_compute_session.assert_awaited_once_with(
                session, sandbox.id, sandbox.owner_id, sandbox.template
            )
            mock_metering.close_compute_session.assert_not_awaited()

    async def test_ready_to_stopped_closes_session(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.READY, SandboxStatus.STOPPED)

            mock_metering.close_compute_session.assert_awaited_once_with(session, sandbox.id)
            mock_metering.open_compute_session.assert_not_awaited()

    async def test_ready_to_error_closes_session(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.close_compute_session = AsyncMock()

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.READY, SandboxStatus.ERROR)

            mock_metering.close_compute_session.assert_awaited_once()

    async def test_ready_to_deleting_closes_session(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.close_compute_session = AsyncMock()

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.READY, SandboxStatus.DELETING)

            mock_metering.close_compute_session.assert_awaited_once()

    async def test_creating_to_error_is_noop(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.CREATING)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.CREATING, SandboxStatus.ERROR)

            mock_metering.open_compute_session.assert_not_awaited()
            mock_metering.close_compute_session.assert_not_awaited()

    async def test_metering_failure_does_not_raise(self):
        from treadstone.services.k8s_sync import _apply_metering_on_transition

        session = AsyncMock()
        sandbox = _make_sandbox(status=SandboxStatus.CREATING)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock(side_effect=RuntimeError("DB failure"))

            await _apply_metering_on_transition(session, sandbox, SandboxStatus.CREATING, SandboxStatus.READY)


class TestTryCloseComputeSession:
    async def test_delegates_to_metering(self):
        from treadstone.services.k8s_sync import _try_close_compute_session

        session = AsyncMock()
        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.close_compute_session = AsyncMock()

            await _try_close_compute_session(session, "sb_test")

            mock_metering.close_compute_session.assert_awaited_once_with(session, "sb_test")

    async def test_failure_does_not_raise(self):
        from treadstone.services.k8s_sync import _try_close_compute_session

        session = AsyncMock()
        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.close_compute_session = AsyncMock(side_effect=RuntimeError("oops"))

            await _try_close_compute_session(session, "sb_test")


# ═══════════════════════════════════════════════════════════
#  F17 — reconcile_metering
# ═══════════════════════════════════════════════════════════


class _MockScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def __iter__(self):
        return iter(self._items)


class TestReconcileMetering:
    async def test_opens_session_for_ready_sandbox_without_one(self):
        from treadstone.services.k8s_sync import reconcile_metering

        sandbox = _make_sandbox(status=SandboxStatus.READY)

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockScalarsResult([sandbox])
            elif call_count == 2:
                return _MockScalarsResult([])
            else:
                return _MockScalarsResult([])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.get = AsyncMock(return_value=sandbox)
        session.commit = AsyncMock()

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await reconcile_metering(session_factory)

            mock_metering.open_compute_session.assert_awaited_once_with(
                session, sandbox.id, sandbox.owner_id, sandbox.template
            )

    async def test_closes_session_for_stopped_sandbox_with_open_session(self):
        from treadstone.services.k8s_sync import reconcile_metering

        stopped_sandbox = _make_sandbox(status=SandboxStatus.STOPPED)
        open_cs = ComputeSession(
            id="cs_test",
            sandbox_id=stopped_sandbox.id,
            user_id=stopped_sandbox.owner_id,
            template="aio-sandbox-small",
            vcpu_request=Decimal("0.5"),
            memory_gib_request=Decimal("1"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
        )

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockScalarsResult([])
            elif call_count == 2:
                return _MockScalarsResult([(open_cs, stopped_sandbox)])
            else:
                return _MockScalarsResult([])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await reconcile_metering(session_factory)

            mock_metering.close_compute_session.assert_awaited_once_with(session, stopped_sandbox.id)

    async def test_closes_session_for_deleted_sandbox(self):
        from treadstone.services.k8s_sync import reconcile_metering

        open_cs = ComputeSession(
            id="cs_orphan",
            sandbox_id="sb_deleted",
            user_id="user01",
            template="aio-sandbox-small",
            vcpu_request=Decimal("0.5"),
            memory_gib_request=Decimal("1"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
        )

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockScalarsResult([])
            elif call_count == 2:
                return _MockScalarsResult([(open_cs, None)])
            else:
                return _MockScalarsResult([])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.close_compute_session = AsyncMock()

            await reconcile_metering(session_factory)

            mock_metering.close_compute_session.assert_awaited_once_with(session, "sb_deleted")

    async def test_no_mismatches_is_noop(self):
        from treadstone.services.k8s_sync import reconcile_metering

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockScalarsResult([]))
        session.commit = AsyncMock()

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock()
            mock_metering.close_compute_session = AsyncMock()

            await reconcile_metering(session_factory)

            mock_metering.open_compute_session.assert_not_awaited()
            mock_metering.close_compute_session.assert_not_awaited()

    async def test_metering_failure_does_not_halt_reconciliation(self):
        from treadstone.services.k8s_sync import reconcile_metering

        sb1 = _make_sandbox(id="sb_a", status=SandboxStatus.READY)
        sb2 = _make_sandbox(id="sb_b", status=SandboxStatus.READY)

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockScalarsResult([sb1, sb2])
            elif call_count in (2, 3):
                return _MockScalarsResult([])
            elif call_count == 4:
                return _MockScalarsResult([])
            else:
                return _MockScalarsResult([])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with patch("treadstone.services.k8s_sync._metering") as mock_metering:
            mock_metering.open_compute_session = AsyncMock(side_effect=[RuntimeError("fail on sb_a"), None])

            await reconcile_metering(session_factory)

            assert mock_metering.open_compute_session.await_count == 2
