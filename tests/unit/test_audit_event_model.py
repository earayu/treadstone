from treadstone.models.audit_event import AuditActorType, AuditEvent, AuditResult


def test_audit_event_fields_exist():
    event = AuditEvent()

    for field in (
        "id",
        "created_at",
        "actor_type",
        "actor_user_id",
        "actor_api_key_id",
        "credential_type",
        "action",
        "target_type",
        "target_id",
        "result",
        "error_code",
        "request_id",
        "ip",
        "user_agent",
        "metadata",
    ):
        assert hasattr(event, field)


def test_audit_event_tablename():
    assert AuditEvent.__tablename__ == "audit_event"


def test_audit_event_enums():
    assert AuditActorType.USER == "user"
    assert AuditActorType.SYSTEM == "system"
    assert AuditResult.SUCCESS == "success"
    assert AuditResult.FAILURE == "failure"
