from treadstone.models.user import Invitation, OAuthAccount, Role, User


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


def test_role_enum_values():
    assert Role.ADMIN.value == "admin"
    assert Role.RW.value == "rw"
    assert Role.RO.value == "ro"


def test_invitation_is_valid(freezer):
    from datetime import datetime, timedelta, timezone

    inv = Invitation()
    inv.is_used = False
    inv.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    assert inv.is_valid() is True


def test_invitation_expired_is_invalid(freezer):
    from datetime import datetime, timedelta, timezone

    inv = Invitation()
    inv.is_used = False
    inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    assert inv.is_valid() is False


def test_invitation_used_is_invalid(freezer):
    from datetime import datetime, timedelta, timezone

    inv = Invitation()
    inv.is_used = True
    inv.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    assert inv.is_valid() is False
