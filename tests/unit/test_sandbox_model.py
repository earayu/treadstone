from treadstone.models.sandbox import Sandbox, SandboxStatus


def test_sandbox_status_enum():
    assert SandboxStatus.CREATING == "creating"
    assert SandboxStatus.READY == "ready"
    assert SandboxStatus.STOPPED == "stopped"
    assert SandboxStatus.ERROR == "error"
    assert SandboxStatus.DELETING == "deleting"
    assert SandboxStatus.DELETED == "deleted"


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
        "status_message",
        "endpoints",
        "version",
        "gmt_created",
        "gmt_started",
        "gmt_stopped",
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
    "creating": ["ready", "error", "deleting"],
    "ready": ["stopped", "error", "deleting"],
    "stopped": ["ready", "deleting", "deleted"],
    "error": ["stopped", "deleting"],
    "deleting": ["deleted"],
    "deleted": [],
}


def test_valid_transitions_exist():
    from treadstone.models.sandbox import VALID_TRANSITIONS as transitions

    assert transitions == VALID_TRANSITIONS


def test_is_valid_transition():
    from treadstone.models.sandbox import is_valid_transition

    assert is_valid_transition("creating", "ready") is True
    assert is_valid_transition("creating", "error") is True
    assert is_valid_transition("creating", "deleted") is False
    assert is_valid_transition("deleted", "ready") is False
    assert is_valid_transition("deleting", "ready") is False
    assert is_valid_transition("ready", "deleting") is True
