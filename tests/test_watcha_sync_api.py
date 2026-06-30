import app as app_module


class FakeSystemctlResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_watcha_sync_status_explains_unavailable_systemd(monkeypatch):
    monkeypatch.setattr(app_module, "_systemctl", lambda args: None)

    response = app_module.app.test_client().get("/api/watcha/sync/status")

    assert response.status_code == 200
    assert response.json["available"] is False
    assert response.json["running"] is False
    assert "systemd" in response.json["detail"]


def test_watcha_sync_status_includes_failed_unit_details(monkeypatch):
    def fake_systemctl(args):
        if args == ["is-active", app_module.WATCHA_SYNC_SERVICE]:
            return FakeSystemctlResult(stdout="failed\n", returncode=3)
        if args[0] == "show":
            return FakeSystemctlResult(
                stdout=(
                    "Result=exit-code\n"
                    "ExecMainStatus=1\n"
                    "InactiveEnterTimestamp=Tue 2026-06-30 21:40:00 KST\n"
                )
            )
        raise AssertionError(args)

    monkeypatch.setattr(app_module, "_systemctl", fake_systemctl)

    response = app_module.app.test_client().get("/api/watcha/sync/status")

    assert response.status_code == 200
    assert response.json["available"] is True
    assert response.json["running"] is False
    assert response.json["state"] == "failed"
    assert response.json["result"] == "exit-code"
    assert response.json["exec_main_status"] == "1"
    assert "journalctl -u cinelog-watcha-sync" in response.json["detail"]
