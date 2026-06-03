#!/bin/bash
# ────────────────────────────────────────────────────────────
#  CINELOG · macOS 자동 시작 설치 스크립트
#  실행: bash install_autostart.sh
# ────────────────────────────────────────────────────────────

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_NAME="com.cinelog.app"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$HOME/Library/Logs/Cinelog"
PYTHON=$(which python3)

# OMDB API 키 입력
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CINELOG 자동 시작 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "OMDb API 키를 입력하세요 (없으면 엔터): " OMDB_KEY
OMDB_KEY="${OMDB_KEY:-YOUR_FREE_OMDB_KEY}"

# 디렉토리 생성
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"

# plist 생성
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_NAME}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${APP_DIR}/app.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${APP_DIR}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>OMDB_API_KEY</key>
    <string>${OMDB_KEY}</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/cinelog.log</string>

  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/cinelog.err</string>
</dict>
</plist>
EOF

# 기존 실행 중이면 unload
launchctl unload "$PLIST_PATH" 2>/dev/null

# 등록 및 시작
launchctl load "$PLIST_PATH"

sleep 2

# 확인
if curl -s http://localhost:5001/api/entries > /dev/null 2>&1; then
  echo ""
  echo "✓ 설치 완료! 서버가 실행 중입니다."
  echo "  → http://localhost:5001"
  echo ""
  echo "  이제 Mac을 재시작해도 자동으로 시작됩니다."
  echo ""
else
  echo ""
  echo "서버 시작 중... 잠시 후 http://localhost:5001 에 접속하세요."
  echo ""
fi

echo "로그 위치: $LOG_DIR"
echo ""
echo "제거하려면:"
echo "  launchctl unload $PLIST_PATH"
echo "  rm $PLIST_PATH"
