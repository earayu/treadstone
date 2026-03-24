"""K8s Lease-based leader election for singleton background tasks."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

logger = logging.getLogger(__name__)

LEASE_API_GROUP = "coordination.k8s.io"
LEASE_API_VERSION = "v1"


class LeadershipState(StrEnum):
    LEADER = "leader"
    FOLLOWER = "follower"


class K8sLeaseError(Exception):
    """Base error for Lease API operations."""


class K8sLeaseConflictError(K8sLeaseError):
    """Raised when a Lease create/replace hits a resourceVersion conflict."""


class LeaseStoreProtocol(Protocol):
    async def get_lease(self, namespace: str, name: str) -> dict[str, Any] | None: ...

    async def create_lease(self, namespace: str, manifest: dict[str, Any]) -> dict[str, Any]: ...

    async def replace_lease(self, namespace: str, name: str, manifest: dict[str, Any]) -> dict[str, Any] | None: ...


def format_lease_time(dt: datetime) -> str:
    """Format Lease timestamps as RFC3339."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_lease_time(value: str | None) -> datetime | None:
    """Parse RFC3339 timestamps returned by the Lease API."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class K8sLeaseStore:
    """Minimal Lease CRUD wrapper using kr8s raw API access."""

    def __init__(self, api_factory: Callable[[], Awaitable[Any]] | None = None) -> None:
        self._api = None
        self._api_factory = api_factory
        self._lock = asyncio.Lock()

    async def _get_api(self):
        if self._api_factory is not None:
            return await self._api_factory()

        async with self._lock:
            if self._api is None:
                import kr8s

                self._api = await kr8s.asyncio.api()
        return self._api

    async def get_lease(self, namespace: str, name: str) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{LEASE_API_GROUP}/{LEASE_API_VERSION}/namespaces/{namespace}/leases/{name}"
        async with api.call_api("GET", base=url, version="", raise_for_status=False) as resp:
            data = _json_or_empty(resp)
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise K8sLeaseError(_error_message(data, resp.status_code))
            return data

    async def create_lease(self, namespace: str, manifest: dict[str, Any]) -> dict[str, Any]:
        api = await self._get_api()
        url = f"/apis/{LEASE_API_GROUP}/{LEASE_API_VERSION}/namespaces/{namespace}/leases"
        async with api.call_api("POST", base=url, version="", json=manifest, raise_for_status=False) as resp:
            data = _json_or_empty(resp)
            if resp.status_code == 409:
                raise K8sLeaseConflictError(_error_message(data, resp.status_code))
            if resp.status_code >= 400:
                raise K8sLeaseError(_error_message(data, resp.status_code))
            return data

    async def replace_lease(self, namespace: str, name: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
        api = await self._get_api()
        url = f"/apis/{LEASE_API_GROUP}/{LEASE_API_VERSION}/namespaces/{namespace}/leases/{name}"
        async with api.call_api("PUT", base=url, version="", json=manifest, raise_for_status=False) as resp:
            data = _json_or_empty(resp)
            if resp.status_code == 404:
                return None
            if resp.status_code == 409:
                raise K8sLeaseConflictError(_error_message(data, resp.status_code))
            if resp.status_code >= 400:
                raise K8sLeaseError(_error_message(data, resp.status_code))
            return data


class LeaderElector:
    """Lease-based leader election for a single named background worker."""

    def __init__(
        self,
        *,
        lease_store: LeaseStoreProtocol,
        namespace: str,
        lease_name: str,
        holder_identity: str,
        lease_duration_seconds: int,
        renew_interval_seconds: int,
        retry_interval_seconds: int,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if renew_interval_seconds >= lease_duration_seconds:
            raise ValueError("renew_interval_seconds must be less than lease_duration_seconds")
        if retry_interval_seconds > renew_interval_seconds:
            raise ValueError("retry_interval_seconds must be less than or equal to renew_interval_seconds")

        self.lease_store = lease_store
        self.namespace = namespace
        self.lease_name = lease_name
        self.holder_identity = holder_identity
        self.lease_duration_seconds = lease_duration_seconds
        self.renew_interval_seconds = renew_interval_seconds
        self.retry_interval_seconds = retry_interval_seconds
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._is_leader = False

    async def try_acquire_or_renew(self) -> LeadershipState:
        now = self._now_fn()
        lease = await self.lease_store.get_lease(self.namespace, self.lease_name)

        if lease is None:
            return await self._create_new_lease(now)

        holder_identity = lease.get("spec", {}).get("holderIdentity", "")
        if holder_identity == self.holder_identity:
            return await self._renew_lease(lease, now)

        if not holder_identity:
            return await self._take_over_lease(lease, now)

        if self._lease_is_expired(lease, now):
            return await self._take_over_lease(lease, now)

        self._is_leader = False
        return LeadershipState.FOLLOWER

    async def release_if_held(self) -> None:
        lease = await self.lease_store.get_lease(self.namespace, self.lease_name)
        if lease is None:
            self._is_leader = False
            return

        holder_identity = lease.get("spec", {}).get("holderIdentity", "")
        if holder_identity != self.holder_identity:
            self._is_leader = False
            return

        manifest = self._build_manifest(
            now=self._now_fn(),
            resource_version=lease.get("metadata", {}).get("resourceVersion", ""),
            holder_identity="",
            acquire_time=lease.get("spec", {}).get("acquireTime"),
            lease_transitions=lease.get("spec", {}).get("leaseTransitions", 0),
        )
        try:
            await self.lease_store.replace_lease(self.namespace, self.lease_name, manifest)
            logger.info("Leadership released for %s/%s", self.namespace, self.lease_name)
        except (K8sLeaseConflictError, K8sLeaseError):
            logger.warning("Failed to release leadership for %s/%s", self.namespace, self.lease_name, exc_info=True)
        finally:
            self._is_leader = False

    async def _create_new_lease(self, now: datetime) -> LeadershipState:
        manifest = self._build_manifest(
            now=now,
            resource_version="",
            holder_identity=self.holder_identity,
            acquire_time=format_lease_time(now),
            lease_transitions=0,
        )
        try:
            await self.lease_store.create_lease(self.namespace, manifest)
        except K8sLeaseConflictError:
            self._is_leader = False
            return LeadershipState.FOLLOWER

        self._mark_leader_transition()
        return LeadershipState.LEADER

    async def _renew_lease(self, lease: dict[str, Any], now: datetime) -> LeadershipState:
        manifest = self._build_manifest(
            now=now,
            resource_version=lease.get("metadata", {}).get("resourceVersion", ""),
            holder_identity=self.holder_identity,
            acquire_time=lease.get("spec", {}).get("acquireTime") or format_lease_time(now),
            lease_transitions=lease.get("spec", {}).get("leaseTransitions", 0),
        )
        try:
            replaced = await self.lease_store.replace_lease(self.namespace, self.lease_name, manifest)
        except K8sLeaseConflictError:
            self._is_leader = False
            return LeadershipState.FOLLOWER

        if replaced is None:
            self._is_leader = False
            return LeadershipState.FOLLOWER

        self._is_leader = True
        return LeadershipState.LEADER

    async def _take_over_lease(self, lease: dict[str, Any], now: datetime) -> LeadershipState:
        manifest = self._build_manifest(
            now=now,
            resource_version=lease.get("metadata", {}).get("resourceVersion", ""),
            holder_identity=self.holder_identity,
            acquire_time=format_lease_time(now),
            lease_transitions=lease.get("spec", {}).get("leaseTransitions", 0) + 1,
        )
        try:
            replaced = await self.lease_store.replace_lease(self.namespace, self.lease_name, manifest)
        except K8sLeaseConflictError:
            self._is_leader = False
            return LeadershipState.FOLLOWER

        if replaced is None:
            self._is_leader = False
            return LeadershipState.FOLLOWER

        self._mark_leader_transition()
        return LeadershipState.LEADER

    def _mark_leader_transition(self) -> None:
        if not self._is_leader:
            logger.info("Leadership acquired for %s/%s", self.namespace, self.lease_name)
        self._is_leader = True

    def _lease_is_expired(self, lease: dict[str, Any], now: datetime) -> bool:
        spec = lease.get("spec", {})
        renew_time = parse_lease_time(spec.get("renewTime"))
        acquire_time = parse_lease_time(spec.get("acquireTime"))
        effective_time = renew_time or acquire_time
        if effective_time is None:
            return True
        lease_duration_seconds = int(spec.get("leaseDurationSeconds", self.lease_duration_seconds))
        return now - effective_time >= timedelta(seconds=lease_duration_seconds)

    def _build_manifest(
        self,
        *,
        now: datetime,
        resource_version: str,
        holder_identity: str,
        acquire_time: str,
        lease_transitions: int,
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "apiVersion": f"{LEASE_API_GROUP}/{LEASE_API_VERSION}",
            "kind": "Lease",
            "metadata": {"name": self.lease_name, "namespace": self.namespace},
            "spec": {
                "holderIdentity": holder_identity,
                "leaseDurationSeconds": self.lease_duration_seconds,
                "acquireTime": acquire_time,
                "renewTime": format_lease_time(now),
                "leaseTransitions": lease_transitions,
            },
        }
        if resource_version:
            manifest["metadata"]["resourceVersion"] = resource_version
        return manifest


def _json_or_empty(resp: Any) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _error_message(data: dict[str, Any], status_code: int) -> str:
    return str(data.get("message") or f"Kubernetes Lease API request failed with status {status_code}")
