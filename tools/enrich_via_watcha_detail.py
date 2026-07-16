#!/usr/bin/env python3
"""bare 왓챠 영화(포스터 없음)를 왓챠 content API 의 원제+연도로 TMDb 재매칭해 보강.

enrich_tmdb_metadata.py 는 한국어 제목으로 검색해 연도 누락/제목 장식 케이스에서
매칭 실패가 많았다. 왓챠 content API(/api/contents/{code})가 original_title(영문/원어)
+ year 를 주므로, 그걸로 검색하면 choose_match 가 score 100(exact_title_year)으로 잡는다.

브라우저로 헤더(x-frograms-*, device-id)만 캡처하고 실제 데이터는 API(HTTP)로 받는다.
headless 는 봇감지로 막히므로 VM 에선 xvfb 로 headful 실행:
    xvfb-run python tools/enrich_via_watcha_detail.py --storage-state watcha_state.json --commit
"""
import argparse
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Movie
from tools.enrich_tmdb_metadata import (
    apply_updates,
    detail_to_updates,
    get_movie_detail,
    search_best_match,
    tmdb_configured,
)

WATCHA_BASE = "https://pedia.watcha.com"

# 제목 끝의 에디션 장식(감독판/디 오리지널/Director's Cut/4K 등)을 떼어 검색 적중률을 높인다.
# 예: "Das Boot - Director's Cut" → "Das Boot", "패왕별희 디 오리지널" → "패왕별희".
_EDITION_PATTERNS = [
    r"\s*[-:]\s*the\s+director'?s\s+cut\b.*$",
    r"\s*[-:]?\s*director'?s\s+cut\b.*$",
    r"\s*[-:]?\s*디렉터스\s*컷.*$",
    r"\s*[-:]?\s*디\s*오리지널.*$",
    r"\s*[-:]?\s*감독판.*$",
    r"\s*[-:]?\s*비디오판.*$",
    r"\s*[-:]?\s*무삭제판.*$",
    r"\s*[-:]?\s*확장판.*$",
    r"\s*[-:]?\s*리마스터(링|드)?.*$",
    r"\s*[-:(]?\s*\b4k\b.*$",
]


def _strip_edition(title: str) -> str:
    text = title or ""
    for pattern in _EDITION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def _capture_headers(page, sample_code: str) -> dict:
    def is_target(req):
        return "/api/contents/" in req.url

    try:
        with page.expect_request(is_target, timeout=20000) as info:
            page.goto(f"{WATCHA_BASE}/ko/contents/{sample_code}", wait_until="domcontentloaded")
        req = info.value
    except Exception:
        return {}
    return {
        k: v for k, v in req.headers.items()
        if k.lower().startswith("x-frograms") or k.lower() == "accept"
    }


def _watcha_detail(page, headers: dict, code: str, timeout: int = 30000):
    resp = page.request.get(
        f"{WATCHA_BASE}/api/contents/{code}", headers=headers, timeout=timeout
    )
    if resp.status != 200:
        return None
    return (resp.json() or {}).get("result") or {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--storage-state", required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--movie-ids-file", type=Path)
    # choose_match 는 정확 제목/원제 매칭만 반환(퍼지 없음). 80=exact_original_title
    # (원제 정확, 연도만 재개봉/지역차로 어긋남) 까지 신뢰. 연도 일치는 100이라 우선됨.
    ap.add_argument("--threshold", type=int, default=80)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--commit-every", type=int, default=50)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    with app.app_context():
        if not tmdb_configured():
            print("TMDb 미설정(.env 토큰 없음) — 중단")
            return

        query = Movie.query.filter(
            Movie.imdb_id.like("watcha:%"), Movie.poster_url.is_(None)
        ).order_by(Movie.id)
        if args.movie_ids_file:
            movie_ids = [
                int(line.strip())
                for line in args.movie_ids_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            query = query.filter(Movie.id.in_(movie_ids)) if movie_ids else query.filter(False)
        if args.limit:
            query = query.limit(args.limit)
        movies = query.all()
        if not movies:
            print("대상 없음(포스터 없는 왓챠 영화 0)")
            return
        print(f"대상 {len(movies)}개")

        checked = updated = no_detail = not_found = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=args.storage_state)
            page = context.new_page()

            first_code = movies[0].imdb_id.split(":", 1)[1]
            headers = _capture_headers(page, first_code)
            if not headers:
                print("왓챠 API 헤더 캡처 실패 — 중단(xvfb/세션 확인)")
                browser.close()
                sys.exit(1)

            for movie in movies:
                checked += 1
                code = movie.imdb_id.split(":", 1)[1]
                try:
                    detail = _watcha_detail(page, headers, code)
                except Exception:
                    detail = None

                if not detail:
                    no_detail += 1
                    print(f"  ? {movie.title}: 왓챠 상세 없음", flush=True)
                else:
                    orig = (detail.get("original_title") or "").strip()
                    ko = (detail.get("title") or "").strip()
                    year = str(detail.get("year")) if detail.get("year") else (movie.year or None)
                    # 원제 → 원제(에디션 strip) → 한국어 제목 → 한국어(strip) 순으로 후보 검색.
                    candidates = []
                    for cand in (orig, _strip_edition(orig), ko, _strip_edition(ko)):
                        cand = (cand or "").strip()
                        if cand and cand not in candidates:
                            candidates.append(cand)

                    match = None
                    for q in candidates:
                        m = search_best_match(q, year, args.retries)
                        if m and (match is None or m.score > match.score):
                            match = m
                        if match and match.score >= 100:
                            break  # 정확 매칭이면 더 안 봄

                    if match and match.score >= args.threshold:
                        data = get_movie_detail(match.tmdb_id, args.retries)
                        updates = detail_to_updates(data)
                        # 한국어 표시명/원제는 왓챠 값 우선 — TMDb ko 가 한국어 없으면 원어로
                        # fallback 되어 title_ko/director_ko 가 일본어 등으로 덮이는 문제 방지.
                        if ko:
                            updates["title_ko"] = ko
                        if orig:
                            updates["title_en"] = orig
                        wdirs = [n for n in (detail.get("director_names") or []) if n]
                        if wdirs:
                            updates["director_ko"] = ", ".join(wdirs)
                        if not movie.year and year:
                            movie.year = year
                        apply_updates(movie, updates)
                        updated += 1
                        print(f"  ✓ {movie.title} → {data.get('title')} "
                              f"(tmdb {match.tmdb_id}, score {match.score})", flush=True)
                    else:
                        not_found += 1
                        print(f"  ✗ {movie.title}: 원제 '{orig}' / {year} → 매칭 실패", flush=True)

                if args.commit and args.commit_every and updated and updated % args.commit_every == 0:
                    db.session.commit()
                if args.sleep:
                    time.sleep(args.sleep)

            context.close()
            browser.close()

        if args.commit:
            db.session.commit()
        print(f"\nMode: {'committed' if args.commit else 'dry run'}")
        print(f"검토 {checked} / 보강 {updated} / 왓챠상세없음 {no_detail} / TMDb매칭실패 {not_found}")


if __name__ == "__main__":
    main()
