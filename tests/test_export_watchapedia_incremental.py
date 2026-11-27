from pathlib import Path

import tools.export_watchapedia as export


class FakePage:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.fallback_used = False

    def evaluate(self, _script, args):
        url, _headers = args
        self.urls.append(url)
        return {'status': 200, 'body': self.responses.pop(0)}

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


def test_watcha_api_header_filter_keeps_browser_context_headers():
    headers = export.watcha_api_headers({
        "accept": "application/json",
        "accept-language": "ko-KR,ko;q=0.9",
        "user-agent": "Mozilla/5.0",
        "referer": "https://pedia.watcha.com/ko-KR/users/u/contents/movies/ratings",
        "x-frograms-app-code": "watcha_web",
        "cookie": "session=secret",
        "host": "pedia.watcha.com",
        "content-length": "0",
    })

    assert headers == {
        "accept": "application/json",
        "accept-language": "ko-KR,ko;q=0.9",
        "user-agent": "Mozilla/5.0",
        "referer": "https://pedia.watcha.com/ko-KR/users/u/contents/movies/ratings",
        "x-frograms-app-code": "watcha_web",
        "cookie": "session=secret",
    }


def test_collect_via_api_stops_after_consecutive_existing_items(monkeypatch):
    monkeypatch.setattr(
        export,
        "_capture_api_seed",
        lambda page, kind, url: ({"accept": "application/json"}, api_payload(["mOld1", "mOld2"], next_uri="/api/next")),
    )
    page = FakePage([
        api_payload(["mShouldNotFetch"]),
    ])

    rows = export.collect_via_api(
        page,
        "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings",
        existing_ids={"mOld1", "mOld2"},
        stop_after_existing=2,
    )

    assert [row.watcha_content_id for row in rows] == ["mOld1", "mOld2"]
    assert len(page.urls) == 0


def test_collect_via_api_continues_when_new_item_resets_existing_streak(monkeypatch):
    monkeypatch.setattr(
        export,
        "_capture_api_seed",
        lambda page, kind, url: ({"accept": "application/json"}, api_payload(["mOld1", "mNew", "mOld2"], next_uri="/api/next")),
    )
    page = FakePage([
        api_payload(["mOld3", "mOld4"]),
    ])

    rows = export.collect_via_api(
        page,
        "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings",
        existing_ids={"mOld1", "mOld2", "mOld3", "mOld4"},
        stop_after_existing=2,
    )

    assert [row.watcha_content_id for row in rows] == ["mOld1", "mNew", "mOld2", "mOld3", "mOld4"]
    assert page.urls == ['https://pedia.watcha.com/api/next']


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


class FakeRequest:
    def __init__(self, url, headers):
        self.url = url
        self.headers = headers


def test_is_watcha_app_api_request_requires_frograms_headers():
    app_headers = {"accept": "application/json", "x-frograms-client": "Galaxy-Web-App"}

    assert export._is_watcha_app_api_request(
        FakeRequest("https://pedia.watcha.com/api/notifications/unread", app_headers)
    )
    assert not export._is_watcha_app_api_request(
        FakeRequest("https://pedia.watcha.com/api/legals", {"accept": "application/json"})
    )
    assert not export._is_watcha_app_api_request(
        FakeRequest("https://sentry.io/api/267909/envelope/", app_headers)
    )


def test_collection_api_url_uses_redesigned_endpoint():
    assert export.collection_api_url("u1", "wishes") == (
        "https://pedia.watcha.com/api/users/u1/wishes/movie"
        "?page=1&size=30&sort_direction=desc&sort_option=acted_at"
    )


class SeedPage:
    """첫 goto 는 타임아웃, 두 번째에 앱 API 요청이 잡히는 페이지."""

    def __init__(self, fetch_results):
        self.calls = 0
        self.urls = []
        self.fetched = []
        self.fetch_results = list(fetch_results)

    def expect_request(self, predicate, timeout):
        page = self

        class Waiter:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                page.calls += 1
                if page.calls == 1:
                    raise TimeoutError("no request")
                return False

            @property
            def value(self):
                req = FakeRequest(
                    "https://pedia.watcha.com/api/notifications/unread",
                    {"accept": "application/json", "x-frograms-client": "Galaxy-Web-App", "host": "x"},
                )
                assert predicate(req)
                return req

        return Waiter()

    def goto(self, url, wait_until="load", timeout=None):
        self.urls.append(url)

    def evaluate(self, _script, args):
        url, headers = args
        self.fetched.append((url, headers))
        return self.fetch_results.pop(0)

    def wait_for_timeout(self, _ms):
        return None


def test_capture_api_seed_captures_headers_then_fetches_first_page(monkeypatch):
    monkeypatch.setattr(export, "ensure_logged_in", lambda page: None)
    first_page = api_payload(["mNew"], next_uri="/api/users/u1/ratings/movie?page=2")
    page = SeedPage([{"status": 200, "body": first_page}])

    headers, payload = export._capture_api_seed(
        page, "ratings", "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/ratings"
    )

    assert page.calls == 2
    assert "about:blank" in page.urls
    assert headers == {"accept": "application/json", "x-frograms-client": "Galaxy-Web-App"}
    assert payload == first_page
    assert page.fetched == [(export.collection_api_url("u1", "ratings"), headers)]


def test_capture_api_seed_returns_no_payload_on_403(monkeypatch):
    monkeypatch.setattr(export, "ensure_logged_in", lambda page: None)
    page = SeedPage([{"status": 403, "body": None}] * 3)
    page.calls = 1  # 첫 캡처부터 성공

    headers, payload = export._capture_api_seed(
        page, "wishes", "https://pedia.watcha.com/ko-KR/users/u1/contents/movies/wishes"
    )

    assert headers
    assert payload is None
    assert len(page.fetched) == 3
