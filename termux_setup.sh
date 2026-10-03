#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
echo "== AI Auto Trader / Termux setup =="
pkg update -y
pkg install -y python git
echo
echo "Python:"
python --version
echo
echo "Git:"
git --version
echo
if [ ! -f "backend/.env" ]; then
  cp backend/.env.termux.example backend/.env
  echo "backend/.env 를 만들었습니다."
  echo "Toss API 정보는 이 휴대폰 파일에 직접 입력하세요."
fi
echo
echo "설치 완료. 추가 Python 패키지는 필요하지 않습니다."
echo "서버 실행: bash termux_start.sh"
echo "백그라운드: bash termux_background.sh"
