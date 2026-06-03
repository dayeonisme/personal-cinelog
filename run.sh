#!/bin/bash
# CINELOG 실행 스크립트
# OMDb 무료 API 키 발급: https://www.omdbapi.com/apikey.aspx

export OMDB_API_KEY="${OMDB_API_KEY:-YOUR_FREE_OMDB_KEY}"

pip install -r requirements.txt -q

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CINELOG  ·  http://localhost:5001"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python app.py
