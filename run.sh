#!/bin/bash
# CINELOG 실행 스크립트
# TMDb API 키 설정은 .env 파일의 TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY를 사용합니다.

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

uv sync --quiet

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CINELOG  ·  http://localhost:5001"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

uv run python app.py
