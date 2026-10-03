#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v cloudflared >/dev/null 2>&1; then pkg install -y cloudflared; fi
mkdir -p logs
nohup cloudflared tunnel --url http://127.0.0.1:8000 > logs/tunnel.log 2>&1 &
echo $! > logs/tunnel.pid
echo "Cloudflare Quick Tunnel 시작"
echo "로그: tail -f logs/tunnel.log"
echo "공개 URL 확인: grep -o 'https://[^ ]*trycloudflare.com' logs/tunnel.log | tail -1"
