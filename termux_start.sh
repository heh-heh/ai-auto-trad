#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
echo "AI Auto Trader - Termux"
echo
echo "Python only / no FastAPI / no Pydantic / no Rust"
echo "Server: http://127.0.0.1:8000"
echo
exec python termux_server/server.py
