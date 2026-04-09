from treadstone.models.sandbox import Sandbox, SandboxPendingOperation, SandboxStatus, StorageBackendMode


def test_sandbox_status_enum():
    assert SandboxStatus.CREATING == "creating"
    assert SandboxStatus.READY == "ready"
    assert SandboxStatus.STOPPED == "stopped"
    assert SandboxStatus.COLD == "cold"
    assert SandboxStatus.ERROR == "error"
    assert SandboxStatus.DELETING == "deleting"
    assert SandboxStatus.DELETED == "deleted"


def test_sandbox_pending_operation_enum():
    assert SandboxPendingOperation.SNAPSHOTTING == "snapshotting"
    assert SandboxPendingOperation.RESTORING == "restoring"


def test_storage_backend_mode_enum():
    assert StorageBackendMode.LIVE_DISK == "live_disk"
    assert StorageBackendMode.STANDARD_SNAPSHOT == "standard_snapshot"
    assert StorageBackendMode.ARCHIVE_SNAPSHOT == "archive_snapshot"


def test_sandbox_fields_exist():
    sb = Sandbox()
    for field in [
        "id",
        "name",
        "owner_id",
        "template",
        "runtime_type",
        "image",
        "labels",
        "auto_stop_interval",
        "auto_delete_interval",
        "k8s_sandbox_claim_name",
        "k8s_sandbox_name",
        "k8s_namespace",
        "k8s_resource_version",
        "last_synced_at",
        "status",
        "pending_operation",
        "pending_operation_target_status",
        "status_message",
        "storage_backend_mode",
        "k8s_workspace_pvc_name",
        "k8s_workspace_pv_name",
        "workspace_volume_handle",
        "workspace_zone",
        "snapshot_provider_id",
        "snapshot_k8s_volume_snapshot_name",
        "snapshot_k8s_volume_snapshot_content_name",
        "endpoints",
        "version",
        "gmt_created",
        "gmt_started",
        "gmt_stopped",
        "gmt_snapshotted",
        "gmt_restored",
        "gmt_snapshot_archived",
        "gmt_deleted",
    ]:
        assert hasattr(sb, field), f"Missing field: {field}"


def test_sandbox_default_values():
    """Column defaults apply at insert time; verify the default values are configured."""
    col_defaults = {col.name: col.default for col in Sandbox.__table__.columns if col.default is not None}
    assert col_defaults["status"].arg == SandboxStatus.CREATING
    assert col_defaults["auto_stop_interval"].arg == 15
    assert col_defaults["auto_delete_interval"].arg == -1
    assert col_defaults["version"].arg == 1
    assert col_defaults["labels"].is_callable
    assert col_defaults["endpoints"].is_callable


def test_sandbox_tablename():
    assert Sandbox.__tablename__ == "sandbox"


VALID_TRANSITIONS: dict[str, list[str]] = {
    "creating": ["ready", "error", "stopped", "deleting"],
    "ready": ["stopped", "error", "deleting"],
    "stopped": ["creating", "ready", "cold", "error", "deleting"],
    "cold": ["stopped", "ready", "error", "deleting"],
    "error": ["ready", "creating", "stopped", "cold", "deleting"],
    "deleting": ["deleted"],
}


def test_valid_transitions_exist():
    from treadstone.models.sandbox import VALID_TRANSITIONS as transitions

    assert transitions == VALID_TRANSITIONS


def test_is_valid_transition():
    from treadstone.models.sandbox import is_valid_transition

    assert is_valid_transition("creating", "ready") is True
    assert is_valid_transition("creating", "error") is True
    assert is_valid_transition("creating", "stopped") is True
    assert is_valid_transition("deleting", "ready") is False
    assert is_valid_transition("deleting", "deleted") is True
    assert is_valid_transition("ready", "deleting") is True
    assert is_valid_transition("stopped", "error") is True
    assert is_valid_transition("stopped", "cold") is True
    assert is_valid_transition("cold", "stopped") is True
    assert is_valid_transition("deleted", "ready") is False
    assert is_valid_transition("error", "ready") is True
    assert is_valid_transition("error", "creating") is True
    assert is_valid_transition("error", "stopped") is True
    assert is_valid_transition("error", "cold") is True
    assert is_valid_transition("error", "deleting") is True


def test_gmt_deleted_defaults_to_none():
    sb = Sandbox()
    assert sb.gmt_deleted is None


def test_partial_unique_index_exists():
    indexes = {idx.name: idx for idx in Sandbox.__table__.indexes}
    assert "uq_sandbox_owner_name_active" in indexes
    idx = indexes["uq_sandbox_owner_name_active"]
    assert idx.unique is True
    col_names = [col.name for col in idx.columns]
    assert "owner_id" in col_names
    assert "name" in col_names
