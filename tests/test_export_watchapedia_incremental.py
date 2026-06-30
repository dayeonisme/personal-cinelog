from pathlib import Path

import tools.export_watchapedia as export


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeRequest:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, headers=None):
        self.urls.append(url)
        return FakeResponse(self.responses.pop(0))


class FakePage:
    def __init__(self, responses):
        self.request = FakeRequest(responses)
        self.fallback_used = False

    def wait_for_timeout(self, _ms):
        return None

    def goto(self, url, wait_until=None):
        self.fallback_used = True

    def wait_for_load_state(self, state):
        self.fallback_used = True


def api_payload(codes, next_uri=None):
    return {
        "result": {
            "result": [
                {
                    "content": {
                        "content_type": "movies",
                        "code": code,
                        "title": f"Movie {code}",
                        "year": 2026,
                    },
                    "user_content_action": {"rating": 8},
                }
                for code in codes
            ],
            "next_uri": next_uri,
        }
    }


def test_load_existing_watcha_ids_accepts_prefixed_and_plain_ids(tmp_path):
    path = tmp_path / "known.txt"
    path.write_text("watcha:mKnown\nmPlain\n\n", encoding="utf-8")

    assert export.load_existing_watcha_ids(path) == {"mKnown", "mPlain"}


def test_collect_via_api_stops_after_consecutive_existing_items(monkeypatch):
    monkeypatch.setattr(export, "_capture_frograms_headers", lambda page, kind, url: {"accept": "application/json"})
    monkeypatch.setattr(export, "ensure_logged_in", lambda page: None)
    page = FakePage([
        api_payload(["mOld1", "mOld2"], next_uri="/api/next"),
        api_payload(["mShouldNotFetch"]),
    ])

    rows = export.collect_via_api(
        page,
        "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings",
        existing_ids={"mOld1", "mOld2"},
        stop_after_existing=2,
    )

    assert [row.watcha_content_id for row in rows] == ["mOld1", "mOld2"]
    assert len(page.request.urls) == 1


def test_collect_via_api_continues_when_new_item_resets_existing_streak(monkeypatch):
    monkeypatch.setattr(export, "_capture_frograms_headers", lambda page, kind, url: {"accept": "application/json"})
    monkeypatch.setattr(export, "ensure_logged_in", lambda page: None)
    page = FakePage([
        api_payload(["mOld1", "mNew", "mOld2"], next_uri="/api/next"),
        api_payload(["mOld3", "mOld4"]),
    ])

    rows = export.collect_via_api(
        page,
        "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings",
        existing_ids={"mOld1", "mOld2", "mOld3", "mOld4"},
        stop_after_existing=2,
    )

    assert [row.watcha_content_id for row in rows] == ["mOld1", "mNew", "mOld2", "mOld3", "mOld4"]
    assert len(page.request.urls) == 2


def test_collect_page_movies_api_only_fails_instead_of_scroll_fallback(monkeypatch):
    monkeypatch.setattr(export, "collect_via_api", lambda *args, **kwargs: [])
    monkeypatch.setattr(export, "ensure_logged_in", lambda page: None)
    monkeypatch.setattr(export, "collect_scrolling_movies", lambda *args, **kwargs: [])
    page = FakePage([])

    try:
        export.collect_page_movies(
            page,
            "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings",
            pause_seconds=0,
            stable_rounds=0,
            api_only=True,
        )
    except RuntimeError as exc:
        assert "API 수집 실패" in str(exc)
    else:
        raise AssertionError("api_only should fail instead of falling back to scroll")

    assert page.fallback_used is False
