import app as app_module


def test_server_options_default_to_debug_off(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    assert app_module.server_options() == {
        "host": "127.0.0.1",
        "port": 5001,
        "debug": False,
    }


def test_server_options_allow_explicit_debug(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "5100")
    monkeypatch.setenv("FLASK_DEBUG", "1")

    assert app_module.server_options() == {
        "host": "0.0.0.0",
        "port": 5100,
        "debug": True,
    }
