import app as app_module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_search_movies_uses_tmdb_korean_search(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse(
            {
                "results": [
                    {
                        "id": 550,
                        "title": "파이트 클럽",
                        "original_title": "Fight Club",
                        "release_date": "1999-10-15",
                        "poster_path": "/poster.jpg",
                    }
                ]
            }
        )

    monkeypatch.setattr(app_module, "TMDB_ACCESS_TOKEN", "token")
    monkeypatch.setattr(app_module.requests, "get", fake_get)

    client = app_module.app.test_client()
    response = client.get("/api/search/movies?q=파이트 클럽")

    assert response.status_code == 200
    assert calls[0]["url"] == "https://api.themoviedb.org/3/search/movie"
    assert calls[0]["params"]["query"] == "파이트 클럽"
    assert calls[0]["params"]["language"] == "ko-KR"
    assert calls[0]["params"]["region"] == "KR"
    assert calls[0]["params"]["include_adult"] == "false"
    assert calls[0]["headers"]["Authorization"] == "Bearer token"
    assert response.json == [
        {
            "imdb_id": "tmdb:550",
            "title": "파이트 클럽",
            "title_ko": "파이트 클럽",
            "title_en": "Fight Club",
            "year": "1999",
            "poster_url": "https://image.tmdb.org/t/p/w342/poster.jpg",
        }
    ]


def test_get_movie_detail_uses_tmdb_korean_details(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse(
            {
                "id": 550,
                "imdb_id": "tt0137523",
                "title": "파이트 클럽",
                "original_title": "Fight Club",
                "release_date": "1999-10-15",
                "overview": "불면증에 시달리는 남자의 이야기.",
                "poster_path": "/poster.jpg",
                "genres": [{"name": "드라마"}, {"name": "스릴러"}],
                "runtime": 139,
                "credits": {
                    "crew": [{"job": "Director", "name": "David Fincher", "original_name": "David Fincher"}],
                    "cast": [{"name": "Brad Pitt"}, {"name": "Edward Norton"}],
                },
                "external_ids": {"imdb_id": "tt0137523"},
            }
        )

    monkeypatch.setattr(app_module, "TMDB_ACCESS_TOKEN", "token")
    monkeypatch.setattr(app_module.requests, "get", fake_get)

    client = app_module.app.test_client()
    response = client.get("/api/search/movies/tmdb:550")

    assert response.status_code == 200
    assert calls[0]["url"] == "https://api.themoviedb.org/3/movie/550"
    assert calls[0]["params"]["language"] == "ko-KR"
    assert calls[0]["params"]["append_to_response"] == "credits,external_ids"
    assert response.json["imdb_id"] == "tmdb:550"
    assert response.json["external_imdb_id"] == "tt0137523"
    assert response.json["title"] == "파이트 클럽"
    assert response.json["title_ko"] == "파이트 클럽"
    assert response.json["title_en"] == "Fight Club"
    assert response.json["year"] == "1999"
    assert response.json["director"] == "David Fincher"
    assert response.json["director_ko"] == "David Fincher"
    assert response.json["director_en"] == "David Fincher"
    assert response.json["actors"] == "Brad Pitt, Edward Norton"
    assert response.json["genre"] == "드라마, 스릴러"
    assert response.json["runtime"] == "139 min"
