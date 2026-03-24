from treadstone.models.api_key import (
    ApiKey,
    ApiKeyDataPlaneMode,
    ApiKeySandboxGrant,
    build_api_key_preview,
    hash_api_key_secret,
)


def test_api_key_fields():
    k = ApiKey()
    assert hasattr(k, "id")
    assert hasattr(k, "key_hash")
    assert hasattr(k, "key_preview")
    assert hasattr(k, "user_id")
    assert hasattr(k, "name")
    assert hasattr(k, "control_plane_enabled")
    assert hasattr(k, "data_plane_mode")
    assert hasattr(k, "gmt_updated")


def test_api_key_soft_delete_defaults_none():
    k = ApiKey()
    assert k.gmt_deleted is None


def test_api_key_data_plane_mode_values():
    assert ApiKeyDataPlaneMode.NONE.value == "none"
    assert ApiKeyDataPlaneMode.ALL.value == "all"
    assert ApiKeyDataPlaneMode.SELECTED.value == "selected"


def test_api_key_sandbox_grant_fields():
    grant = ApiKeySandboxGrant()
    assert hasattr(grant, "id")
    assert hasattr(grant, "api_key_id")
    assert hasattr(grant, "sandbox_id")


def test_api_key_helpers():
    secret = "sk-0123456789abcdef"
    assert hash_api_key_secret(secret) != secret
    assert build_api_key_preview(secret) == "sk-0123...cdef"
