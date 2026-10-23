#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/dev_db.sh" start

if [ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  echo "Не найден .venv. Установите зависимости:" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

cd "$ROOT_DIR/backend"
exec "$ROOT_DIR/.venv/bin/uvicorn" app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}"
