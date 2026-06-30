import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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
    updated_reviews: int = 0
    inserted_watchlist: int = 0
    skipped_duplicates: int = 0
    invalid_rows: int = 0


def find_movie(imdb_id: str, title: str, year: str) -> Optional[Movie]:
    local_id = make_local_movie_id(imdb_id, "")
    if local_id:
        movie = Movie.query.filter_by(imdb_id=local_id).first()
        if movie:
            return movie

    query = Movie.query
    if year:
        query = query.filter_by(year=year)

    normalized = normalize_title(title)
    for movie in query.all():
        if normalize_title(movie.title) == normalized:
            return movie
    return None


def make_local_movie_id(imdb_id: str, watcha_content_id: str) -> Optional[str]:
    if imdb_id:
        return imdb_id
    if watcha_content_id:
        return f"watcha:{watcha_content_id}"
    return None


def get_or_create_movie(row: Union[WatchaRatingRow, WatchaWatchlistRow]) -> Movie:
    local_id = make_local_movie_id(row.imdb_id, row.watcha_content_id)
    if local_id:
        movie = Movie.query.filter_by(imdb_id=local_id).first()
        if movie:
            return movie
        if not row.imdb_id:
            movie = None
        else:
            movie = find_movie(row.imdb_id, row.title, row.year)
    else:
        movie = find_movie(row.imdb_id, row.title, row.year)

    if movie:
        return movie

    movie = Movie(
        imdb_id=local_id,
        title=row.title,
        title_ko=row.title,
        title_en=row.title,
        year=row.year or None,
        poster_url=None,
    )
    db.session.add(movie)
    db.session.flush()
    return movie


def movie_has_entry(movie: Movie, entry_type: Optional[str] = None) -> bool:
    query = Entry.query.filter_by(movie_id=movie.id)
    if entry_type:
        query = query.filter_by(entry_type=entry_type)
    return query.first() is not None


def existing_entry(movie: Movie, entry_type: str) -> Optional[Entry]:
    return Entry.query.filter_by(movie_id=movie.id, entry_type=entry_type).first()


def import_rating(row: WatchaRatingRow, result: ImportResult) -> None:
    movie = get_or_create_movie(row)
    entry = existing_entry(movie, "review")
    if entry:
        watcha_rating = RatingModule.query.filter_by(
            entry_id=entry.id,
            name="왓챠 별점",
        ).first()
        if watcha_rating and watcha_rating.value != row.rating:
            watcha_rating.value = row.rating
            entry.updated_at = datetime.utcnow()
            result.updated_reviews += 1
        else:
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
    if movie_has_entry(movie, "watchlist"):
        result.skipped_duplicates += 1
        return

    db.session.add(Entry(movie_id=movie.id, entry_type="watchlist", watch_status=None))
    result.inserted_watchlist += 1


def import_watcha_csvs(
    ratings_csv: Optional[Path],
    watchlist_csv: Optional[Path],
    commit: bool = False,
) -> ImportResult:
    result = ImportResult()

    if ratings_csv:
        seen_rating_keys = set()
        for row in parse_ratings_csv(ratings_csv):
            row_key = make_local_movie_id(row.imdb_id, row.watcha_content_id) or f"{normalize_title(row.title)}:{row.year}"
            if row_key in seen_rating_keys:
                result.skipped_duplicates += 1
                continue
            seen_rating_keys.add(row_key)
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
    parser = argparse.ArgumentParser(
        description="Import WatchaPedia CSV files into Cinelog."
    )
    parser.add_argument("--ratings", type=Path)
    parser.add_argument("--watchlist", type=Path)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    with app.app_context():
        result = import_watcha_csvs(args.ratings, args.watchlist, commit=args.commit)

    mode = "committed" if args.commit else "dry run"
    print(f"Mode: {mode}")
    print(f"Inserted reviews: {result.inserted_reviews}")
    print(f"Updated reviews: {result.updated_reviews}")
    print(f"Inserted watchlist: {result.inserted_watchlist}")
    print(f"Skipped duplicates: {result.skipped_duplicates}")
    print(f"Invalid rows: {result.invalid_rows}")


if __name__ == "__main__":
    main()
