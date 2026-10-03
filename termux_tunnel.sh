#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared 설치 중..."
  pkg install -y cloudflared
fi
echo "AI Auto Trader public HTTPS tunnel"
echo "휴대폰 서버가 먼저 실행되어 있어야 합니다."
echo "http://127.0.0.1:8000/health 확인 후 진행하세요."
echo
exec cloudflared tunnel --url http://127.0.0.1:8000
