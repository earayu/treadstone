def test_verifier_is_none_when_cookie_mode(monkeypatch):
    monkeypatch.setenv("TREADSTONE_AUTH_TYPE", "cookie")
    from importlib import reload

    import treadstone.config as cfg

    reload(cfg)
    import treadstone.auth as auth_mod

    reload(auth_mod)
    assert auth_mod.tv is None


def test_verifier_is_none_when_none_mode(monkeypatch):
    monkeypatch.setenv("TREADSTONE_AUTH_TYPE", "none")
    from importlib import reload

    import treadstone.config as cfg

    reload(cfg)
    import treadstone.auth as auth_mod

    reload(auth_mod)
    assert auth_mod.tv is None
