from tools.enrich_tmdb_metadata import (
    apply_manual_matches,
    canonical_title,
    choose_match,
    detail_to_updates,
    search_queries_for_title,
    search_unique_title_year_match,
    poster_url,
)
import tools.enrich_tmdb_metadata as enrichment


class FakeMovie:
    def __init__(self):
        self.imdb_id = "watcha:m123"
        self.title = "곡성(哭聲)"
        self.title_ko = "곡성(哭聲)"
        self.title_en = "곡성(哭聲)"
        self.tmdb_id = None
        self.poster_url = None
        self.director = None
        self.director_ko = None
        self.director_en = None
        self.year = None
        self.plot = None
        self.genre = None
        self.runtime = None


def test_choose_match_accepts_exact_korean_title_without_year():
    result = choose_match(
        title="트레인스포팅",
        year=None,
        results=[
            {
                "id": 627,
                "title": "트레인스포팅",
                "original_title": "Trainspotting",
                "release_date": "1996-02-23",
            }
        ],
    )

    assert result is not None
    assert result.tmdb_id == 627
    assert result.score == 85
    assert result.reason == "exact_title"


def test_choose_match_rejects_non_exact_title():
    result = choose_match(
        title="괴물",
        year=None,
        results=[
            {
                "id": 1091,
                "title": "괴물 2",
                "original_title": "The Thing",
                "release_date": "1982-06-25",
            }
        ],
    )

    assert result is None


def test_canonical_title_removes_spacing_punctuation_and_hanja_parentheses():
    assert canonical_title("곡성(哭聲)") == "곡성"
    assert canonical_title("듄: 파트2") == "듄파트2"
    assert canonical_title("해리포터와 죽음의 성물 2부") == "해리포터와죽음의성물2"
    assert canonical_title("2046 리마스터링") == "2046"


def test_search_queries_for_title_includes_safe_title_variants():
    assert search_queries_for_title("곡성(哭聲)")[:2] == ["곡성(哭聲)", "곡성"]
    assert "2046" in search_queries_for_title("2046 리마스터링")


def test_choose_match_accepts_canonical_title_match():
    result = choose_match(
        title="듄: 파트2",
        year=None,
        results=[
            {
                "id": 693134,
                "title": "듄: 파트 2",
                "original_title": "Dune: Part Two",
                "release_date": "2024-02-27",
            }
        ],
    )

    assert result is not None
    assert result.tmdb_id == 693134
    assert result.score == 90
    assert result.reason == "canonical_title"


def test_choose_match_prefers_matching_year():
    result = choose_match(
        title="괴물",
        year="2006",
        results=[
            {
                "id": 1091,
                "title": "괴물",
                "original_title": "The Thing",
                "release_date": "1982-06-25",
            },
            {
                "id": 1255,
                "title": "괴물",
                "original_title": "The Host",
                "release_date": "2006-07-27",
            },
        ],
    )

    assert result is not None
    assert result.tmdb_id == 1255
    assert result.score == 100
    assert result.reason == "exact_title_year"


def test_search_unique_title_year_match_accepts_single_year_match(monkeypatch):
    monkeypatch.setattr(
        "tools.enrich_tmdb_metadata.search_movie",
        lambda query, year, retries: {
            "results": [
                {
                    "id": 12445,
                    "title": "해리 포터와 죽음의 성물 2",
                    "original_title": "Harry Potter and the Deathly Hallows: Part 2",
                    "release_date": "2011-07-12",
                }
            ]
        },
    )

    result = search_unique_title_year_match("해리포터와 죽음의 성물 2", "2011", retries=0)

    assert result is not None
    assert result.tmdb_id == 12445


def test_search_unique_title_year_match_rejects_multiple_year_matches(monkeypatch):
    monkeypatch.setattr(
        "tools.enrich_tmdb_metadata.search_movie",
        lambda query, year, retries: {
            "results": [
                {
                    "id": 1,
                    "title": "사구",
                    "original_title": "Dune",
                    "release_date": "1984-12-14",
                },
                {
                    "id": 2,
                    "title": "사구",
                    "original_title": "Dune",
                    "release_date": "1984-01-01",
                },
            ]
        },
    )

    result = search_unique_title_year_match("사구", "1984", retries=0)

    assert result is None


def test_detail_to_updates_extracts_poster_and_bilingual_metadata():
    updates = detail_to_updates(
        {
            "id": 1255,
            "title": "괴물",
            "original_title": "The Host",
            "release_date": "2006-07-27",
            "overview": "한강에 나타난 괴물.",
            "poster_path": "/poster.jpg",
            "genres": [{"name": "드라마"}, {"name": "SF"}],
            "runtime": 119,
            "credits": {
                "crew": [
                    {
                        "job": "Director",
                        "name": "봉준호",
                        "original_name": "Bong Joon Ho",
                    }
                ]
            },
        }
    )

    assert updates["tmdb_id"] == "1255"
    assert updates["title_ko"] == "괴물"
    assert updates["title_en"] == "The Host"
    assert updates["director_ko"] == "봉준호"
    assert updates["director_en"] == "Bong Joon Ho"
    assert updates["poster_url"] == poster_url("/poster.jpg")
    assert updates["genre"] == "드라마, SF"
    assert updates["runtime"] == "119 min"


def test_apply_manual_matches_updates_movies_from_csv(tmp_path, monkeypatch):
    movie = FakeMovie()
    manual_csv = tmp_path / "manual_matches.csv"
    manual_csv.write_text("watcha_id,tmdb_id\nwatcha:m123,293670\n", encoding="utf-8")

    class FakeQuery:
        def filter_by(self, imdb_id):
            assert imdb_id == "watcha:m123"
            return self

        def first(self):
            return movie

    class FakeSession:
        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    fake_session = FakeSession()

    class FakeMovieModel:
        query = FakeQuery()

    monkeypatch.setattr(enrichment, "Movie", FakeMovieModel)
    monkeypatch.setattr(enrichment.db, "session", fake_session)
    monkeypatch.setattr(
        "tools.enrich_tmdb_metadata.get_movie_detail",
        lambda tmdb_id, retries: {
            "id": tmdb_id,
            "title": "곡성",
            "original_title": "The Wailing",
            "release_date": "2016-05-12",
            "poster_path": "/wailing.jpg",
            "runtime": 156,
            "genres": [{"name": "공포"}],
            "credits": {
                "crew": [
                    {
                        "job": "Director",
                        "name": "나홍진",
                        "original_name": "Na Hong-jin",
                    }
                ]
            },
        },
    )

    result = apply_manual_matches(
        manual_csv=manual_csv,
        commit=True,
        report_path=tmp_path / "manual_report.csv",
        retries=0,
    )

    assert result.checked == 1
    assert result.updated == 1
    assert movie.tmdb_id == "293670"
    assert movie.title == "곡성"
    assert movie.title_en == "The Wailing"
    assert movie.director_ko == "나홍진"
    assert movie.poster_url == poster_url("/wailing.jpg")
    assert fake_session.committed is True
