import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from models import Movie


def extract_directors_from_text(text: str) -> list:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    directors = []
    for index, line in enumerate(lines):
        if line == "감독" and index > 0:
            name = lines[index - 1]
            if name not in directors:
                directors.append(name)
    return directors


def extract_detail_year_from_text(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        match = re.match(r"^(19\d{2}|20\d{2})\s*·", line)
        if match:
            return match.group(1)
    return ""


def watchapedia_url(watcha_id: str) -> str:
    content_id = watcha_id.split(":", 1)[1] if ":" in watcha_id else watcha_id
    return f"https://pedia.watcha.com/ko-KR/contents/{content_id}"


def target_movies(limit: int = None) -> list:
    query = (
        Movie.query.filter(Movie.imdb_id.like("watcha:%"))
        .filter(Movie.tmdb_id.is_(None))
        .order_by(Movie.title)
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def collect_hints(out: Path, limit: int = None, pause: float = 0.2) -> int:
    from playwright.sync_api import sync_playwright

    movies = target_movies(limit=limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = str((ROOT_DIR / ".watchapedia-browser").resolve())

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()

        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "movie_id",
                    "watcha_id",
                    "title_ko",
                    "year",
                    "watcha_url",
                    "directors",
                    "status",
                    "error",
                ],
            )
            writer.writeheader()

            for index, movie in enumerate(movies, start=1):
                url = watchapedia_url(movie.imdb_id)
                status = "ok"
                error = ""
                directors = []
                detail_year = movie.year or ""
                try:
                    page.goto(url, wait_until="networkidle")
                    text = page.locator("body").inner_text(timeout=8000)
                    directors = extract_directors_from_text(text)
                    detail_year = extract_detail_year_from_text(text) or detail_year
                except Exception as exc:
                    status = "error"
                    error = str(exc)

                writer.writerow(
                    {
                        "movie_id": movie.id,
                        "watcha_id": movie.imdb_id,
                        "title_ko": movie.title_ko or movie.title,
                        "year": detail_year,
                        "watcha_url": url,
                        "directors": "|".join(directors),
                        "status": status,
                        "error": error,
                    }
                )
                print(f"{index}/{len(movies)} {movie.title}: {', '.join(directors) or '-'}")
                if pause:
                    time.sleep(pause)

        context.close()

    return len(movies)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect WatchaPedia detail hints such as directors for unmatched movies."
    )
    parser.add_argument("--out", type=Path, default=Path("data/watchapedia_detail_hints.csv"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pause", type=float, default=0.2)
    args = parser.parse_args()

    with app.app_context():
        count = collect_hints(out=args.out, limit=args.limit, pause=args.pause)

    print(f"Wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
