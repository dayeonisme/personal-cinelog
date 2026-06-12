from app import app
from database import db
from models import Entry, Movie, RatingModule

TEST_DB_CONFIGURED = False


def configure_test_db(tmp_path):
    global TEST_DB_CONFIGURED
    if not TEST_DB_CONFIGURED:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
        app.config["TESTING"] = True
        app._got_first_request = False
        app.extensions.pop("sqlalchemy", None)
        db.init_app(app)
        TEST_DB_CONFIGURED = True
    with app.app_context():
        db.drop_all()
        db.create_all()


def create_movie(**kwargs):
    title = kwargs.get("title", "괴물")
    director = kwargs.get("director", "봉준호")
    movie = Movie(
        imdb_id=kwargs.get("imdb_id"),
        title=title,
        title_ko=kwargs.get("title_ko", title),
        title_en=kwargs.get("title_en", "The Host"),
        year=kwargs.get("year", "2006"),
        director=director,
        director_ko=kwargs.get("director_ko", director),
        director_en=kwargs.get("director_en", "Bong Joon Ho"),
    )
    db.session.add(movie)
    db.session.flush()
    return movie


def add_entry(movie, entry_type):
    entry = Entry(
        movie_id=movie.id,
        entry_type=entry_type,
        watch_status="completed" if entry_type == "review" else None,
    )
    db.session.add(entry)
    db.session.flush()
    if entry_type == "review":
        db.session.add(
            RatingModule(
                entry_id=entry.id,
                name="평점",
                emoji="⭐",
                value=4.0,
                is_default=True,
                order=0,
            )
        )
    return entry


def test_watchlist_entries_are_classified_by_review_presence(tmp_path):
    configure_test_db(tmp_path)
    with app.app_context():
        wish_movie = create_movie(imdb_id="tmdb:1", title="미평가 영화")
        rewatch_movie = create_movie(imdb_id="tmdb:2", title="평가한 영화")
        add_entry(wish_movie, "watchlist")
        add_entry(rewatch_movie, "review")
        add_entry(rewatch_movie, "watchlist")
        db.session.commit()

    client = app.test_client()
    all_response = client.get("/api/entries?type=watchlist")
    assert all_response.status_code == 200
    assert all_response.json["total"] == 2
    kinds = {item["movie"]["title"]: item["watchlist_kind"] for item in all_response.json["items"]}
    assert kinds == {
        "미평가 영화": "wish",
        "평가한 영화": "rewatch",
    }

    rewatch_response = client.get("/api/entries?type=watchlist&watchlist_kind=rewatch")
    assert rewatch_response.status_code == 200
    assert rewatch_response.json["total"] == 1
    assert rewatch_response.json["items"][0]["movie"]["title"] == "평가한 영화"
    assert rewatch_response.json["items"][0]["watchlist_label"] == "다시 보고싶어요"


def test_home_scope_hides_watchlist_when_review_exists(tmp_path):
    configure_test_db(tmp_path)
    with app.app_context():
        wish_movie = create_movie(imdb_id="tmdb:1", title="미평가 영화")
        rewatch_movie = create_movie(imdb_id="tmdb:2", title="평가한 영화")
        add_entry(wish_movie, "watchlist")
        add_entry(rewatch_movie, "review")
        add_entry(rewatch_movie, "watchlist")
        db.session.commit()

    client = app.test_client()
    response = client.get("/api/entries?scope=home")
    assert response.status_code == 200
    assert response.json["total"] == 2
    home_types = {item["movie"]["title"]: item["entry_type"] for item in response.json["items"]}
    assert home_types == {
        "미평가 영화": "watchlist",
        "평가한 영화": "review",
    }


def test_movie_response_contains_bilingual_display_fields(tmp_path):
    configure_test_db(tmp_path)
    with app.app_context():
        movie = create_movie(imdb_id="tmdb:1")
        add_entry(movie, "review")
        db.session.commit()

    response = app.test_client().get("/api/entries?type=review&lang=en")
    assert response.status_code == 200
    movie = response.json["items"][0]["movie"]
    assert movie["title"] == "The Host"
    assert movie["director"] == "Bong Joon Ho"
    assert movie["title_ko"] == "괴물"
    assert movie["title_en"] == "The Host"
    assert movie["director_ko"] == "봉준호"
    assert movie["director_en"] == "Bong Joon Ho"


def test_review_default_comment_name_falls_back_to_review_label(tmp_path):
    configure_test_db(tmp_path)

    response = app.test_client().post(
        "/api/entries",
        json={
            "entry_type": "review",
            "movie": {"imdb_id": "tmdb:10", "title": "리뷰 영화"},
            "comments": [{"content": "좋았다", "is_default": True}],
        },
    )

    assert response.status_code == 201
    assert response.json["comments"][0]["name"] == "감상평"


def test_watchlist_default_comment_name_falls_back_to_reason_label(tmp_path):
    configure_test_db(tmp_path)

    response = app.test_client().post(
        "/api/entries",
        json={
            "entry_type": "watchlist",
            "movie": {"imdb_id": "tmdb:11", "title": "보고싶은 영화"},
            "comments": [{"content": "궁금해서", "is_default": True}],
        },
    )

    assert response.status_code == 201
    assert response.json["comments"][0]["name"] == "보고싶은 이유"
