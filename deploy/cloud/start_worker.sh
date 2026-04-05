#!/usr/bin/env bash
set -euo pipefail

if [[ "${CLOUD_SKIP_PREFLIGHT:-false}" != "true" ]]; then
  echo "[cloud] preflight: live_readiness"
  python live_readiness.py

  echo "[cloud] preflight: verify_live"
  python verify_live.py

  echo "[cloud] preflight: verify_ont_live"
  python verify_ont_live.py || true
fi

echo "[cloud] starting worker: main.py"
exec python main.py
