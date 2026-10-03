#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
termux-wake-lock 2>/dev/null || true
mkdir -p logs
nohup python termux_server/server.py > logs/server.log 2>&1 &
PID=$!
echo "$PID" > logs/server.pid
echo "AI Auto Trader 백그라운드 서버 시작"
echo "PID: $PID"
echo "로그: tail -f logs/server.log"
echo "종료: bash termux_stop.sh"
