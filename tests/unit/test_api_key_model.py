from treadstone.models.api_key import ApiKey, build_api_key_preview, hash_api_key_secret


def test_api_key_fields():
    k = ApiKey()
    assert hasattr(k, "id")
    assert hasattr(k, "key_hash")
    assert hasattr(k, "key_preview")
    assert hasattr(k, "user_id")
    assert hasattr(k, "name")


def test_api_key_soft_delete_defaults_none():
    k = ApiKey()
    assert k.gmt_deleted is None


def test_api_key_helpers():
    secret = "sk-0123456789abcdef"
    assert hash_api_key_secret(secret) != secret
    assert build_api_key_preview(secret) == "sk-0123...cdef"
