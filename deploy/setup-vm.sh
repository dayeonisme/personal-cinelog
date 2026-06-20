#!/usr/bin/env bash
# VM 에서 실행: 가상환경 생성 + 의존성 설치 + systemd 서비스 등록(부팅 자동 시작/크래시 재시작)
# 사용: 레포를 clone 한 뒤  bash deploy/setup-vm.sh
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APPDIR"

echo "==> 시스템 패키지 설치"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip

echo "==> 가상환경 + 의존성"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> swap 확인/생성 (e2-micro RAM 1GB 보호, OOM 방지)"
if swapon --show | grep -q .; then
  echo "    swap 이미 있음 — 건너뜀"
else
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  echo "    2G swap 생성 + 부팅 시 자동 활성화 등록"
fi

echo "==> systemd 서비스 등록 (user=$USER, dir=$APPDIR)"
sed -e "s|__USER__|$USER|g" -e "s|__APPDIR__|$APPDIR|g" deploy/cinelog.service \
  | sudo tee /etc/systemd/system/cinelog.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now cinelog

echo "==> 상태"
sudo systemctl --no-pager status cinelog | head -8
echo ""
echo "완료. Tailscale 주소로 접속: http://<이 VM 의 tailscale IP>:5001"
echo "Tailscale IP 확인:  tailscale ip -4"
