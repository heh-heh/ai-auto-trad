#!/data/data/com.termux/files/usr/bin/bash
pkill -f "uvicorn app.main:app" || true
echo "AI Auto Trader 서버를 종료했습니다."
