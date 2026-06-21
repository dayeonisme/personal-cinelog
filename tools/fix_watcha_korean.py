#!/usr/bin/env python3
"""TMDb 보강이 한국어 제목/감독을 원어로 덮은 왓챠 영화를 왓챠의 한국어 값으로 교정.

TMDb 는 language=ko-KR 로 조회해도 한국어 제목이 없으면 원어(일본어/중국어/프랑스어 등)로
fallback 한다. 그 값이 title_ko/director_ko 에 들어가 홈/상세가 원어로만 표기되던 문제
(예: おとし穴 → 함정 이어야 함). 왓챠 content API 의 title(한국어)/director_names(한국어)로 되돌린다.

대상: title_ko 또는 director_ko 에 한글이 전혀 없는 왓챠 영화(원어로 덮인 것).
title_en(원제)은 왓챠 original_title 로 보정한다.

브라우저는 헤더 캡처용(데이터는 API) → VM 은 xvfb:
    xvfb-run python tools/fix_watcha_korean.py --storage-state watcha_state.json --commit
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
from tools.enrich_via_watcha_detail import _capture_headers, _watcha_detail

HANGUL = re.compile(r"[가-힣]")


def _no_hangul(text: str) -> bool:
    return bool(text) and not HANGUL.search(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--storage-state", required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--commit-every", type=int, default=50)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    with app.app_context():
        all_watcha = Movie.query.filter(Movie.imdb_id.like("watcha:%")).order_by(Movie.id).all()
        targets = [m for m in all_watcha if _no_hangul(m.title_ko) or _no_hangul(m.director_ko)]
        if args.limit:
            targets = targets[: args.limit]
        if not targets:
            print("교정 대상 없음(한글 없는 title_ko/director_ko 0)")
            return
        print(f"교정 대상 {len(targets)}개")

        checked = fixed = no_detail = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=args.storage_state)
            page = context.new_page()
            headers = _capture_headers(page, targets[0].imdb_id.split(":", 1)[1])
            if not headers:
                print("왓챠 API 헤더 캡처 실패 — 중단(xvfb/세션 확인)")
                browser.close()
                return

            for movie in targets:
                checked += 1
                code = movie.imdb_id.split(":", 1)[1]
                detail = None
                for attempt in range(3):
                    try:
                        detail = _watcha_detail(page, headers, code)
                    except Exception:
                        detail = None
                    if detail:
                        break
                    page.wait_for_timeout(1200 * (attempt + 1))  # rate-limit 백오프
                if not detail:
                    no_detail += 1
                    continue

                ko = (detail.get("title") or "").strip()
                orig = (detail.get("original_title") or "").strip()
                wdirs = [n for n in (detail.get("director_names") or []) if n]

                changed = []
                if ko and HANGUL.search(ko) and ko != movie.title_ko:
                    movie.title_ko = ko
                    movie.title = ko
                    changed.append("제목")
                if orig and orig != movie.title_en:
                    movie.title_en = orig
                if wdirs:
                    dko = ", ".join(wdirs)
                    if HANGUL.search(dko) and dko != movie.director_ko:
                        movie.director_ko = dko
                        movie.director = dko
                        changed.append("감독")

                if changed:
                    fixed += 1
                    print(f"  ✓ {code}: {movie.title_ko} ({'/'.join(changed)})", flush=True)

                if args.commit and args.commit_every and fixed and fixed % args.commit_every == 0:
                    db.session.commit()
                if args.sleep:
                    time.sleep(args.sleep)

            context.close()
            browser.close()

        if args.commit:
            db.session.commit()
        print(f"\nMode: {'committed' if args.commit else 'dry run'}")
        print(f"검토 {checked} / 교정 {fixed} / 왓챠상세없음 {no_detail}")


if __name__ == "__main__":
    main()
