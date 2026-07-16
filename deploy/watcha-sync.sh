#!/usr/bin/env bash
# 왓챠 → CSV → Cinelog DB 일일 동기화 (VM systemd 타이머가 호출).
# 자격증명/URL 은 레포 밖 설정 파일에서 읽는다(평문 비번이 git 에 안 들어가게).
#   기본 경로: ~/.cinelog-watcha.env  (override: CINELOG_WATCHA_ENV)
# 설정 파일 예시(chmod 600):
#   (아래 값은 예시 — 본인 왓챠 계정/비번/URL 로 교체)
#   WATCHA_EMAIL=you@example.com
#   WATCHA_PASSWORD=YOUR_PW
#   WATCHA_RATINGS_URL=https://pedia.watcha.com/ko-KR/users/XXXX/contents/movies/ratings
#   WATCHA_WATCHLIST_URL=https://pedia.watcha.com/ko-KR/users/XXXX/contents/movies/wishes
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APPDIR"

CONF="${CINELOG_WATCHA_ENV:-$HOME/.cinelog-watcha.env}"
if [ ! -f "$CONF" ]; then
  echo "설정 파일 없음: $CONF (WATCHA_EMAIL/PASSWORD/RATINGS_URL/WATCHLIST_URL 필요)" >&2
  exit 1
fi
set -a; . "$CONF"; set +a

: "${WATCHA_RATINGS_URL:?WATCHA_RATINGS_URL 미설정}"
: "${WATCHA_WATCHLIST_URL:?WATCHA_WATCHLIST_URL 미설정}"

PY="$APPDIR/.venv/bin/python"
STATE="$APPDIR/watcha_state.json"
if [ ! -f "$STATE" ]; then
  echo "세션 파일 없음: $STATE" >&2
  echo "Mac 에서 'python tools/dump_watcha_state.py' 로 생성 후 VM ~/movie-review/ 로 복사하세요." >&2
  exit 1
fi

mkdir -p data
RATINGS_EXISTING_IDS="$APPDIR/data/watchapedia_existing_ratings.txt"
WATCHLIST_EXISTING_IDS="$APPDIR/data/watchapedia_existing_watchlist.txt"
CHANGED_MOVIE_IDS="$APPDIR/data/watchapedia_changed_movie_ids.txt"
"$PY" - <<'PY'
from pathlib import Path

from app import app
from models import Entry, Movie

out = Path("data")
out.mkdir(exist_ok=True)

with app.app_context():
    for entry_type, filename in (
        ("review", "watchapedia_existing_ratings.txt"),
        ("watchlist", "watchapedia_existing_watchlist.txt"),
    ):
        rows = (
            Movie.query.join(Entry)
            .filter(Entry.entry_type == entry_type, Movie.imdb_id.like("watcha:%"))
            .with_entities(Movie.imdb_id)
            .distinct()
            .all()
        )
        ids = sorted(row[0].split(":", 1)[1] for row in rows if row[0])
        (out / filename).write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")
        print(f"기존 {entry_type} 왓챠 ID {len(ids)}개 기록: {out / filename}")
PY

# headless 는 왓챠 봇감지로 앱이 API 호출을 안 해 헤더 캡처가 안 됨.
# xvfb 가상 디스플레이 + headful 로 실제 브라우저처럼 동작시켜야 API 요청이 떠 헤더를 캡처.
# (수집 자체는 API 페이징(HTTP)이라 가볍고, 브라우저는 첫 페이지 1회 로드만.)
echo "[$(date -Is)] export 시작 (xvfb headful + API-only + storage-state)"
timeout 240 xvfb-run -a "$PY" -u tools/export_watchapedia.py \
  --storage-state "$STATE" \
  --ratings-url "$WATCHA_RATINGS_URL" \
  --watchlist-url "$WATCHA_WATCHLIST_URL" \
  --ratings-existing-ids "$RATINGS_EXISTING_IDS" \
  --watchlist-existing-ids "$WATCHLIST_EXISTING_IDS" \
  --stop-after-existing 10 \
  --api-only \
  --out-dir data

echo "[$(date -Is)] import 시작 (--commit)"
"$PY" tools/import_watcha_csv.py \
  --ratings data/watchapedia_ratings.csv \
  --watchlist data/watchapedia_watchlist.csv \
  --commit \
  --changed-movie-ids-out "$CHANGED_MOVIE_IDS"

CHANGED_COUNT="$(grep -c '^[0-9]' "$CHANGED_MOVIE_IDS" 2>/dev/null || true)"

# 1차 보강: 변경 여부와 무관하게 항상 전체 스윕.
# --movie-ids-file 없이 poster_url IS NULL 전체를 타겟 → 과거 실패분도 매 sync 재시도.
echo "[$(date -Is)] TMDb 보강 1차 (한국어 제목, 전체 누락 스윕)"
"$PY" tools/enrich_tmdb_metadata.py --only-missing-poster --commit --sleep 0.3 || \
  echo "  (1차 보강 일부 실패 — TMDb 일시 오류일 수 있음)"

# 2차 보강: 브라우저로 왓챠 원제+연도 취득 후 TMDb 재매칭.
# --limit 30: 매 sync 최대 30개만 처리해 실행 시간 제한 (나머지는 다음 sync 때).
echo "[$(date -Is)] TMDb 보강 2차 (왓챠 원제, 전체 누락 스윕 최대 30개)"
xvfb-run -a "$PY" tools/enrich_via_watcha_detail.py --storage-state "$STATE" --limit 30 --commit --sleep 0.2 || \
  echo "  (2차 보강 실패 — xvfb/세션 확인 필요)"

if [ "${CHANGED_COUNT:-0}" -eq 0 ]; then
  echo "[$(date -Is)] 신규/변경 영화 없음 — 태그 백필 생략"
  echo "[$(date -Is)] 동기화 완료"
  exit 0
fi

echo "[$(date -Is)] 신규/변경 영화 ${CHANGED_COUNT}개 태그 백필"

# 원작(소설/만화 등) 있는 작품의 신규 엔트리에 '원작존재' 해시태그 백필(멱등).
echo "[$(date -Is)] 원작존재 해시태그 백필"
"$PY" tools/backfill_original_source_tag.py --commit --movie-ids-file "$CHANGED_MOVIE_IDS" --sleep 0.2 || \
  echo "  (태그 백필 일부 실패 — 다음 실행 때 재시도됨)"

echo "[$(date -Is)] 동기화 완료"
