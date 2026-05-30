#!/usr/bin/env bash
# macOS local dev: Postgres via Docker, API + UI native
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

docker compose -f docker/docker-compose.yml up postgres redis -d

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://retnza:retnza@localhost:5432/retnza}"
export PYTHONPATH="$ROOT:$ROOT/backend"

echo "Seeding database..."
"$ROOT/.venv/bin/python" backend/scripts/seed_db.py

echo "Starting API on :8000..."
"$ROOT/.venv/bin/uvicorn" app.main:app --reload --app-dir backend --port 8000 &
API_PID=$!

echo "Starting UI on :3000..."
(cd frontend && npm run dev) &
UI_PID=$!

trap "kill $API_PID $UI_PID 2>/dev/null" EXIT
wait
