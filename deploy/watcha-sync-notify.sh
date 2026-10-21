#!/usr/bin/env bash
# 왓챠 동기화 실패 시 텔레그램 알림 발송.
# cinelog-watcha-sync-failed.service 가 호출.
# BOT_TOKEN/CHAT_ID 는 ~/.cinelog-watcha.env 에 저장 (gitignore).
set -euo pipefail

CONF="${CINELOG_WATCHA_ENV:-$HOME/.cinelog-watcha.env}"
[ -f "$CONF" ] && set -a && . "$CONF" && set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "텔레그램 설정 없음 (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정)" >&2
  exit 0
fi

MSG="🔴 Cinelog 왓챠 동기화 실패
세션 만료 또는 API 오류일 가능성이 높습니다.

Mac에서 갱신:
1. python3 tools/dump_watcha_state.py
2. scp watcha_state.json cinelog:~/movie-review/watcha_state.json

로그 확인: ssh cinelog 'journalctl -u cinelog-watcha-sync -n 50'"

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d text="${MSG}" \
  > /dev/null
