#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[ERROR] 먼저 bash termux_setup.sh 를 실행하세요."
  exit 1
fi

termux-wake-lock 2>/dev/null || true
mkdir -p logs

nohup bash termux_run.sh > logs/server.log 2>&1 &
PID=$!
echo "$PID" > logs/server.pid

echo "AI Auto Trader 백그라운드 서버 시작"
echo "PID: $PID"
echo "로그: tail -f logs/server.log"
echo "종료: bash termux_stop.sh"
