from app import app
from database import db
from models import Entry, Hashtag, Movie
from tools import migrate_watcha_hashtag


def configure_test_db(tmp_path):
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
    app.config["TESTING"] = True
    app._got_first_request = False
    app.extensions.pop("sqlalchemy", None)
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()


def create_entry(title, imdb_id, entry_type):
    movie = Movie(imdb_id=imdb_id, title=title)
    db.session.add(movie)
    db.session.flush()
    entry = Entry(movie_id=movie.id, entry_type=entry_type)
    db.session.add(entry)
    db.session.flush()
    return entry


def test_migrate_watcha_hashtag_tags_watcha_reviews_and_watchlist(tmp_path):
    configure_test_db(tmp_path)

    with app.app_context():
        watcha_review = create_entry("왓챠 평가", "watcha:review", "review")
        watcha_watchlist = create_entry("왓챠 보고싶어요", "watcha:watchlist", "watchlist")
        tmdb_watchlist = create_entry("TMDb 보고싶어요", "tmdb:watchlist", "watchlist")
        db.session.commit()

        updated, skipped, total = migrate_watcha_hashtag.add_watcha_backup_hashtag()

        tag = Hashtag.query.filter_by(name="왓챠백업").one()
        assert (updated, skipped, total) == (2, 0, 2)
        assert tag in watcha_review.hashtags
        assert tag in watcha_watchlist.hashtags
        assert tag not in tmdb_watchlist.hashtags
