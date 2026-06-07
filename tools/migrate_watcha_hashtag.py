"""
왓챠에서 마이그레이션한 모든 평가(리뷰)에 '왓챠 백업' 해시태그를 일괄 추가합니다.

대상: RatingModule.name == '왓챠 별점' 을 가진 Entry (review)

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
from models import Entry, Hashtag, RatingModule

TAG_NAME = "왓챠 백업"


def get_or_create_hashtag(name: str) -> Hashtag:
    tag = Hashtag.query.filter_by(name=name).first()
    if not tag:
        tag = Hashtag(name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def main():
    with app.app_context():
        tag = get_or_create_hashtag(TAG_NAME)

        entry_ids = [
            row[0]
            for row in db.session.query(RatingModule.entry_id)
            .filter(RatingModule.name == "왓챠 별점")
            .distinct()
            .all()
        ]

        if not entry_ids:
            print("왓챠에서 마이그레이션한 평가를 찾지 못했습니다 (RatingModule.name == '왓챠 별점').")
            return

        updated = 0
        skipped = 0
        for entry in Entry.query.filter(Entry.id.in_(entry_ids)).all():
            if tag in entry.hashtags:
                skipped += 1
                continue
            entry.hashtags.append(tag)
            updated += 1

        db.session.commit()
        print(f"'{TAG_NAME}' 해시태그 추가 완료: {updated}건 추가, {skipped}건은 이미 보유하여 건너뜀 (총 대상 {len(entry_ids)}건)")


if __name__ == "__main__":
    main()
