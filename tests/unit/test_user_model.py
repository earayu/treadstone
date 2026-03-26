from treadstone.models.user import OAuthAccount, Role, User


def test_user_fields_exist():
    u = User()
    assert hasattr(u, "id")
    assert hasattr(u, "email")
    assert hasattr(u, "hashed_password")
    assert hasattr(u, "role")
    assert hasattr(u, "is_active")
    assert hasattr(u, "is_superuser")
    assert hasattr(u, "is_verified")


def test_oauth_account_fields_exist():
    o = OAuthAccount()
    assert hasattr(o, "id")
    assert hasattr(o, "user_id")
    assert hasattr(o, "oauth_name")
    assert hasattr(o, "access_token")
    assert any(
        constraint.name == "uq_oauth_account_provider_account" for constraint in OAuthAccount.__table__.constraints
    )
    assert any(constraint.name == "uq_oauth_account_user_provider" for constraint in OAuthAccount.__table__.constraints)


def test_role_enum_values():
    assert Role.ADMIN.value == "admin"
    assert Role.RW.value == "rw"
    assert Role.RO.value == "ro"
