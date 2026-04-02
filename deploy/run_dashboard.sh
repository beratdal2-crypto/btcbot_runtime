#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STREAMLIT_BIN="$PROJECT_ROOT/venv/bin/streamlit"

if [ -x "$PROJECT_ROOT/venv312/bin/streamlit" ]; then
  STREAMLIT_BIN="$PROJECT_ROOT/venv312/bin/streamlit"
fi

cd "$PROJECT_ROOT"
exec "$STREAMLIT_BIN" run dashboard.py \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.fileWatcherType none \
  --browser.gatherUsageStats false
