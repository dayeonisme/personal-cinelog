import pytest

import tools.enrich_via_watcha_detail as detail


class FakePage:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def evaluate(self, script, args):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(detail.time, "sleep", lambda _: None)


def test_watcha_detail_returns_result_on_200():
    page = FakePage([{"status": 200, "body": {"result": {"title": "이유없는 반항", "year": 1955}}}])

    assert detail._watcha_detail(page, {}, "mY5Qp8d") == {"title": "이유없는 반항", "year": 1955}


def test_watcha_detail_returns_none_for_missing_content():
    page = FakePage([{"status": 404, "body": None}])

    assert detail._watcha_detail(page, {}, "gone") is None
    assert page.calls == 1


def test_watcha_detail_retries_when_blocked_then_succeeds():
    page = FakePage([{"status": 403, "body": None}, {"status": 200, "body": {"result": {"year": 1955}}}])

    assert detail._watcha_detail(page, {}, "mY5Qp8d") == {"year": 1955}
    assert page.calls == 2


def test_watcha_detail_raises_when_block_persists():
    page = FakePage([{"status": 403, "body": None}] * 3)

    with pytest.raises(detail.WatchaBlocked):
        detail._watcha_detail(page, {}, "mY5Qp8d")
