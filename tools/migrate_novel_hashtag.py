"""
TMDb 키워드를 검색해 소설/만화/희곡 등 원작이 존재하는 영화의 평가·보고싶어요
항목에 '원작존재' 해시태그를 일괄 추가합니다.

판별 방식: TMDb의 영화별 keywords(/movie/{id}/keywords)에서
"based on novel", "based on novel or book", "based on book", "based on young adult novel",
"based on short story", "based on graphic novel", "based on comic", "based on memoir or
autobiography", "based on play or musical" 등 원작이 있음을 가리키는 키워드가 있으면
원작이 있는 것으로 간주합니다. (소설뿐 아니라 만화/희곡/논픽션 등도 포함되므로
태그명을 '원작존재' 로 합니다. TMDb 데이터에 키워드가 등록되지 않은 영화는
누락될 수 있습니다.)

실행:
    cd /path/to/personal-cinelog
    python3 tools/migrate_novel_hashtag.py

옵션:
    --dry-run   실제로 DB를 변경하지 않고 대상만 출력
"""
import argparse
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests

from app import (
    ORIGINAL_SOURCE_KEYWORD_HINTS,
    ORIGINAL_SOURCE_TAG_NAME,
    TMDB_API_BASE,
    _tmdb_configured,
    _tmdb_headers,
    _tmdb_params,
    app,
)
from database import db
from models import Entry, Hashtag, Movie

TAG_NAME = ORIGINAL_SOURCE_TAG_NAME


def is_novel_based(keywords):
    names = [(k.get("name") or "").strip().lower() for k in keywords]
    return any(any(hint in name for hint in ORIGINAL_SOURCE_KEYWORD_HINTS) for name in names)


def fetch_keywords(tmdb_id):
    url = f"{TMDB_API_BASE}/movie/{tmdb_id}/keywords"
    resp = requests.get(url, headers=_tmdb_headers(), params=_tmdb_params({}), timeout=15)
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get("keywords") or data.get("results") or []


def get_or_create_hashtag(name: str) -> Hashtag:
    tag = Hashtag.query.filter_by(name=name).first()
    if not tag:
        tag = Hashtag(name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 대상만 출력")
    args = parser.parse_args()

    with app.app_context():
        if not _tmdb_configured():
            print("TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY가 설정되어 있지 않습니다. .env를 확인해주세요.")
            return

        movies = Movie.query.filter(Movie.tmdb_id.isnot(None)).all()
        print(f"TMDb ID가 있는 영화 {len(movies)}건의 키워드를 조회합니다...")

        novel_movie_ids = []
        for i, movie in enumerate(movies, 1):
            keywords = fetch_keywords(movie.tmdb_id)
            if keywords is None:
                print(f"  [{i}/{len(movies)}] {movie.title}: 키워드 조회 실패 (건너뜀)")
            elif is_novel_based(keywords):
                novel_movie_ids.append(movie.id)
                matched = [k.get("name") for k in keywords if any(h in (k.get("name") or "").lower() for h in ORIGINAL_SOURCE_KEYWORD_HINTS)]
                print(f"  [{i}/{len(movies)}] {movie.title}: 원작 있음 ({', '.join(matched)})")
            time.sleep(0.05)  # TMDb rate limit 여유

        if not novel_movie_ids:
            print("원작 소설/책이 있는 영화를 찾지 못했습니다.")
            return

        entries = Entry.query.filter(Entry.movie_id.in_(novel_movie_ids)).all()
        print(f"\n총 {len(novel_movie_ids)}개 영화 / {len(entries)}개 항목(평가+보고싶어요)에 '{TAG_NAME}' 태그를 추가합니다.")

        if args.dry_run:
            print("(--dry-run 모드: 실제 변경 없음)")
            return

        tag = get_or_create_hashtag(TAG_NAME)
        added, skipped = 0, 0
        for entry in entries:
            if tag in entry.hashtags:
                skipped += 1
                continue
            entry.hashtags.append(tag)
            added += 1

        db.session.commit()
        print(f"완료: {added}건 추가, {skipped}건은 이미 보유하여 건너뜀")


if __name__ == "__main__":
    main()
