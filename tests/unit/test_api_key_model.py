from treadstone.models.api_key import ApiKey


def test_api_key_fields():
    k = ApiKey()
    assert hasattr(k, "id")
    assert hasattr(k, "key")
    assert hasattr(k, "user_id")
    assert hasattr(k, "name")


def test_api_key_soft_delete_defaults_none():
    k = ApiKey()
    assert k.gmt_deleted is None
