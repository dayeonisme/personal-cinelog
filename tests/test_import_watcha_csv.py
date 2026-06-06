from pathlib import Path

from app import app
from database import db
from models import Entry, Movie, RatingModule
from tools.import_watcha_csv import import_watcha_csvs

TEST_DB_CONFIGURED = False


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def configure_test_db(tmp_path):
    global TEST_DB_CONFIGURED
    if not TEST_DB_CONFIGURED:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
        app.extensions.pop("sqlalchemy", None)
        db.init_app(app)
        TEST_DB_CONFIGURED = True
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_import_creates_review_with_watcha_rating(tmp_path):
    configure_test_db(tmp_path)
    ratings = write_csv(
        tmp_path / "ratings.csv",
        "source,title,year,rating,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,헤어질 결심,2022,4.5,md123,https://pedia.watcha.com/ko-KR/contents/md123,tt12477480\n",
    )

    with app.app_context():
        result = import_watcha_csvs(ratings_csv=ratings, watchlist_csv=None, commit=True)

        assert result.inserted_reviews == 1
        entry = Entry.query.one()
        assert entry.entry_type == "review"
        assert entry.watch_status == "completed"
        assert entry.movie.title == "헤어질 결심"
        rating = RatingModule.query.one()
        assert rating.name == "왓챠 별점"
        assert rating.value == 4.5


def test_import_skips_duplicate_review_by_imdb_id(tmp_path):
    configure_test_db(tmp_path)
    ratings = write_csv(
        tmp_path / "ratings.csv",
        "source,title,year,rating,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,헤어질 결심,2022,4.5,md123,https://pedia.watcha.com/ko-KR/contents/md123,tt12477480\n"
        "watchapedia,Decision to Leave,2022,5.0,md123,https://pedia.watcha.com/ko-KR/contents/md123,tt12477480\n",
    )

    with app.app_context():
        result = import_watcha_csvs(ratings_csv=ratings, watchlist_csv=None, commit=True)

        assert result.inserted_reviews == 1
        assert result.skipped_duplicates == 1
        assert Entry.query.count() == 1
        assert Movie.query.count() == 1


def test_import_keeps_same_title_movies_with_different_watcha_ids(tmp_path):
    configure_test_db(tmp_path)
    ratings = write_csv(
        tmp_path / "ratings.csv",
        "source,title,year,rating,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,괴물,,3.5,mOopwPa,https://pedia.watcha.com/ko/contents/mOopwPa,\n"
        "watchapedia,괴물,,4.0,mOPooYW,https://pedia.watcha.com/ko/contents/mOPooYW,\n",
    )

    with app.app_context():
        result = import_watcha_csvs(ratings_csv=ratings, watchlist_csv=None, commit=True)

        assert result.inserted_reviews == 2
        assert result.skipped_duplicates == 0
        assert Entry.query.count() == 2
        assert Movie.query.count() == 2
        assert {movie.imdb_id for movie in Movie.query.all()} == {
            "watcha:mOopwPa",
            "watcha:mOPooYW",
        }


def test_import_skips_watchlist_when_review_exists(tmp_path):
    configure_test_db(tmp_path)
    ratings = write_csv(
        tmp_path / "ratings.csv",
        "source,title,year,rating,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,괴물,2006,4.0,md456,https://pedia.watcha.com/ko-KR/contents/md456,tt0468492\n",
    )
    watchlist = write_csv(
        tmp_path / "watchlist.csv",
        "source,title,year,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,괴물,2006,md456,https://pedia.watcha.com/ko-KR/contents/md456,tt0468492\n",
    )

    with app.app_context():
        result = import_watcha_csvs(
            ratings_csv=ratings,
            watchlist_csv=watchlist,
            commit=True,
        )

        assert result.inserted_reviews == 1
        assert result.inserted_watchlist == 1
        assert result.skipped_duplicates == 0
        assert Entry.query.count() == 2


def test_import_skips_duplicate_watchlist_for_same_movie(tmp_path):
    configure_test_db(tmp_path)
    watchlist = write_csv(
        tmp_path / "watchlist.csv",
        "source,title,year,watcha_content_id,watcha_url,imdb_id\n"
        "watchapedia,괴물,2006,md456,https://pedia.watcha.com/ko-KR/contents/md456,tt0468492\n"
        "watchapedia,괴물,2006,md456,https://pedia.watcha.com/ko-KR/contents/md456,tt0468492\n",
    )

    with app.app_context():
        result = import_watcha_csvs(
            ratings_csv=None,
            watchlist_csv=watchlist,
            commit=True,
        )

        assert result.inserted_watchlist == 1
        assert result.skipped_duplicates == 1
        assert Entry.query.count() == 1
