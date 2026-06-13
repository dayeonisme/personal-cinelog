from app import app
from database import db
from models import Entry, Hashtag, Movie, RatingModule
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


def create_entry(title, imdb_id, entry_type, rating_name=None):
    movie = Movie(imdb_id=imdb_id, title=title)
    db.session.add(movie)
    db.session.flush()
    entry = Entry(movie_id=movie.id, entry_type=entry_type)
    db.session.add(entry)
    db.session.flush()
    if rating_name:
        db.session.add(
            RatingModule(
                entry_id=entry.id,
                name=rating_name,
                emoji="⭐",
                value=4.0,
                is_default=True,
                order=0,
            )
        )
    return entry


def test_migrate_watcha_hashtag_tags_imported_watcha_reviews_only(tmp_path):
    configure_test_db(tmp_path)

    with app.app_context():
        watcha_review = create_entry("왓챠 평가", "watcha:review", "review", rating_name="왓챠 별점")
        direct_review_on_watcha_movie = create_entry("직접 평가", "watcha:direct-review", "review", rating_name="평점")
        watcha_watchlist = create_entry("왓챠 보고싶어요", "watcha:watchlist", "watchlist")
        tmdb_watchlist = create_entry("TMDb 보고싶어요", "tmdb:watchlist", "watchlist")
        wrong_tag = Hashtag(name="왓챠백업")
        db.session.add(wrong_tag)
        watcha_watchlist.hashtags.append(wrong_tag)
        direct_review_on_watcha_movie.hashtags.append(wrong_tag)
        db.session.commit()

        added, skipped, removed, total = migrate_watcha_hashtag.sync_watcha_backup_hashtag()

        tag = Hashtag.query.filter_by(name="왓챠백업").one()
        assert (added, skipped, removed, total) == (1, 0, 2, 1)
        assert tag in watcha_review.hashtags
        assert tag not in watcha_watchlist.hashtags
        assert tag not in direct_review_on_watcha_movie.hashtags
        assert tag not in tmdb_watchlist.hashtags
