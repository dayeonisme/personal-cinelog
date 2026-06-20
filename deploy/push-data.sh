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

echo "==> DB 전송"
gcloud compute scp "${ZONE_ARG[@]}" movies.db "$VM:$REMOTE_DIR/movies.db"

if [ -d static/uploads ] && [ -n "$(ls -A static/uploads 2>/dev/null)" ]; then
  echo "==> 업로드 이미지 전송"
  gcloud compute scp "${ZONE_ARG[@]}" --recurse static/uploads "$VM:$REMOTE_DIR/static/"
fi

echo "완료. VM 에서 서비스 재시작:  sudo systemctl restart cinelog"
