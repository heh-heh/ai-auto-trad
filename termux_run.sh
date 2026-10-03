#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "[ERROR] .venv가 없습니다. 먼저 ./termux_setup.sh 를 실행하세요."
  exit 1
fi
source .venv/bin/activate
if [ ! -f "backend/.env" ]; then
  echo "[ERROR] backend/.env가 없습니다. 먼저 ./termux_setup.sh 를 실행하세요."
  exit 1
fi
export PYTHONPATH="$PWD/backend"
echo "======================================"
echo " AI Auto Trader - Termux Server"
echo "======================================"
echo " Local:  http://127.0.0.1:8000"
echo " LAN:    http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000"
echo " Mode:   paper"
echo
echo "종료: Ctrl+C"
echo "======================================"
exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
