# WatchaPedia Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build local tools that export the user's own WatchaPedia movie ratings/watchlist to CSV and import those CSVs into Cinelog.

**Architecture:** Keep the live web automation and database import as separate tools. Put deterministic parsing/import logic in small modules that can be tested without a browser, then keep Playwright-specific behavior in the exporter script.

**Tech Stack:** Python, Flask-SQLAlchemy models already in the repo, SQLite, pytest, Playwright.

---

## File Structure

- Create `tools/watcha_csv.py`: CSV row parsing, validation, normalization, and result dataclasses.
- Create `tools/import_watcha_csv.py`: CLI importer that uses `watcha_csv.py` and existing Cinelog models.
- Create `tools/export_watchapedia.py`: Playwright exporter that creates `data/watchapedia_ratings.csv` and `data/watchapedia_watchlist.csv`.
- Create `tests/test_watcha_csv.py`: parser and validation tests.
- Create `tests/test_import_watcha_csv.py`: importer tests against a temporary SQLite DB.
- Modify `requirements.txt`: add `pytest` and `playwright`.

### Task 1: CSV Parsing And Validation

**Files:**
- Create: `tools/watcha_csv.py`
- Test: `tests/test_watcha_csv.py`

- [ ] **Step 1: Write the failing parser tests**

```python
from pathlib import Path

import pytest

from tools.watcha_csv import (
    InvalidWatchaCsv,
    parse_ratings_csv,
    parse_watchlist_csv,
    validate_rating_value,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watcha_csv.py -v`

Expected: FAIL because `tools.watcha_csv` does not exist.

- [ ] **Step 3: Implement the parser module**

```python
import csv
from dataclasses import dataclass
from pathlib import Path


class InvalidWatchaCsv(ValueError):
    pass


@dataclass(frozen=True)
class WatchaRatingRow:
    source: str
    title: str
    year: str
    rating: float
    watcha_content_id: str
    watcha_url: str
    imdb_id: str


@dataclass(frozen=True)
class WatchaWatchlistRow:
    source: str
    title: str
    year: str
    watcha_content_id: str
    watcha_url: str
    imdb_id: str


RATING_COLUMNS = {"source", "title", "year", "rating", "watcha_content_id", "watcha_url", "imdb_id"}
WATCHLIST_COLUMNS = {"source", "title", "year", "watcha_content_id", "watcha_url", "imdb_id"}


def normalize_title(title: str) -> str:
    return " ".join((title or "").strip().split()).casefold()


def normalize_year(year: str) -> str:
    return (year or "").strip()


def validate_rating_value(value: str) -> float:
    try:
        rating = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidWatchaCsv(f"invalid rating value: {value}") from exc
    if rating < 0.5 or rating > 5.0 or (rating * 2) % 1 != 0:
        raise InvalidWatchaCsv(f"invalid rating value: {value}")
    return rating


def _read_dicts(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing = required_columns - fieldnames
        if missing:
            raise InvalidWatchaCsv(f"missing required columns: {', '.join(sorted(missing))}")
        return list(reader)


def parse_ratings_csv(path: Path) -> list[WatchaRatingRow]:
    parsed = []
    for row in _read_dicts(path, RATING_COLUMNS):
        title = (row.get("title") or "").strip()
        if not title:
            raise InvalidWatchaCsv("rating row has empty title")
        parsed.append(
            WatchaRatingRow(
                source=(row.get("source") or "watchapedia").strip(),
                title=title,
                year=normalize_year(row.get("year", "")),
                rating=validate_rating_value(row.get("rating", "")),
                watcha_content_id=(row.get("watcha_content_id") or "").strip(),
                watcha_url=(row.get("watcha_url") or "").strip(),
                imdb_id=(row.get("imdb_id") or "").strip(),
            )
        )
    return parsed


def parse_watchlist_csv(path: Path) -> list[WatchaWatchlistRow]:
    parsed = []
    for row in _read_dicts(path, WATCHLIST_COLUMNS):
        title = (row.get("title") or "").strip()
        if not title:
            raise InvalidWatchaCsv("watchlist row has empty title")
        parsed.append(
            WatchaWatchlistRow(
                source=(row.get("source") or "watchapedia").strip(),
                title=title,
                year=normalize_year(row.get("year", "")),
                watcha_content_id=(row.get("watcha_content_id") or "").strip(),
                watcha_url=(row.get("watcha_url") or "").strip(),
                imdb_id=(row.get("imdb_id") or "").strip(),
            )
        )
    return parsed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watcha_csv.py -v`

Expected: PASS.

### Task 2: Cinelog Importer

**Files:**
- Create: `tools/import_watcha_csv.py`
- Test: `tests/test_import_watcha_csv.py`

- [ ] **Step 1: Write importer tests**

```python
from pathlib import Path

from app import app
from database import db
from models import Entry, Movie, RatingModule
from tools.import_watcha_csv import import_watcha_csvs


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def configure_test_db(tmp_path):
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
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
        result = import_watcha_csvs(ratings_csv=ratings, watchlist_csv=watchlist, commit=True)

        assert result.inserted_reviews == 1
        assert result.inserted_watchlist == 0
        assert result.skipped_duplicates == 1
        assert Entry.query.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_watcha_csv.py -v`

Expected: FAIL because `tools.import_watcha_csv` does not exist.

- [ ] **Step 3: Implement importer module**

Create `tools/import_watcha_csv.py`:

```python
import argparse
from dataclasses import dataclass
from pathlib import Path

from app import app
from database import db
from models import Entry, Movie, RatingModule
from tools.watcha_csv import (
    WatchaRatingRow,
    WatchaWatchlistRow,
    normalize_title,
    parse_ratings_csv,
    parse_watchlist_csv,
)


@dataclass
class ImportResult:
    inserted_reviews: int = 0
    inserted_watchlist: int = 0
    skipped_duplicates: int = 0
    invalid_rows: int = 0


def find_movie(imdb_id: str, title: str, year: str) -> Movie | None:
    if imdb_id:
        movie = Movie.query.filter_by(imdb_id=imdb_id).first()
        if movie:
            return movie
    candidates = Movie.query.filter_by(year=year).all() if year else Movie.query.all()
    normalized = normalize_title(title)
    for movie in candidates:
        if normalize_title(movie.title) == normalized:
            return movie
    return None


def get_or_create_movie(row: WatchaRatingRow | WatchaWatchlistRow) -> Movie:
    movie = find_movie(row.imdb_id, row.title, row.year)
    if movie:
        return movie
    movie = Movie(
        imdb_id=row.imdb_id or None,
        title=row.title,
        year=row.year or None,
        poster_url=None,
    )
    db.session.add(movie)
    db.session.flush()
    return movie


def movie_has_entry(movie: Movie, entry_type: str | None = None) -> bool:
    query = Entry.query.filter_by(movie_id=movie.id)
    if entry_type:
        query = query.filter_by(entry_type=entry_type)
    return query.first() is not None


def import_rating(row: WatchaRatingRow, result: ImportResult) -> None:
    movie = get_or_create_movie(row)
    if movie_has_entry(movie, "review"):
        result.skipped_duplicates += 1
        return
    entry = Entry(movie_id=movie.id, entry_type="review", watch_status="completed")
    db.session.add(entry)
    db.session.flush()
    db.session.add(
        RatingModule(
            entry_id=entry.id,
            name="왓챠 별점",
            emoji="⭐",
            value=row.rating,
            is_default=True,
            order=0,
        )
    )
    result.inserted_reviews += 1


def import_watchlist(row: WatchaWatchlistRow, result: ImportResult) -> None:
    movie = get_or_create_movie(row)
    if movie_has_entry(movie):
        result.skipped_duplicates += 1
        return
    db.session.add(Entry(movie_id=movie.id, entry_type="watchlist", watch_status=None))
    result.inserted_watchlist += 1


def import_watcha_csvs(
    ratings_csv: Path | None,
    watchlist_csv: Path | None,
    commit: bool = False,
) -> ImportResult:
    result = ImportResult()
    if ratings_csv:
        for row in parse_ratings_csv(ratings_csv):
            import_rating(row, result)
    if watchlist_csv:
        for row in parse_watchlist_csv(watchlist_csv):
            import_watchlist(row, result)
    if commit:
        db.session.commit()
    else:
        db.session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import WatchaPedia CSV files into Cinelog.")
    parser.add_argument("--ratings", type=Path)
    parser.add_argument("--watchlist", type=Path)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    with app.app_context():
        result = import_watcha_csvs(args.ratings, args.watchlist, commit=args.commit)
    mode = "committed" if args.commit else "dry run"
    print(f"Mode: {mode}")
    print(f"Inserted reviews: {result.inserted_reviews}")
    print(f"Inserted watchlist: {result.inserted_watchlist}")
    print(f"Skipped duplicates: {result.skipped_duplicates}")
    print(f"Invalid rows: {result.invalid_rows}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run importer tests**

Run: `pytest tests/test_import_watcha_csv.py -v`

Expected: PASS.

### Task 3: WatchaPedia Exporter

**Files:**
- Create: `tools/export_watchapedia.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependencies**

Append these lines to `requirements.txt`:

```txt
pytest>=8.0
playwright>=1.44
```

- [ ] **Step 2: Create exporter script**

Create a script with this CLI:

```bash
python tools/export_watchapedia.py --profile-url "https://pedia.watcha.com/ko-KR/users/<USER_ID>/contents/movies" --out-dir data
```

Behavior:

- Use `playwright.sync_api.sync_playwright`.
- Launch persistent Chromium context in `.watchapedia-browser`.
- Open the supplied profile URL.
- Wait for the user to log in if login UI is visible.
- Scroll until no new movie cards are found after three attempts.
- Extract visible cards into candidate rows.
- Write two CSVs with the headers from the design spec.
- Sleep at least one second between scroll attempts.

- [ ] **Step 3: Manual smoke test**

Run:

```bash
python tools/export_watchapedia.py --profile-url "https://pedia.watcha.com/ko-KR/users/<USER_ID>/contents/movies" --out-dir data
```

Expected:

- Browser opens.
- User can log in manually.
- CSV files are created under `data/`.
- No password or cookie values are printed.

### Task 4: End-To-End Verification

**Files:**
- Use generated CSVs in `data/`.
- Use current app DB `movies.db`.

- [ ] **Step 1: Dry run import**

Run:

```bash
python tools/import_watcha_csv.py --ratings data/watchapedia_ratings.csv --watchlist data/watchapedia_watchlist.csv
```

Expected: Prints counts and does not change `movies.db`.

- [ ] **Step 2: Commit import**

Run:

```bash
python tools/import_watcha_csv.py --ratings data/watchapedia_ratings.csv --watchlist data/watchapedia_watchlist.csv --commit
```

Expected: Prints inserted review/watchlist counts.

- [ ] **Step 3: Run local app**

Run:

```bash
python app.py
```

Expected: App starts on `http://localhost:5001`.

- [ ] **Step 4: Verify UI**

Open `http://localhost:5001`.

Expected:

- Imported rated movies appear on the 평가 page.
- Imported watchlist movies appear on the 보고싶어요 page.
- Duplicate rows do not appear after running the import command twice.
