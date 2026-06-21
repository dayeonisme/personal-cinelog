#!/usr/bin/env bash
# VM 에서 실행: 왓챠 일일 동기화용 Chromium 설치 + systemd 타이머 등록.
# 선행조건: setup-vm.sh 로 .venv 가 이미 있어야 함.
# 사용: bash deploy/setup-watcha-sync.sh
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APPDIR"

if [ ! -x "$APPDIR/.venv/bin/python" ]; then
  echo "에러: .venv 없음. 먼저 bash deploy/setup-vm.sh 실행." >&2
  exit 1
fi

echo "==> Playwright Chromium + 시스템 의존성 설치 (headless 스크랩용)"
sudo NEEDRESTART_MODE=a "$APPDIR/.venv/bin/python" -m playwright install-deps chromium
"$APPDIR/.venv/bin/python" -m playwright install chromium

chmod +x deploy/watcha-sync.sh

echo "==> systemd 유닛 등록 (user=$USER, dir=$APPDIR)"
for unit in cinelog-watcha-sync.service cinelog-watcha-sync-failed.service cinelog-watcha-sync.timer; do
  sed -e "s|__USER__|$USER|g" -e "s|__APPDIR__|$APPDIR|g" "deploy/$unit" \
    | sudo tee "/etc/systemd/system/$unit" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now cinelog-watcha-sync.timer

echo "==> GNB 수동 동기화 버튼용 sudoers (gunicorn 유저가 무비번으로 서비스 start)"
SUDOERS_LINE="$USER ALL=(root) NOPASSWD: /usr/bin/systemctl start --no-block cinelog-watcha-sync.service"
echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/cinelog-watcha >/dev/null
sudo chmod 440 /etc/sudoers.d/cinelog-watcha
if sudo visudo -cf /etc/sudoers.d/cinelog-watcha >/dev/null 2>&1; then
  echo "  sudoers OK"
else
  echo "  sudoers 검증 실패 — 제거"; sudo rm -f /etc/sudoers.d/cinelog-watcha
fi

echo ""
echo "==> 다음 실행 예정"
systemctl list-timers cinelog-watcha-sync.timer --no-pager || true
echo ""
echo "설정 파일 확인: ~/.cinelog-watcha.env (WATCHA_EMAIL/PASSWORD/RATINGS_URL/WATCHLIST_URL)"
echo "지금 바로 1회 테스트:  sudo systemctl start cinelog-watcha-sync.service && journalctl -u cinelog-watcha-sync -f"
