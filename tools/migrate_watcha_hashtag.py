"""
왓챠에서 마이그레이션한 평가/보고싶어요에 '왓챠백업' 해시태그를 동기화합니다.

대상:
  - review: RatingModule.name == '왓챠 별점'
  - watchlist: Movie.imdb_id가 'watcha:'로 시작하는 Entry

실행:
    cd /Users/dayeon.park/dev/movie-review
    python3 tools/migrate_watcha_hashtag.py
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Entry, Hashtag, Movie, RatingModule

TAG_NAME = "왓챠백업"


def get_or_create_hashtag(name: str) -> Hashtag:
    tag = Hashtag.query.filter_by(name=name).first()
    if not tag:
        tag = Hashtag(name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def watcha_backup_entries():
    watcha_reviews = Entry.query.filter(
        Entry.entry_type == "review",
        Entry.ratings.any(RatingModule.name == "왓챠 별점"),
    )
    watcha_watchlist = Entry.query.join(Movie).filter(
        Entry.entry_type == "watchlist",
        Movie.imdb_id.like("watcha:%"),
    )
    return watcha_reviews.union(watcha_watchlist).all()


def sync_watcha_backup_hashtag():
    tag = get_or_create_hashtag(TAG_NAME)
    entries = watcha_backup_entries()
    target_ids = {entry.id for entry in entries}

    added = 0
    skipped = 0
    for entry in entries:
        if tag in entry.hashtags:
            skipped += 1
            continue
        entry.hashtags.append(tag)
        added += 1

    removed = 0
    incorrectly_tagged_entries = Entry.query.filter(
        Entry.hashtags.any(Hashtag.name == TAG_NAME),
        ~Entry.id.in_(target_ids),
    ).all()
    for entry in incorrectly_tagged_entries:
        entry.hashtags.remove(tag)
        removed += 1

    db.session.commit()
    return added, skipped, removed, len(entries)


def add_watcha_backup_hashtag():
    added, skipped, _removed, total = sync_watcha_backup_hashtag()
    return added, skipped, total

def main():
    with app.app_context():
        if not watcha_backup_entries():
            print("왓챠에서 마이그레이션한 항목을 찾지 못했습니다.")
            return

        added, skipped, removed, total = sync_watcha_backup_hashtag()
        print(
            f"'{TAG_NAME}' 해시태그 동기화 완료: "
            f"{added}건 추가, {skipped}건 유지, {removed}건 제거 (총 대상 {total}건)"
        )


if __name__ == "__main__":
    main()
