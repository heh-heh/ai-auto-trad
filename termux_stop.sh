#!/data/data/com.termux/files/usr/bin/bash
if [ -f logs/server.pid ]; then
  PID=$(cat logs/server.pid)
  kill "$PID" 2>/dev/null || true
  rm -f logs/server.pid
fi
pkill -f "termux_server/server.py" 2>/dev/null || true
termux-wake-unlock 2>/dev/null || true
echo "AI Auto Trader 서버를 종료했습니다."
