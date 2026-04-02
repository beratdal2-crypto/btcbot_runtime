#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
MPLCONFIGDIR="$PROJECT_ROOT/logs/.mplconfig"

if [ -x "$PROJECT_ROOT/venv312/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/venv312/bin/python"
fi

cd "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/logs" "$MPLCONFIGDIR"
export MPLCONFIGDIR
exec "$PYTHON_BIN" -u archive_market_data.py
