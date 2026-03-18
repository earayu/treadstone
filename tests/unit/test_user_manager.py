from treadstone.core.users import (
    UserManager,
    auth_backend,
    cookie_transport,
    fastapi_users,
    get_jwt_strategy,
)


def test_user_manager_class_exists():
    assert UserManager is not None


def test_auth_backend_name():
    assert auth_backend.name == "cookie"


def test_cookie_transport_config():
    assert cookie_transport.cookie_name == "session"
    assert cookie_transport.cookie_max_age == 86400


def test_jwt_strategy_lifetime():
    strategy = get_jwt_strategy()
    assert strategy.lifetime_seconds == 86400


def test_fastapi_users_instance():
    assert fastapi_users is not None
