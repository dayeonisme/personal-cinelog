import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app, TMDB_ACCESS_TOKEN, TMDB_API_BASE, TMDB_API_KEY, _tmdb_headers, _tmdb_params
from database import db
from models import Movie
from tools.watcha_csv import normalize_title

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"


@dataclass
class MatchResult:
    tmdb_id: int
    score: int
    reason: str
    item: Dict


@dataclass
class EnrichResult:
    checked: int = 0
    updated: int = 0
    skipped_low_confidence: int = 0
    not_found: int = 0
    errors: int = 0


def poster_url(path: Optional[str]) -> Optional[str]:
    return f"{TMDB_IMAGE_BASE}{path}" if path else None


def release_year(release_date: Optional[str]) -> Optional[str]:
    return release_date[:4] if release_date else None


def canonical_title(title: str) -> str:
    value = (title or "").casefold()
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\[[^\]]*\]", "", value)
    replacements = {
        "Ⅰ": "1",
        "Ⅱ": "2",
        "Ⅲ": "3",
        "Ⅳ": "4",
        "Ⅴ": "5",
        "Ⅵ": "6",
        "Ⅶ": "7",
        "Ⅷ": "8",
        "Ⅸ": "9",
        "Ⅹ": "10",
    }
    for source, target in replacements.items():
        value = value.replace(source.casefold(), target)
    value = re.sub(r"(리마스터링|리마스터|감독판|디렉터스\s*컷|극장판)", "", value)
    value = re.sub(r"(\d+)부", r"\1", value)
    value = re.sub(r"[^0-9a-z가-힣ぁ-ゟ゠-ヿ一-龯]+", "", value)
    return value


def normalize_person_name(name: str) -> str:
    return re.sub(r"[^0-9a-z가-힣ぁ-ゟ゠-ヿ一-龯]+", "", (name or "").casefold())


def directors_match(source_directors: list, candidate_directors: list) -> bool:
    source = {normalize_person_name(name) for name in source_directors if normalize_person_name(name)}
    candidate = {normalize_person_name(name) for name in candidate_directors if normalize_person_name(name)}
    return bool(source and candidate and source.intersection(candidate))


def search_queries_for_title(title: str) -> list:
    candidates = []

    def add(value: str) -> None:
        cleaned = " ".join((value or "").strip().split())
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    add(title)
    add(re.sub(r"\([^)]*\)", "", title))
    add(re.sub(r"\[[^\]]*\]", "", title))
    add(re.sub(r"(리마스터링|리마스터|감독판|디렉터스\s*컷)", "", title))
    add(re.sub(r"^극장판\s+", "", title))
    add(title.replace("Ⅱ", "2").replace("Ⅰ", "1").replace("Ⅲ", "3"))
    return candidates


def choose_match(title: str, year: Optional[str], results: Iterable[Dict]) -> Optional[MatchResult]:
    normalized_title = normalize_title(title)
    canonical_source = canonical_title(title)
    best: Optional[MatchResult] = None

    for item in results:
        item_title = normalize_title(item.get("title") or "")
        original_title = normalize_title(item.get("original_title") or "")
        item_title_canonical = canonical_title(item.get("title") or "")
        original_title_canonical = canonical_title(item.get("original_title") or "")
        item_year = release_year(item.get("release_date"))

        normalized_match = item_title == normalized_title or original_title == normalized_title
        canonical_match = (
            canonical_source
            and (item_title_canonical == canonical_source or original_title_canonical == canonical_source)
        )

        if not normalized_match and not canonical_match:
            continue

        year_match = bool(year) and bool(item_year) and item_year == year
        if year and item_year and not year_match:
            # 지역 개봉 연도 차이(±1)는 같은 작품으로 본다. 단 정확 일치가 더 높은 점수.
            try:
                year_match = abs(int(item_year) - int(year)) <= 1
            except (TypeError, ValueError):
                year_match = False

        if year_match:
            score = 100 if item_year == year else 96
            reason = "exact_title_year"
        elif canonical_match and not normalized_match:
            score = 90
            reason = "canonical_title"
        elif item_title == normalized_title:
            score = 85
            reason = "exact_title"
        else:
            score = 80
            reason = "exact_original_title"

        candidate = MatchResult(
            tmdb_id=int(item["id"]),
            score=score,
            reason=reason,
            item=item,
        )
        if best is None or candidate.score > best.score:
            best = candidate

    return best


def detail_to_updates(data: Dict) -> Dict[str, Optional[str]]:
    credits = data.get("credits") or {}
    crew = credits.get("crew") or []
    directors_ko = [
        person.get("name")
        for person in crew
        if person.get("job") == "Director" and person.get("name")
    ]
    directors_en = [
        person.get("original_name") or person.get("name")
        for person in crew
        if person.get("job") == "Director" and (person.get("original_name") or person.get("name"))
    ]
    genres = [genre.get("name") for genre in data.get("genres", []) if genre.get("name")]
    runtime = data.get("runtime")
    title_ko = data.get("title") or data.get("original_title") or ""
    title_en = data.get("original_title") or title_ko

    return {
        "tmdb_id": str(data.get("id")) if data.get("id") else None,
        "title_ko": title_ko,
        "title_en": title_en,
        "year": release_year(data.get("release_date")),
        "director": ", ".join(directors_ko) or None,
        "director_ko": ", ".join(directors_ko) or None,
        "director_en": ", ".join(directors_en) or (", ".join(directors_ko) or None),
        "plot": data.get("overview"),
        "poster_url": poster_url(data.get("poster_path")),
        "genre": ", ".join(genres) or None,
        "runtime": f"{runtime} min" if runtime else None,
    }


def detail_directors(data: Dict) -> list:
    credits = data.get("credits") or {}
    crew = credits.get("crew") or []
    names = []
    for person in crew:
        if person.get("job") != "Director":
            continue
        for key in ("name", "original_name"):
            name = person.get(key)
            if name and name not in names:
                names.append(name)
    return names


def apply_updates(movie: Movie, updates: Dict[str, Optional[str]]) -> None:
    for key, value in updates.items():
        if value:
            setattr(movie, key, value)
    if updates.get("title_ko"):
        movie.title = updates["title_ko"]
    if updates.get("director_ko"):
        movie.director = updates["director_ko"]


def tmdb_configured() -> bool:
    return bool(TMDB_ACCESS_TOKEN or TMDB_API_KEY)


def tmdb_get(path: str, params: Dict, retries: int) -> Dict:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                f"{TMDB_API_BASE}{path}",
                params=_tmdb_params(params),
                headers=_tmdb_headers(),
                timeout=12,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def search_movie(title: str, year: Optional[str], retries: int) -> Dict:
    params = {
        "query": title,
        "language": "ko-KR",
        "region": "KR",
        "include_adult": "false",
        "page": 1,
    }
    if year:
        params["year"] = year
    return tmdb_get("/search/movie", params, retries=retries)


def search_best_match(title: str, year: Optional[str], retries: int) -> Optional[MatchResult]:
    seen_ids = set()
    combined_results = []
    for query in search_queries_for_title(title):
        data = search_movie(query, year, retries)
        for item in data.get("results", []):
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            combined_results.append(item)
        match = choose_match(title, year, combined_results)
        if match:
            return match
    return choose_match(title, year, combined_results)


def search_unique_title_year_match(title: str, year: Optional[str], retries: int) -> Optional[MatchResult]:
    if not year:
        return None

    seen_ids = set()
    matches = []
    for query in search_queries_for_title(title):
        data = search_movie(query, year, retries)
        for item in data.get("results", []):
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            match = choose_match(title, year, [item])
            if match and match.reason == "exact_title_year":
                matches.append(match)

    if len(matches) == 1:
        return matches[0]
    return None


def get_movie_detail(tmdb_id: int, retries: int) -> Dict:
    return tmdb_get(
        f"/movie/{tmdb_id}",
        {
            "language": "ko-KR",
            "append_to_response": "credits,external_ids",
        },
        retries=retries,
    )


def load_movie_ids(path: Optional[Path]) -> Optional[list[int]]:
    if not path:
        return None
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value:
            ids.append(int(value))
    return ids


def target_movies(
    limit: Optional[int],
    only_missing_poster: bool,
    start_id: Optional[int],
    movie_ids: Optional[list[int]] = None,
):
    query = Movie.query.filter(Movie.imdb_id.like("watcha:%"))
    if movie_ids is not None:
        if not movie_ids:
            return []
        query = query.filter(Movie.id.in_(movie_ids))
    if start_id:
        query = query.filter(Movie.id >= start_id)
    if only_missing_poster:
        query = query.filter(Movie.poster_url.is_(None))
    else:
        query = query.filter(
            db.or_(
                Movie.poster_url.is_(None),
                Movie.tmdb_id.is_(None),
                Movie.title_en.is_(None),
                Movie.title_en == Movie.title_ko,
            )
        )
    query = query.order_by(Movie.id)
    if limit:
        query = query.limit(limit)
    return query.all()


def write_report_row(writer, movie: Movie, match: Optional[MatchResult], status: str, error: str = "") -> None:
    writer.writerow(
        {
            "movie_id": movie.id,
            "watcha_id": movie.imdb_id,
            "title": movie.title,
            "year": movie.year or "",
            "status": status,
            "tmdb_id": match.tmdb_id if match else "",
            "score": match.score if match else "",
            "reason": match.reason if match else "",
            "tmdb_title": match.item.get("title", "") if match else "",
            "tmdb_original_title": match.item.get("original_title", "") if match else "",
            "tmdb_year": release_year(match.item.get("release_date")) if match else "",
            "error": error,
        }
    )


def enrich_movies(
    commit: bool,
    limit: Optional[int],
    threshold: int,
    report_path: Path,
    sleep_seconds: float,
    only_missing_poster: bool,
    commit_every: int,
    progress_every: int,
    start_id: Optional[int],
    retries: int,
    strict_unique_year: bool = False,
    movie_ids: Optional[list[int]] = None,
) -> EnrichResult:
    if not tmdb_configured():
        raise RuntimeError("TMDb API credential is not configured.")

    result = EnrichResult()
    movies = target_movies(
        limit=limit,
        only_missing_poster=only_missing_poster,
        start_id=start_id,
        movie_ids=movie_ids,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "movie_id",
                "watcha_id",
                "title",
                "year",
                "status",
                "tmdb_id",
                "score",
                "reason",
                "tmdb_title",
                "tmdb_original_title",
                "tmdb_year",
                "error",
            ],
        )
        writer.writeheader()

        for movie in movies:
            result.checked += 1
            try:
                if strict_unique_year:
                    match = search_unique_title_year_match(movie.title_ko or movie.title, movie.year, retries=retries)
                else:
                    match = search_best_match(movie.title_ko or movie.title, movie.year, retries=retries)
                if not match:
                    result.not_found += 1
                    write_report_row(writer, movie, None, "not_found")
                    continue
                if match.score < threshold:
                    result.skipped_low_confidence += 1
                    write_report_row(writer, movie, match, "low_confidence")
                    continue

                detail = get_movie_detail(match.tmdb_id, retries=retries)
                updates = detail_to_updates(detail)
                if commit:
                    apply_updates(movie, updates)
                result.updated += 1
                write_report_row(writer, movie, match, "updated" if commit else "would_update")
                if commit and commit_every and result.updated % commit_every == 0:
                    db.session.commit()
                if progress_every and result.checked % progress_every == 0:
                    print(
                        f"Progress: checked={result.checked}, updated={result.updated}, "
                        f"not_found={result.not_found}, errors={result.errors}",
                        file=sys.stderr,
                        flush=True,
                    )
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            except Exception as exc:
                result.errors += 1
                write_report_row(writer, movie, None, "error", str(exc))
                if progress_every and result.checked % progress_every == 0:
                    print(
                        f"Progress: checked={result.checked}, updated={result.updated}, "
                        f"not_found={result.not_found}, errors={result.errors}",
                        file=sys.stderr,
                        flush=True,
                    )

    if commit:
        db.session.commit()
    else:
        db.session.rollback()
    return result


def write_manual_report_row(writer, watcha_id: str, tmdb_id: str, status: str, movie: Optional[Movie] = None, error: str = "") -> None:
    writer.writerow(
        {
            "watcha_id": watcha_id,
            "tmdb_id": tmdb_id,
            "movie_id": getattr(movie, "id", "") if movie else "",
            "title": getattr(movie, "title", "") if movie else "",
            "status": status,
            "error": error,
        }
    )


def apply_manual_matches(
    manual_csv: Path,
    commit: bool,
    report_path: Path,
    retries: int,
) -> EnrichResult:
    if not tmdb_configured():
        raise RuntimeError("TMDb API credential is not configured.")

    result = EnrichResult()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with manual_csv.open(encoding="utf-8") as f, report_path.open("w", newline="", encoding="utf-8") as report:
        reader = csv.DictReader(f)
        writer = csv.DictWriter(
            report,
            fieldnames=["watcha_id", "tmdb_id", "movie_id", "title", "status", "error"],
        )
        writer.writeheader()

        for row in reader:
            watcha_id = (row.get("watcha_id") or "").strip()
            tmdb_id = (row.get("tmdb_id") or "").strip()
            if not watcha_id and row.get("watcha_content_id"):
                watcha_id = f"watcha:{row['watcha_content_id'].strip()}"
            if not watcha_id or not tmdb_id:
                continue

            result.checked += 1
            movie = Movie.query.filter_by(imdb_id=watcha_id).first()
            if not movie:
                result.not_found += 1
                write_manual_report_row(writer, watcha_id, tmdb_id, "movie_not_found")
                continue

            try:
                detail = get_movie_detail(int(tmdb_id), retries=retries)
                updates = detail_to_updates(detail)
                if commit:
                    apply_updates(movie, updates)
                result.updated += 1
                write_manual_report_row(
                    writer,
                    watcha_id,
                    tmdb_id,
                    "updated" if commit else "would_update",
                    movie,
                )
            except Exception as exc:
                result.errors += 1
                write_manual_report_row(writer, watcha_id, tmdb_id, "error", movie, str(exc))

    if commit:
        db.session.commit()
    else:
        db.session.rollback()
    return result


def apply_watchapedia_hints(
    hints_csv: Path,
    commit: bool,
    report_path: Path,
    retries: int,
) -> EnrichResult:
    if not tmdb_configured():
        raise RuntimeError("TMDb API credential is not configured.")

    result = EnrichResult()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with hints_csv.open(encoding="utf-8") as f, report_path.open("w", newline="", encoding="utf-8") as report:
        reader = csv.DictReader(f)
        writer = csv.DictWriter(
            report,
            fieldnames=[
                "watcha_id",
                "movie_id",
                "title",
                "year",
                "watcha_directors",
                "status",
                "tmdb_id",
                "tmdb_title",
                "tmdb_year",
                "tmdb_directors",
                "error",
            ],
        )
        writer.writeheader()

        for row in reader:
            watcha_id = (row.get("watcha_id") or "").strip()
            title = (row.get("title_ko") or "").strip()
            year = (row.get("year") or "").strip() or None
            source_directors = [
                name.strip()
                for name in (row.get("directors") or "").split("|")
                if name.strip()
            ]
            if not watcha_id or not title or not source_directors:
                continue

            result.checked += 1
            movie = Movie.query.filter_by(imdb_id=watcha_id).first()
            if not movie:
                result.not_found += 1
                writer.writerow(
                    {
                        "watcha_id": watcha_id,
                        "movie_id": "",
                        "title": title,
                        "year": year or "",
                        "watcha_directors": "|".join(source_directors),
                        "status": "movie_not_found",
                    }
                )
                continue

            try:
                candidates = []
                seen_ids = set()
                for query in search_queries_for_title(title):
                    search_data = search_movie(query, year, retries)
                    for item in search_data.get("results", []):
                        tmdb_id = item.get("id")
                        if tmdb_id in seen_ids:
                            continue
                        seen_ids.add(tmdb_id)
                        if not choose_match(title, year, [item]):
                            continue
                        if year and release_year(item.get("release_date")) != year:
                            continue
                        detail = get_movie_detail(int(tmdb_id), retries=retries)
                        candidate_directors = detail_directors(detail)
                        if directors_match(source_directors, candidate_directors):
                            candidates.append((item, detail, candidate_directors))

                if len(candidates) != 1:
                    if len(candidates) == 0:
                        result.not_found += 1
                        status = "not_found"
                    else:
                        result.skipped_low_confidence += 1
                        status = "multiple_candidates"
                    writer.writerow(
                        {
                            "watcha_id": watcha_id,
                            "movie_id": movie.id,
                            "title": title,
                            "year": year or "",
                            "watcha_directors": "|".join(source_directors),
                            "status": status,
                            "error": f"{len(candidates)} candidates",
                        }
                    )
                    continue

                item, detail, candidate_directors = candidates[0]
                updates = detail_to_updates(detail)
                if commit:
                    apply_updates(movie, updates)
                result.updated += 1
                writer.writerow(
                    {
                        "watcha_id": watcha_id,
                        "movie_id": movie.id,
                        "title": title,
                        "year": year or "",
                        "watcha_directors": "|".join(source_directors),
                        "status": "updated" if commit else "would_update",
                        "tmdb_id": item.get("id"),
                        "tmdb_title": item.get("title"),
                        "tmdb_year": release_year(item.get("release_date")) or "",
                        "tmdb_directors": "|".join(candidate_directors),
                    }
                )
            except Exception as exc:
                result.errors += 1
                writer.writerow(
                    {
                        "watcha_id": watcha_id,
                        "movie_id": getattr(movie, "id", ""),
                        "title": title,
                        "year": year or "",
                        "watcha_directors": "|".join(source_directors),
                        "status": "error",
                        "error": str(exc),
                    }
                )

    if commit:
        db.session.commit()
    else:
        db.session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich imported WatchaPedia movies with TMDb metadata and posters."
    )
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--threshold", type=int, default=85)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--commit-every", type=int, default=100)
    parser.add_argument("--progress-every", type=int, default=50)
    parser.add_argument("--only-missing-poster", action="store_true")
    parser.add_argument("--start-id", type=int)
    parser.add_argument("--movie-ids-file", type=Path)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--strict-unique-year", action="store_true")
    parser.add_argument("--manual-matches", type=Path)
    parser.add_argument("--watcha-hints", type=Path)
    parser.add_argument("--report", type=Path, default=Path("data/tmdb_enrichment_report.csv"))
    args = parser.parse_args()

    with app.app_context():
        if args.watcha_hints:
            result = apply_watchapedia_hints(
                hints_csv=args.watcha_hints,
                commit=args.commit,
                report_path=args.report,
                retries=args.retries,
            )
        elif args.manual_matches:
            result = apply_manual_matches(
                manual_csv=args.manual_matches,
                commit=args.commit,
                report_path=args.report,
                retries=args.retries,
            )
        else:
            result = enrich_movies(
                commit=args.commit,
                limit=args.limit,
                threshold=args.threshold,
                report_path=args.report,
                sleep_seconds=args.sleep,
                only_missing_poster=args.only_missing_poster,
                commit_every=args.commit_every,
                progress_every=args.progress_every,
                start_id=args.start_id,
                retries=args.retries,
                strict_unique_year=args.strict_unique_year,
                movie_ids=load_movie_ids(args.movie_ids_file),
            )

    print(f"Mode: {'committed' if args.commit else 'dry run'}")
    print(f"Checked: {result.checked}")
    print(f"Updated: {result.updated}")
    print(f"Skipped low confidence: {result.skipped_low_confidence}")
    print(f"Not found: {result.not_found}")
    print(f"Errors: {result.errors}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
