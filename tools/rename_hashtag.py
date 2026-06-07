"""
'원작 소설' 해시태그를 '원작 존재' 로 이름 변경합니다.

이유: 마이그레이션으로 일괄 추가된 항목 중 만화/코믹 등 소설이 아닌 원작도
포함되어 있어, 더 포괄적인 이름인 '원작 존재' 로 바꿉니다. (태그 자체의
이름만 바꾸는 것이므로 연결된 항목들은 그대로 유지됩니다.)

실행 전 자동으로 movies.db 백업을 생성합니다.

실행:
    cd /Users/dayeon.park/dev/movie-review
    python3 tools/rename_hashtag.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Hashtag

OLD_NAME = "원작 소설"
NEW_NAME = "원작 존재"


def main():
    with app.app_context():
        old_tag = Hashtag.query.filter_by(name=OLD_NAME).first()
        if not old_tag:
            print(f"'{OLD_NAME}' 해시태그를 찾을 수 없습니다. (이미 변경되었거나 존재하지 않음)")
            return

        existing_new = Hashtag.query.filter_by(name=NEW_NAME).first()
        if existing_new:
            print(f"이미 '{NEW_NAME}' 해시태그가 존재합니다 (id={existing_new.id}). "
                  f"이름만 바꾸면 충돌하므로 직접 확인 후 처리해주세요.")
            return

        db_path = ROOT_DIR / "movies.db"
        if db_path.exists():
            backup_path = ROOT_DIR / f"movies.db.bak-before-rename-hashtag-{datetime.now():%Y%m%d-%H%M%S}"
            shutil.copy2(db_path, backup_path)
            print(f"백업 생성: {backup_path.name}")

        count = len(old_tag.entries) if hasattr(old_tag, "entries") else None
        old_tag.name = NEW_NAME
        db.session.commit()
        print(f"완료: 해시태그 이름을 '{OLD_NAME}' → '{NEW_NAME}' 로 변경했습니다."
              + (f" (연결된 항목 {count}건 유지)" if count is not None else ""))


if __name__ == "__main__":
    main()
