#!/usr/bin/env bash
# 一键启动：后端(8000) + 前端(5173)
set -e
cd "$(dirname "$0")"

if [ ! -d backend/.venv ]; then
  echo "==> 初始化后端虚拟环境"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements.txt
fi

if [ ! -d frontend/node_modules ]; then
  echo "==> 安装前端依赖"
  (cd frontend && npm install)
fi

[ -f backend/.env ] || cp backend/.env.example backend/.env
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env

echo "==> 启动后端 (http://127.0.0.1:8000)"
(cd backend && ./.venv/bin/python run.py) &
BACK_PID=$!

echo "==> 启动前端 (http://127.0.0.1:5173)"
(cd frontend && npm run dev) &
FRONT_PID=$!

trap "kill $BACK_PID $FRONT_PID 2>/dev/null" EXIT INT TERM
wait
