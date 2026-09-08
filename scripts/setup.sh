#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
GRETA_PYTHON="${GRETA_PYTHON:-python3.12}"
if ! command -v "$GRETA_PYTHON" >/dev/null 2>&1; then GRETA_PYTHON=python3.11; fi
if ! command -v "$GRETA_PYTHON" >/dev/null 2>&1; then
  printf 'Install Python 3.12 (preferred) or 3.11, then rerun.\n'; exit 1
fi
"$GRETA_PYTHON" -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
npm ci
printf '\nSetup complete. Run ./scripts/dev.sh and open http://127.0.0.1:3000\n'
