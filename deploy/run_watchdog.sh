#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"

if [ -x "$PROJECT_ROOT/venv312/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/venv312/bin/python"
fi

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -u btcbot_watchdog.py
