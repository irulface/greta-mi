#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x backend/.venv/bin/python ]; then
  printf 'Run scripts/setup.sh first.\n'
  exit 1
fi
export APP_ENV=development
(cd backend && .venv/bin/alembic upgrade head)
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log &
GRETA_API_PID=$!
(cd backend && exec .venv/bin/python -m app.ingestion) &
GRETA_WORKER_PID=$!
(cd backend && exec .venv/bin/python -m app.agent_worker) &
GRETA_AGENT_PID=$!
trap 'kill "$GRETA_API_PID" "$GRETA_WORKER_PID" "$GRETA_AGENT_PID" 2>/dev/null || true' EXIT INT TERM
npm run dev -- --host 127.0.0.1
