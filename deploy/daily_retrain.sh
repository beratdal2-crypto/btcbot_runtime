#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
ARCHIVE_DIR="$PROJECT_ROOT/logs/report_archives/$TIMESTAMP"
MPLCONFIGDIR="$PROJECT_ROOT/logs/.mplconfig"

if [ -x "$PROJECT_ROOT/venv312/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/venv312/bin/python"
fi

cd "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/logs" "$MPLCONFIGDIR" "$ARCHIVE_DIR"
export MPLCONFIGDIR

"$PYTHON_BIN" -u archive_market_data.py
"$PYTHON_BIN" -u trainer.py
"$PYTHON_BIN" -u rl_train.py
"$PYTHON_BIN" -u optimize_parameters.py
"$PYTHON_BIN" -u backtest.py
"$PYTHON_BIN" -u walkforward.py
"$PYTHON_BIN" -u live_readiness.py
"$PYTHON_BIN" -u health_report.py
"$PYTHON_BIN" -u live_shadow_analysis.py
"$PYTHON_BIN" -u daily_summary.py
"$PYTHON_BIN" -u security_audit.py
"$PYTHON_BIN" -u sqlite_store.py

for report_file in \
  "$PROJECT_ROOT/logs/backtest_trades.csv" \
  "$PROJECT_ROOT/logs/backtest_summary.csv" \
  "$PROJECT_ROOT/logs/walkforward_results.csv" \
  "$PROJECT_ROOT/logs/optimization_results.csv" \
  "$PROJECT_ROOT/logs/best_params.json" \
  "$PROJECT_ROOT/logs/symbol_optimization_results.csv" \
  "$PROJECT_ROOT/logs/symbol_best_params.json" \
  "$PROJECT_ROOT/logs/symbol_training_report.csv" \
  "$PROJECT_ROOT/logs/live_readiness.json" \
  "$PROJECT_ROOT/logs/system_health.json" \
  "$PROJECT_ROOT/logs/live_shadow_analysis.csv" \
  "$PROJECT_ROOT/logs/daily_summary.json" \
  "$PROJECT_ROOT/logs/security_audit.json" \
  "$PROJECT_ROOT/logs/btcbot.sqlite3"
do
  if [ -f "$report_file" ]; then
    cp "$report_file" "$ARCHIVE_DIR/"
  fi
done

for archive_file in "$PROJECT_ROOT"/logs/market_data_archive*.csv
do
  if [ -f "$archive_file" ]; then
    cp "$archive_file" "$ARCHIVE_DIR/"
  fi
done

printf '%s\n' \
  "timestamp=$TIMESTAMP" \
  "python_bin=$PYTHON_BIN" \
  "archive_dir=$ARCHIVE_DIR" \
  > "$ARCHIVE_DIR/manifest.txt"
