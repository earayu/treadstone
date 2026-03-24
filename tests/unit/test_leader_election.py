import copy
from datetime import UTC, datetime, timedelta

from treadstone.services.leader_election import (
    K8sLeaseConflictError,
    LeaderElector,
    LeadershipState,
    format_lease_time,
)


def _ts(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_format_lease_time_uses_microseconds():
    now = datetime(2026, 3, 24, 4, 0, 1, 234567, tzinfo=UTC)

    assert format_lease_time(now) == "2026-03-24T04:00:01.234567Z"


class FakeLeaseStore:
    def __init__(self):
        self._leases: dict[tuple[str, str], dict] = {}
        self.conflict_on_create = False
        self.conflict_on_replace = False

    async def get_lease(self, namespace: str, name: str) -> dict | None:
        lease = self._leases.get((namespace, name))
        return copy.deepcopy(lease) if lease else None

    async def create_lease(self, namespace: str, manifest: dict) -> dict:
        if self.conflict_on_create:
            raise K8sLeaseConflictError("create conflict")
        key = (namespace, manifest["metadata"]["name"])
        created = copy.deepcopy(manifest)
        created["metadata"]["resourceVersion"] = "1"
        self._leases[key] = created
        return copy.deepcopy(created)

    async def replace_lease(self, namespace: str, name: str, manifest: dict) -> dict | None:
        if self.conflict_on_replace:
            raise K8sLeaseConflictError("replace conflict")
        key = (namespace, name)
        current = self._leases.get(key)
        if current is None:
            return None
        if manifest["metadata"].get("resourceVersion") != current["metadata"].get("resourceVersion"):
            raise K8sLeaseConflictError("stale resource version")
        replaced = copy.deepcopy(manifest)
        replaced["metadata"]["resourceVersion"] = str(int(current["metadata"]["resourceVersion"]) + 1)
        self._leases[key] = replaced
        return copy.deepcopy(replaced)

    def seed_lease(self, namespace: str, name: str, lease: dict) -> None:
        self._leases[(namespace, name)] = copy.deepcopy(lease)


def _make_elector(store: FakeLeaseStore, *, now: datetime, holder_identity: str = "pod-a") -> LeaderElector:
    return LeaderElector(
        lease_store=store,
        namespace="treadstone-prod",
        lease_name="treadstone-sync-leader",
        holder_identity=holder_identity,
        lease_duration_seconds=15,
        renew_interval_seconds=5,
        retry_interval_seconds=2,
        now_fn=lambda: now,
    )


async def test_try_acquire_or_renew_creates_lease_and_becomes_leader():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    elector = _make_elector(store, now=now)

    state = await elector.try_acquire_or_renew()

    assert state == LeadershipState.LEADER
    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == "pod-a"
    assert lease["spec"]["acquireTime"] == _ts(now)
    assert lease["spec"]["renewTime"] == _ts(now)
    assert lease["spec"]["leaseDurationSeconds"] == 15
    assert lease["spec"]["leaseTransitions"] == 0


async def test_try_acquire_or_renew_renews_existing_self_held_lease():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    acquired_at = now - timedelta(minutes=5)
    renewed_at = now - timedelta(seconds=4)
    store = FakeLeaseStore()
    store.seed_lease(
        "treadstone-prod",
        "treadstone-sync-leader",
        {
            "apiVersion": "coordination.k8s.io/v1",
            "kind": "Lease",
            "metadata": {"name": "treadstone-sync-leader", "namespace": "treadstone-prod", "resourceVersion": "7"},
            "spec": {
                "holderIdentity": "pod-a",
                "acquireTime": _ts(acquired_at),
                "renewTime": _ts(renewed_at),
                "leaseDurationSeconds": 15,
                "leaseTransitions": 3,
            },
        },
    )
    elector = _make_elector(store, now=now)

    state = await elector.try_acquire_or_renew()

    assert state == LeadershipState.LEADER
    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == "pod-a"
    assert lease["spec"]["acquireTime"] == _ts(acquired_at)
    assert lease["spec"]["renewTime"] == _ts(now)
    assert lease["spec"]["leaseTransitions"] == 3
    assert lease["metadata"]["resourceVersion"] == "8"


async def test_try_acquire_or_renew_returns_follower_when_other_holder_not_expired():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    store.seed_lease(
        "treadstone-prod",
        "treadstone-sync-leader",
        {
            "apiVersion": "coordination.k8s.io/v1",
            "kind": "Lease",
            "metadata": {"name": "treadstone-sync-leader", "namespace": "treadstone-prod", "resourceVersion": "2"},
            "spec": {
                "holderIdentity": "pod-b",
                "acquireTime": _ts(now - timedelta(minutes=1)),
                "renewTime": _ts(now - timedelta(seconds=3)),
                "leaseDurationSeconds": 15,
                "leaseTransitions": 1,
            },
        },
    )
    elector = _make_elector(store, now=now)

    state = await elector.try_acquire_or_renew()

    assert state == LeadershipState.FOLLOWER
    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == "pod-b"


async def test_try_acquire_or_renew_takes_over_expired_lease():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    store.seed_lease(
        "treadstone-prod",
        "treadstone-sync-leader",
        {
            "apiVersion": "coordination.k8s.io/v1",
            "kind": "Lease",
            "metadata": {"name": "treadstone-sync-leader", "namespace": "treadstone-prod", "resourceVersion": "9"},
            "spec": {
                "holderIdentity": "pod-b",
                "acquireTime": _ts(now - timedelta(minutes=3)),
                "renewTime": _ts(now - timedelta(seconds=30)),
                "leaseDurationSeconds": 15,
                "leaseTransitions": 4,
            },
        },
    )
    elector = _make_elector(store, now=now)

    state = await elector.try_acquire_or_renew()

    assert state == LeadershipState.LEADER
    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == "pod-a"
    assert lease["spec"]["acquireTime"] == _ts(now)
    assert lease["spec"]["renewTime"] == _ts(now)
    assert lease["spec"]["leaseTransitions"] == 5
    assert lease["metadata"]["resourceVersion"] == "10"


async def test_try_acquire_or_renew_returns_follower_on_create_conflict():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    store.conflict_on_create = True
    elector = _make_elector(store, now=now)

    state = await elector.try_acquire_or_renew()

    assert state == LeadershipState.FOLLOWER


async def test_release_if_held_clears_holder_identity():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    elector = _make_elector(store, now=now)

    await elector.try_acquire_or_renew()
    await elector.release_if_held()

    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == ""
    assert lease["spec"]["renewTime"] == _ts(now)


async def test_released_lease_can_be_reacquired_immediately():
    now = datetime(2026, 3, 24, 4, 0, tzinfo=UTC)
    store = FakeLeaseStore()
    first_elector = _make_elector(store, now=now, holder_identity="pod-a")

    await first_elector.try_acquire_or_renew()
    await first_elector.release_if_held()

    second_elector = _make_elector(store, now=now + timedelta(seconds=1), holder_identity="pod-b")
    state = await second_elector.try_acquire_or_renew()

    assert state == LeadershipState.LEADER
    lease = await store.get_lease("treadstone-prod", "treadstone-sync-leader")
    assert lease["spec"]["holderIdentity"] == "pod-b"
    assert lease["spec"]["renewTime"] == _ts(now + timedelta(seconds=1))
