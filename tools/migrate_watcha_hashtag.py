"""
왓챠에서 마이그레이션한 모든 평가/보고싶어요에 '왓챠백업' 해시태그를 일괄 추가합니다.

대상: Movie.imdb_id가 'watcha:'로 시작하는 모든 Entry (review + watchlist)

실행:
    cd /path/to/personal-cinelog
    python3 tools/migrate_watcha_hashtag.py
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Entry, Hashtag, Movie

TAG_NAME = "왓챠백업"


def get_or_create_hashtag(name: str) -> Hashtag:
    tag = Hashtag.query.filter_by(name=name).first()
    if not tag:
        tag = Hashtag(name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def watcha_backup_entries():
    return Entry.query.join(Movie).filter(Movie.imdb_id.like("watcha:%")).all()


def add_watcha_backup_hashtag():
    tag = get_or_create_hashtag(TAG_NAME)
    entries = watcha_backup_entries()

    updated = 0
    skipped = 0
    for entry in entries:
        if tag in entry.hashtags:
            skipped += 1
            continue
        entry.hashtags.append(tag)
        updated += 1

    db.session.commit()
    return updated, skipped, len(entries)

def main():
    with app.app_context():
        if not watcha_backup_entries():
            print("왓챠에서 마이그레이션한 항목을 찾지 못했습니다 (Movie.imdb_id LIKE 'watcha:%').")
            return

        updated, skipped, total = add_watcha_backup_hashtag()
        print(f"'{TAG_NAME}' 해시태그 추가 완료: {updated}건 추가, {skipped}건은 이미 보유하여 건너뜀 (총 대상 {total}건)")


if __name__ == "__main__":
    main()
