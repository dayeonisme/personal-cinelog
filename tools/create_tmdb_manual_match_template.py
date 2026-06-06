import argparse
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from models import Movie


def rows_for_manual_matching():
    movies = (
        Movie.query.filter(Movie.imdb_id.like("watcha:%"))
        .filter(Movie.tmdb_id.is_(None))
        .order_by(Movie.title)
        .all()
    )
    for movie in movies:
        yield {
            "watcha_id": movie.imdb_id,
            "tmdb_id": "",
            "title_ko": movie.title_ko or movie.title,
            "year": movie.year or "",
            "search_url": f"https://www.themoviedb.org/search/movie?query={movie.title_ko or movie.title}",
            "note": "",
        }


def write_template(out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows_for_manual_matching())
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["watcha_id", "tmdb_id", "title_ko", "year", "search_url", "note"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a CSV template for manually mapping WatchaPedia movies to TMDb IDs."
    )
    parser.add_argument("--out", type=Path, default=Path("data/tmdb_manual_matches.csv"))
    args = parser.parse_args()

    with app.app_context():
        count = write_template(args.out)

    print(f"Wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
