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


RATING_COLUMNS = {
    "source",
    "title",
    "year",
    "rating",
    "watcha_content_id",
    "watcha_url",
    "imdb_id",
}
WATCHLIST_COLUMNS = {
    "source",
    "title",
    "year",
    "watcha_content_id",
    "watcha_url",
    "imdb_id",
}


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


def _read_dicts(path: Path, required_columns: set) -> list:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing = required_columns - fieldnames
        if missing:
            raise InvalidWatchaCsv(
                f"missing required columns: {', '.join(sorted(missing))}"
            )
        return list(reader)


def parse_ratings_csv(path: Path) -> list:
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


def parse_watchlist_csv(path: Path) -> list:
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
