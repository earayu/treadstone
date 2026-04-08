"""Sandbox lifecycle service layer.

Dual-path provisioning:
- persist=False → SandboxClaim path (WarmPool-eligible, no storage)
- persist=True  → Direct Sandbox CR path (with volumeClaimTemplates)

start/stop use scale_sandbox on the Sandbox CR regardless of path.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.config import SANDBOX_STORAGE_SIZE_VALUES, settings
from treadstone.core.errors import (
    BadRequestError,
    InvalidTransitionError,
    SandboxDurationExceededError,
    SandboxNameConflictError,
    SandboxNotFoundError,
    StorageBackendNotReadyError,
    TemplateNotFoundError,
    ValidationError,
)
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import random_id, utc_now
from treadstone.services.k8s_client import (
    ANNOTATION_CREATED_AT,
    ANNOTATION_SANDBOX_NAME,
    LABEL_OWNER_ID,
    LABEL_PROVISION_MODE,
    LABEL_SANDBOX_ID,
    LABEL_TEMPLATE,
    LABEL_WORKLOAD,
    PROVISION_MODE_CLAIM,
    PROVISION_MODE_DIRECT,
    WORKLOAD_SANDBOX,
    K8sClientProtocol,
    get_k8s_client,
)
from treadstone.services.metering_helpers import parse_storage_size_gib

if TYPE_CHECKING:
    from treadstone.services.metering_service import MeteringService

logger = logging.getLogger(__name__)


def _sandbox_status_rank():
    """Stable list ordering: running first, then provisioning, deleting, then error/stopped."""
    return case(
        (Sandbox.status == SandboxStatus.READY, 0),
        (Sandbox.status == SandboxStatus.CREATING, 1),
        (Sandbox.status.in_(["starting", "stopping"]), 1),
        (Sandbox.status == SandboxStatus.DELETING, 2),
        (Sandbox.status.in_([SandboxStatus.ERROR, SandboxStatus.STOPPED]), 3),
        else_=4,
    )


def _sandbox_activity_at():
    """Recency proxy when no gmt_updated exists (see sandbox list sorting design)."""
    return func.coalesce(
        Sandbox.gmt_last_active,
        Sandbox.last_synced_at,
        Sandbox.gmt_started,
        Sandbox.gmt_stopped,
        Sandbox.gmt_created,
    )


def _effective_resource_limits(requests: dict[str, str], limits: dict[str, str] | None) -> dict[str, str]:
    """Use template limits when both CPU and memory are set; otherwise fall back to requests."""
    if not limits:
        return requests
    cpu, mem = limits.get("cpu", "").strip(), limits.get("memory", "").strip()
    if cpu and mem:
        return {"cpu": cpu, "memory": mem}
    return requests


class SandboxService:
    def __init__(
        self,
        session: AsyncSession,
        k8s_client: K8sClientProtocol | None = None,
        metering: MeteringService | None = None,
    ):
        self.session = session
        self.k8s = k8s_client or get_k8s_client()
        self._metering = metering

    async def create(
        self,
        owner_id: str,
        template: str,
        name: str | None = None,
        labels: dict | None = None,
        auto_stop_interval: int = 15,
        auto_delete_interval: int = -1,
        persist: bool = False,
        storage_size: str | None = None,
    ) -> Sandbox:
        effective_storage_size = storage_size or settings.sandbox_default_storage_size

        # ── Validate storage size against template annotation (if persistent) ──
        if persist:
            tmpl = await self._resolve_template(settings.sandbox_namespace, template)
            allowed = tmpl.get("allowed_storage_sizes") or list(SANDBOX_STORAGE_SIZE_VALUES)
            if effective_storage_size not in allowed:
                raise BadRequestError(
                    f"Storage size '{effective_storage_size}' is not allowed for template '{template}'. "
                    f"Allowed sizes: {', '.join(allowed)}"
                )

        # ── Metering: enforcement checks (gated by config) ──
        max_duration: int | None = None
        if self._metering is not None and settings.metering_enforcement_enabled:
            await self._metering.check_template_allowed(self.session, owner_id, template)
            await self._metering.check_compute_quota(self.session, owner_id)
            await self._metering.check_concurrent_limit(self.session, owner_id)

            if persist:
                size_gib = parse_storage_size_gib(effective_storage_size)
                await self._metering.check_storage_quota(self.session, owner_id, size_gib)

            max_duration = await self._metering.check_sandbox_duration(self.session, owner_id)
            if max_duration > 0:
                # Tier enforces a maximum duration.
                # auto_stop_interval == 0 means "never", which is not allowed when tier has a limit.
                if auto_stop_interval == 0 or (auto_stop_interval * 60) > max_duration:
                    plan = await self._metering.get_user_plan(self.session, owner_id)
                    raise SandboxDurationExceededError(plan.tier, max_duration)

        # ── Create sandbox record ──
        sandbox_id = "sb" + random_id()
        sandbox_name = name or f"sb-{random_id(8)}"

        if persist:
            await self._ensure_persistent_storage_backend_ready()

        sandbox = Sandbox()
        sandbox.id = sandbox_id
        sandbox.name = sandbox_name
        sandbox.owner_id = owner_id
        sandbox.template = template
        sandbox.labels = labels or {}
        sandbox.auto_stop_interval = auto_stop_interval
        sandbox.auto_delete_interval = auto_delete_interval
        sandbox.status = SandboxStatus.CREATING
        sandbox.version = 1
        sandbox.endpoints = {}
        sandbox.gmt_created = utc_now()
        sandbox.gmt_last_active = utc_now()
        sandbox.k8s_namespace = settings.sandbox_namespace
        sandbox.persist = persist
        sandbox.storage_size = effective_storage_size if persist else None

        if persist:
            sandbox.provision_mode = "direct"
            sandbox.k8s_sandbox_name = sandbox_id
        else:
            sandbox.provision_mode = "claim"
            sandbox.k8s_sandbox_claim_name = sandbox_id

        self.session.add(sandbox)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise SandboxNameConflictError(sandbox_name)
        await self.session.refresh(sandbox)

        shutdown_time: datetime | None = None
        if max_duration is not None:
            shutdown_time = datetime.now(UTC) + timedelta(seconds=max_duration)

        try:
            if persist:
                await self._create_direct(sandbox, template, effective_storage_size, shutdown_time=shutdown_time)
            else:
                await self._create_via_claim(sandbox, template, shutdown_time=shutdown_time)
        except TemplateNotFoundError:
            await self.session.delete(sandbox)
            await self.session.commit()
            raise
        except Exception:
            logger.exception("Failed to create K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = f"Failed to create {'Sandbox CR' if persist else 'SandboxClaim'}"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()
            logger.info(
                "Sandbox %s status creating -> error (source=api_create) message=%r",
                sandbox_id,
                sandbox.status_message,
            )

        # ── Metering: record storage allocation for persistent sandboxes (best-effort) ──
        if self._metering is not None and persist and sandbox.status != SandboxStatus.ERROR:
            try:
                size_gib = parse_storage_size_gib(effective_storage_size)
                await self._metering.record_storage_allocation(self.session, owner_id, sandbox.id, size_gib)
                await self.session.commit()
            except Exception:
                logger.exception("Failed to record storage allocation for sandbox %s", sandbox_id)

        return sandbox

    async def update(self, sandbox_id: str, owner_id: str, patch: dict[str, Any]) -> Sandbox:
        """Update mutable sandbox metadata. ``patch`` must be non-empty (caller validates)."""
        if not patch:
            raise ValidationError("No fields to update.")

        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        allowed = {"name", "labels", "auto_stop_interval", "auto_delete_interval"}
        extra = set(patch.keys()) - allowed
        if extra:
            raise BadRequestError(f"Unsupported fields: {', '.join(sorted(extra))}")

        new_auto_stop = patch["auto_stop_interval"] if "auto_stop_interval" in patch else sandbox.auto_stop_interval
        if self._metering is not None and settings.metering_enforcement_enabled:
            max_duration = await self._metering.check_sandbox_duration(self.session, owner_id)
            if max_duration > 0:
                if new_auto_stop == 0 or (new_auto_stop * 60) > max_duration:
                    plan = await self._metering.get_user_plan(self.session, owner_id)
                    raise SandboxDurationExceededError(plan.tier, max_duration)

        if "name" in patch:
            sandbox.name = patch["name"]
        if "labels" in patch:
            sandbox.labels = patch["labels"]
        if "auto_stop_interval" in patch:
            sandbox.auto_stop_interval = patch["auto_stop_interval"]
        if "auto_delete_interval" in patch:
            sandbox.auto_delete_interval = patch["auto_delete_interval"]

        sandbox.version += 1
        self.session.add(sandbox)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            if "name" in patch:
                raise SandboxNameConflictError(patch["name"])
            raise
        await self.session.refresh(sandbox)
        return sandbox

    async def _resolve_template(self, namespace: str, template: str) -> dict:
        templates = await self.k8s.list_sandbox_templates(namespace=namespace)
        tmpl = next((t for t in templates if t["name"] == template), None)
        if tmpl is None:
            raise TemplateNotFoundError(template)
        return tmpl

    async def _create_via_claim(
        self, sandbox: Sandbox, template: str, *, shutdown_time: datetime | None = None
    ) -> None:
        await self._resolve_template(sandbox.k8s_namespace, template)

        claim_name = sandbox.k8s_sandbox_claim_name or sandbox.id
        labels = {
            LABEL_SANDBOX_ID: sandbox.id,
            LABEL_OWNER_ID: sandbox.owner_id,
            LABEL_TEMPLATE: template,
            LABEL_PROVISION_MODE: PROVISION_MODE_CLAIM,
        }
        annotations = {
            ANNOTATION_SANDBOX_NAME: sandbox.name,
            ANNOTATION_CREATED_AT: sandbox.gmt_created.isoformat(),
        }
        logger.info("Creating SandboxClaim %s (template=%s, ns=%s)", claim_name, template, sandbox.k8s_namespace)
        await self.k8s.create_sandbox_claim(
            name=claim_name,
            template_ref=template,
            namespace=sandbox.k8s_namespace,
            shutdown_time=shutdown_time,
            labels=labels,
            annotations=annotations,
        )

    async def _ensure_persistent_storage_backend_ready(self) -> None:
        storage_class_name = settings.sandbox_storage_class.strip()
        storage_class = await self.k8s.get_storage_class(storage_class_name)
        if storage_class is None:
            raise StorageBackendNotReadyError(storage_class_name)

    async def _create_direct(
        self, sandbox: Sandbox, template: str, storage_size: str, *, shutdown_time: datetime | None = None
    ) -> None:
        tmpl = await self._resolve_template(sandbox.k8s_namespace, template)

        image = tmpl.get("image", "")
        if not image:
            raise TemplateNotFoundError(template)

        resource_requests = tmpl["resource_spec"]
        resource_limits = _effective_resource_limits(resource_requests, tmpl.get("resource_limits"))
        resources = {
            "requests": resource_requests,
            "limits": resource_limits,
        }
        volume_claim_templates = [
            {
                "metadata": {"name": "workspace"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": settings.sandbox_storage_class,
                    "resources": {"requests": {"storage": storage_size}},
                },
            }
        ]

        k8s_name = sandbox.k8s_sandbox_name or sandbox.id
        labels = {
            LABEL_SANDBOX_ID: sandbox.id,
            LABEL_OWNER_ID: sandbox.owner_id,
            LABEL_TEMPLATE: template,
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        }
        annotations = {
            ANNOTATION_SANDBOX_NAME: sandbox.name,
            ANNOTATION_CREATED_AT: sandbox.gmt_created.isoformat(),
        }
        pod_labels = {
            LABEL_SANDBOX_ID: sandbox.id,
            LABEL_OWNER_ID: sandbox.owner_id,
            LABEL_WORKLOAD: WORKLOAD_SANDBOX,
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        }
        logger.info(
            "Creating Sandbox CR %s (template=%s, persist=true, ns=%s)", k8s_name, template, sandbox.k8s_namespace
        )
        await self.k8s.create_sandbox(
            name=k8s_name,
            namespace=sandbox.k8s_namespace,
            image=image,
            container_port=settings.sandbox_port,
            resources=resources,
            startup_probe=tmpl.get("startup_probe"),
            readiness_probe=tmpl.get("readiness_probe"),
            liveness_probe=tmpl.get("liveness_probe"),
            volume_claim_templates=volume_claim_templates,
            shutdown_time=shutdown_time,
            labels=labels,
            annotations=annotations,
            pod_labels=pod_labels,
        )

    async def get(self, sandbox_id: str, owner_id: str) -> Sandbox | None:
        result = await self.session.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.owner_id == owner_id, Sandbox.gmt_deleted.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: str,
        labels: dict | None = None,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Sandbox], int]:
        """Return one page of sandboxes and total count, ordered for stable UI lists."""
        conds = [Sandbox.owner_id == owner_id, Sandbox.gmt_deleted.is_(None)]
        if labels:
            conds.append(Sandbox.labels.contains(labels))
        where_clause = and_(*conds)

        count_stmt = select(func.count()).select_from(Sandbox).where(where_clause)
        total = int((await self.session.execute(count_stmt)).scalar_one())

        order_by = (
            _sandbox_status_rank().asc(),
            _sandbox_activity_at().desc(),
            Sandbox.gmt_created.desc(),
            Sandbox.name.asc(),
        )
        data_stmt = select(Sandbox).where(where_clause).order_by(*order_by).offset(offset).limit(limit)
        result = await self.session.execute(data_stmt)
        sandboxes = list(result.scalars().all())
        return sandboxes, total

    async def delete(self, sandbox_id: str, owner_id: str) -> None:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if not is_valid_transition(sandbox.status, SandboxStatus.DELETING):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "deleting")

        prev_status = sandbox.status
        sandbox.status = SandboxStatus.DELETING
        sandbox.version += 1
        self.session.add(sandbox)

        link_result = await self.session.execute(
            select(SandboxWebLink).where(
                SandboxWebLink.sandbox_id == sandbox.id,
                SandboxWebLink.gmt_deleted.is_(None),
            )
        )
        link = link_result.scalar_one_or_none()
        if link is not None:
            link.gmt_deleted = utc_now()
            link.gmt_updated = utc_now()
            self.session.add(link)
        await self.session.commit()
        logger.info(
            "Sandbox %s status %s -> deleting (source=user_api_delete)",
            sandbox_id,
            prev_status,
        )

        try:
            if sandbox.provision_mode == "direct":
                sb_name = sandbox.k8s_sandbox_name or sandbox.id
                logger.info("Deleting Sandbox CR %s (ns=%s)", sb_name, sandbox.k8s_namespace)
                await self.k8s.delete_sandbox(name=sb_name, namespace=sandbox.k8s_namespace)
            else:
                claim_name = sandbox.k8s_sandbox_claim_name or sandbox.id
                logger.info("Deleting SandboxClaim %s (ns=%s)", claim_name, sandbox.k8s_namespace)
                await self.k8s.delete_sandbox_claim(name=claim_name, namespace=sandbox.k8s_namespace)
        except Exception:
            logger.exception("Failed to delete K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to delete K8s resource"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()
            logger.info(
                "Sandbox %s status deleting -> error (source=user_api_delete_k8s_failure) message=%r",
                sandbox_id,
                sandbox.status_message,
            )

    async def start(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status not in (SandboxStatus.STOPPED, SandboxStatus.ERROR):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "ready")

        # ── Metering: enforcement checks before resuming (gated by config) ──
        if self._metering is not None and settings.metering_enforcement_enabled:
            await self._metering.check_template_allowed(self.session, owner_id, sandbox.template)
            await self._metering.check_compute_quota(self.session, owner_id)
            await self._metering.check_concurrent_limit(self.session, owner_id)

            max_duration = await self._metering.check_sandbox_duration(self.session, owner_id)
            if sandbox.auto_stop_interval > 0 and (sandbox.auto_stop_interval * 60) > max_duration:
                plan = await self._metering.get_user_plan(self.session, owner_id)
                raise SandboxDurationExceededError(plan.tier, max_duration)

        sandbox.status = SandboxStatus.CREATING
        sandbox.gmt_started = utc_now()
        sandbox.gmt_last_active = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
        try:
            logger.info("Scaling sandbox %s to replicas=1 (ns=%s)", k8s_name, sandbox.k8s_namespace)
            await self.k8s.scale_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace, replicas=1)
        except Exception:
            logger.exception("Failed to scale sandbox %s to 1", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to start sandbox"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()
            logger.info(
                "Sandbox %s status creating -> error (source=user_api_start_k8s_failure) message=%r",
                sandbox_id,
                sandbox.status_message,
            )
            return sandbox

        # The sandbox may already be READY in K8s (e.g. it auto-recovered from ERROR
        # while the DB still showed ERROR, or a no-op scale was issued).  In that case
        # K8s will not fire a new Watch MODIFIED event, so we do a single GET and apply
        # the status immediately rather than waiting for the Watch loop or next reconcile.
        try:
            cr = await self.k8s.get_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace)
            if cr is not None:
                from treadstone.services.k8s_sync import derive_status_from_sandbox_cr

                actual_status, msg = derive_status_from_sandbox_cr(cr)
                if actual_status == SandboxStatus.READY:
                    cr_rv = cr.get("metadata", {}).get("resourceVersion")
                    refreshed = await self.get(sandbox_id, owner_id)
                    if refreshed is not None and is_valid_transition(refreshed.status, SandboxStatus.READY):
                        logger.info("Sandbox %s already READY in K8s after start, updating DB immediately", sandbox_id)
                        refreshed.status = SandboxStatus.READY
                        refreshed.status_message = msg
                        refreshed.version += 1
                        refreshed.gmt_started = utc_now()
                        refreshed.k8s_resource_version = cr_rv
                        self.session.add(refreshed)
                        await self.session.commit()
                        await self.session.refresh(refreshed)
                        return refreshed
        except Exception:
            logger.debug("Post-start K8s status check failed for %s; Watch/reconcile will sync later", sandbox_id)

        return sandbox

    async def stop(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status not in (SandboxStatus.READY, SandboxStatus.ERROR):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "stopped")

        sandbox.status = SandboxStatus.STOPPED
        sandbox.gmt_stopped = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
        try:
            logger.info("Scaling sandbox %s to replicas=0 (ns=%s)", k8s_name, sandbox.k8s_namespace)
            await self.k8s.scale_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace, replicas=0)
        except Exception:
            logger.exception("Failed to scale sandbox %s to 0", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to stop sandbox"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()
            logger.info(
                "Sandbox %s status stopped -> error (source=user_api_stop_k8s_failure) message=%r",
                sandbox_id,
                sandbox.status_message,
            )
            return sandbox

        if self._metering is not None:
            try:
                await self._metering.close_compute_session(self.session, sandbox.id)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                logger.exception(
                    "Failed to close compute session after stopping sandbox %s; reconcile will repair it",
                    sandbox_id,
                )

        return sandbox

    async def touch_activity(self, sandbox_id: str) -> None:
        """Lightweight gmt_last_active bump — single UPDATE, no version bump."""

        await self.session.execute(update(Sandbox).where(Sandbox.id == sandbox_id).values(gmt_last_active=utc_now()))
        await self.session.commit()
