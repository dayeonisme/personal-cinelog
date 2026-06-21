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

echo "[$(date -Is)] export 시작 (headless)"
"$PY" tools/export_watchapedia.py --headless \
  --ratings-url "$WATCHA_RATINGS_URL" \
  --watchlist-url "$WATCHA_WATCHLIST_URL" \
  --out-dir data

echo "[$(date -Is)] import 시작 (--commit)"
"$PY" tools/import_watcha_csv.py \
  --ratings data/watchapedia_ratings.csv \
  --watchlist data/watchapedia_watchlist.csv \
  --commit

echo "[$(date -Is)] 동기화 완료"
