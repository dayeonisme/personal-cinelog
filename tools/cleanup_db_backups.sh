#!/bin/bash
# 오래된 DB 백업(movies.db.bak-*) 정리: 최신 5개만 남기고 삭제.
# launchd(주간)로 실행. 수동 실행도 가능.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
KEEP=5
LOG="$REPO/tools/cleanup_db_backups.log"

cd "$REPO"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# mtime 최신순 정렬 후 KEEP개를 건너뛴 나머지를 삭제.
# 백업 파일명은 타임스탬프뿐이라 공백/개행 없음 → 라인 단위 처리 안전.
deleted=0
i=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  i=$((i+1))
  if [ "$i" -le "$KEEP" ]; then
    continue
  fi
  if rm -f -- "$f"; then
    echo "$(ts) deleted $f" >> "$LOG"
    deleted=$((deleted+1))
  fi
done < <(ls -t movies.db.bak-* 2>/dev/null || true)

if [ "$i" -le "$KEEP" ]; then
  echo "$(ts) nothing to delete ($i backups, keep $KEEP)" >> "$LOG"
else
  echo "$(ts) done: deleted $deleted, kept $KEEP" >> "$LOG"
fi
