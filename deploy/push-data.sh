#!/usr/bin/env bash
# Mac 에서 실행: 로컬 DB와 업로드 이미지를 VM 으로 전송 (gitignore 라 git clone 으로는 안 따라옴)
# 사용: deploy/push-data.sh <gcp-vm-이름> [zone] [원격경로]
#   예: deploy/push-data.sh cinelog-vm us-central1-a
set -euo pipefail

VM="${1:?VM 이름 필요 (예: cinelog-vm)}"
ZONE="${2:-}"
REMOTE_DIR="${3:-~/movie-review}"

ZONE_ARG=()
[ -n "$ZONE" ] && ZONE_ARG=(--zone="$ZONE")

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# 원격 cinelog 및 watcha-sync 서비스/타이머를 먼저 중지해야 한다(README 참고).
# 실행 중인 로컬 DB는 WAL에 최신 데이터가 있을 수 있으므로 스냅샷을 전송한다.
SNAPSHOT_DIR="$(mktemp -d)"
trap 'rm -rf "$SNAPSHOT_DIR"' EXIT
python3 tools/backup_sqlite.py movies.db "$SNAPSHOT_DIR/movies.db"

echo "==> DB 스냅샷 전송"
gcloud compute scp "${ZONE_ARG[@]}" "$SNAPSHOT_DIR/movies.db" "$VM:$REMOTE_DIR/movies.db"

if [ -d static/uploads ] && [ -n "$(ls -A static/uploads 2>/dev/null)" ]; then
  echo "==> 업로드 이미지 전송"
  gcloud compute scp "${ZONE_ARG[@]}" --recurse static/uploads "$VM:$REMOTE_DIR/static/"
fi

echo "완료. VM 에서 서비스 재시작:  sudo systemctl restart cinelog"
