#!/usr/bin/env python3
"""tmdb_id 가 채워진 영화 중 원작(소설/만화 등)이 있는 작품의 엔트리에 '원작존재' 태그를 백필.

app.py 는 엔트리를 API 로 생성할 때만 이 태그를 단다. 왓챠 import 로 만든 엔트리는
태그가 없으므로, TMDb 키워드로 원작 여부를 보고 누락된 엔트리에 태그를 추가한다.
- 멱등: 이미 태그가 달린 엔트리는 건너뜀(재실행 안전).
- TMDb 호출은 tmdb_id 당 1회만(캐시). tmdb_id 없는 영화는 판정 불가라 제외.

사용: python tools/backfill_original_source_tag.py [--commit] [--sleep 0.2] [--limit N]
"""
import argparse
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app, ORIGINAL_SOURCE_TAG_NAME, _movie_has_original_source
from database import db
from models import Movie, Hashtag


def _get_or_create_tag():
    tag = Hashtag.query.filter_by(name=ORIGINAL_SOURCE_TAG_NAME).first()
    if not tag:
        tag = Hashtag(name=ORIGINAL_SOURCE_TAG_NAME)
        db.session.add(tag)
        db.session.flush()
    return tag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--movie-ids-file", type=Path)
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--commit-every", type=int, default=200,
                    help="N개 원작영화 처리마다 중간 커밋(중단/재실행 시 이어감)")
    args = ap.parse_args()

    with app.app_context():
        tag = _get_or_create_tag()
        query = Movie.query.filter(Movie.tmdb_id.isnot(None))
        if args.movie_ids_file:
            movie_ids = [
                int(line.strip())
                for line in args.movie_ids_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            query = query.filter(Movie.id.in_(movie_ids)) if movie_ids else query.filter(False)
        movies = query.all()

        checked = qualified = api_calls = tagged = 0
        cache = {}
        for movie in movies:
            if args.limit and checked >= args.limit:
                break
            untagged = [
                e for e in movie.entries
                if not any(h.name == ORIGINAL_SOURCE_TAG_NAME for h in e.hashtags)
            ]
            if not untagged:
                continue
            checked += 1

            key = str(movie.tmdb_id)
            if key not in cache:
                cache[key] = _movie_has_original_source(movie.tmdb_id)
                api_calls += 1
                if args.sleep:
                    time.sleep(args.sleep)
            if cache[key]:
                qualified += 1
                for entry in untagged:
                    entry.hashtags.append(tag)
                    tagged += 1
                if args.commit and args.commit_every and qualified % args.commit_every == 0:
                    db.session.commit()

            if args.progress_every and checked % args.progress_every == 0:
                print(f"  진행: {checked} 검토 / 원작 {qualified} / 태그 {tagged}", flush=True)

        if args.commit:
            db.session.commit()

        print(f"Mode: {'committed' if args.commit else 'dry run'}")
        print(f"검토(태그 누락 엔트리 보유) 영화: {checked}")
        print(f"TMDb 키워드 조회: {api_calls}")
        print(f"원작 존재 영화: {qualified}")
        print(f"태그 추가된 엔트리: {tagged}")


if __name__ == "__main__":
    main()
