from pathlib import Path

import pytest

from tools.watcha_csv import (
    InvalidWatchaCsv,
    parse_ratings_csv,
    parse_watchlist_csv,
    validate_rating_value,
)
from tools.export_watchapedia import (
    derive_collection_url,
    is_movie_content_link,
)


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_ratings_csv_reads_valid_rows(tmp_path):
    csv_path = write_csv(
        tmp_path / "ratings.csv",
        "source,title,year,rating,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,헤어질 결심,2022,4.5,md123,https://pedia.watcha.com/ko-KR/contents/md123,tt12477480\n",
    )

    rows = parse_ratings_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].title == "헤어질 결심"
    assert rows[0].year == "2022"
    assert rows[0].rating == 4.5
    assert rows[0].imdb_id == "tt12477480"


def test_parse_watchlist_csv_reads_valid_rows(tmp_path):
    csv_path = write_csv(
        tmp_path / "watchlist.csv",
        "source,title,year,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,괴물,2006,md456,https://pedia.watcha.com/ko-KR/contents/md456,tt0468492\n",
    )

    rows = parse_watchlist_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].title == "괴물"
    assert rows[0].year == "2006"
    assert rows[0].watcha_content_id == "md456"


@pytest.mark.parametrize("value", ["0", "5.5", "4.25", "bad"])
def test_validate_rating_value_rejects_invalid_values(value):
    with pytest.raises(InvalidWatchaCsv):
        validate_rating_value(value)


def test_parse_ratings_csv_rejects_missing_headers(tmp_path):
    csv_path = write_csv(tmp_path / "bad.csv", "title,rating\n괴물,4.0\n")

    with pytest.raises(InvalidWatchaCsv, match="missing required columns"):
        parse_ratings_csv(csv_path)


def test_is_movie_content_link_accepts_only_movie_cards():
    assert is_movie_content_link("/ko/contents/md123", "헤어질 결심")
    assert is_movie_content_link("/en/contents/mOllnqg", "Furiosa")
    assert not is_movie_content_link("/ko/users/u/contents/movies", "영화")
    assert not is_movie_content_link("https://watcha.com/contents/m5NnbDR", "")


def test_derive_collection_url_from_profile_url():
    profile = "https://pedia.watcha.com/ko-KR/users/exampleUser123/contents/movies"

    assert derive_collection_url(profile, "ratings") == (
        "https://pedia.watcha.com/ko-KR/users/exampleUser123/contents/movies/ratings"
    )
    assert derive_collection_url(profile, "wishes") == (
        "https://pedia.watcha.com/ko-KR/users/exampleUser123/contents/movies/wishes"
    )
