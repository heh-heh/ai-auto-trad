#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
echo "== AI Auto Trader / Termux setup =="
pkg update -y
pkg install -y python git
if [ ! -d ".venv" ]; then python -m venv .venv; fi
source .venv/bin/activate
pip install -r backend/requirements.txt
if [ ! -f "backend/.env" ]; then
  cp .env.example backend/.env
  echo
  echo "[안내] backend/.env 파일이 생성되었습니다."
  echo "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET / TOSS_ACCOUNT_SEQ를 휴대폰에서 직접 입력하세요."
fi
echo
echo "설치 완료."
echo "서버 실행: ./termux_run.sh"
