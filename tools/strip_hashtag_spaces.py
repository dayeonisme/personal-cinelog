"""
해시태그는 이제 공백을 포함할 수 없도록 정책이 바뀌었습니다.
기존에 등록된 해시태그 중 이름에 공백이 있는 것들의 공백을 제거합니다.

대상(현재 기준):
  '왓챠 백업'  → '왓챠백업'
  '원작 존재'  → '원작존재'

만약 공백을 제거한 이름이 이미 다른 해시태그로 존재하면(충돌), 두 태그를
하나로 합칩니다(연결된 항목을 모두 옮긴 뒤 빈 태그 삭제).

실행 전 자동으로 movies.db 백업을 생성합니다.

실행:
    cd /Users/dayeon.park/dev/movie-review
    python3 tools/strip_hashtag_spaces.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Entry, Hashtag

WHITESPACE_RE = re.compile(r"\s+")


def main():
    with app.app_context():
        targets = [t for t in Hashtag.query.all() if WHITESPACE_RE.search(t.name or "")]
        if not targets:
            print("공백이 포함된 해시태그가 없습니다.")
            return

        db_path = ROOT_DIR / "movies.db"
        if db_path.exists():
            backup_path = ROOT_DIR / f"movies.db.bak-before-strip-hashtag-spaces-{datetime.now():%Y%m%d-%H%M%S}"
            shutil.copy2(db_path, backup_path)
            print(f"백업 생성: {backup_path.name}")

        for tag in targets:
            old_name = tag.name
            new_name = WHITESPACE_RE.sub("", old_name)
            existing = Hashtag.query.filter_by(name=new_name).first()

            entries = Entry.query.filter(Entry.hashtags.any(Hashtag.id == tag.id)).all()

            if existing and existing.id != tag.id:
                # 충돌: 기존 태그로 항목들을 옮기고 공백 있던 태그는 삭제
                moved = 0
                for entry in entries:
                    if existing not in entry.hashtags:
                        entry.hashtags.append(existing)
                        moved += 1
                    entry.hashtags.remove(tag)
                db.session.flush()
                db.session.delete(tag)
                print(f"'{old_name}' → '{new_name}' (이미 존재) : {moved}건 병합 후 빈 태그 삭제")
            else:
                tag.name = new_name
                print(f"'{old_name}' → '{new_name}' 이름 변경 ({len(entries)}건 유지)")

        db.session.commit()
        print("\n완료: 해시태그 이름의 공백을 모두 제거했습니다.")


if __name__ == "__main__":
    main()
