"""
같은 영화에 대해 평가(review)와 보고싶어요(watchlist)가 서로 다른 movie_id 로
나뉘어 등록된 경우, 한쪽으로 합쳐서 영화 상세 페이지에서 평가·보고싶어요를
한 번에 볼 수 있도록 정리합니다.

오늘(6/7) 수기로 등록하면서 중복 생성된 영화 레코드 2건을 대상으로 합니다:
  - 레이첼, 결혼하다 (2008): watchlist movie_id=1254 → review movie_id=1852 로 이동
  - 모래의 여자 (1964):     watchlist movie_id=1268 → review movie_id=1851 로 이동

이동 후 비어버린 영화 레코드(1254, 1268)는 삭제됩니다.
(평가 쪽 레코드를 기준(keep)으로 삼은 이유: 정보가 더 풍부하고 최근에 TMDb에서
다시 불러온 레코드이기 때문입니다.)

실행 전 자동으로 movies.db 백업을 생성합니다.

실행:
    cd /Users/dayeon.park/dev/movie-review
    python3 tools/merge_movie_duplicates.py            # 실제 적용
    python3 tools/merge_movie_duplicates.py --dry-run  # 미리보기만 (DB 변경 없음)
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from database import db
from models import Entry, Movie

# (옮길 movie_id, 합쳐질 대상 movie_id, 표시용 라벨)
MERGE_PAIRS = [
    (1254, 1852, "레이첼, 결혼하다 (2008)"),
    (1268, 1851, "모래의 여자 (1964)"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 대상만 출력")
    args = parser.parse_args()

    with app.app_context():
        db_path = ROOT_DIR / "movies.db"
        if not args.dry_run and db_path.exists():
            backup_path = ROOT_DIR / f"movies.db.bak-before-merge-duplicates-{datetime.now():%Y%m%d-%H%M%S}"
            shutil.copy2(db_path, backup_path)
            print(f"백업 생성: {backup_path.name}")

        for old_id, keep_id, label in MERGE_PAIRS:
            old_movie = Movie.query.get(old_id)
            keep_movie = Movie.query.get(keep_id)
            print(f"\n[{label}] movie_id {old_id} → {keep_id}")

            if not old_movie or not keep_movie:
                print(f"  영화 레코드를 찾을 수 없어 건너뜁니다 (old={old_id}: {bool(old_movie)}, keep={keep_id}: {bool(keep_movie)})")
                continue

            entries = Entry.query.filter_by(movie_id=old_id).all()
            if not entries:
                print(f"  movie_id={old_id} 에 연결된 항목이 없습니다 (이미 정리됨).")
            for e in entries:
                print(f"  - entry id={e.id} ({e.entry_type}) 의 movie_id 를 {old_id} → {keep_id} 로 변경")
                if not args.dry_run:
                    e.movie_id = keep_id

            if not args.dry_run:
                db.session.flush()
                remaining = Entry.query.filter_by(movie_id=old_id).count()
                if remaining == 0:
                    db.session.delete(old_movie)
                    print(f"  - 빈 영화 레코드(id={old_id}) 삭제")
                else:
                    print(f"  - movie_id={old_id} 에 아직 {remaining}건이 남아있어 레코드를 삭제하지 않습니다.")

        if args.dry_run:
            print("\n(--dry-run 모드: 실제 변경 없음)")
        else:
            db.session.commit()
            print("\n완료: 두 영화 모두 평가·보고싶어요가 같은 영화 페이지에서 함께 보입니다.")


if __name__ == "__main__":
    main()
