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


def _watcha_detail(page, headers: dict, code: str):
    resp = page.request.get(f"{WATCHA_BASE}/api/contents/{code}", headers=headers)
    if resp.status != 200:
        return None
    return (resp.json() or {}).get("result") or {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--storage-state", required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--threshold", type=int, default=85)
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
                return

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
                    query_title = orig or ko

                    match = None
                    if query_title:
                        match = search_best_match(query_title, year, args.retries)
                        if (not match or match.score < args.threshold) and ko and ko != query_title:
                            alt = search_best_match(ko, year, args.retries)
                            if alt and (not match or alt.score > match.score):
                                match = alt

                    if match and match.score >= args.threshold:
                        data = get_movie_detail(match.tmdb_id, args.retries)
                        updates = detail_to_updates(data)
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
