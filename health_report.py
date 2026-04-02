from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from config import SETTINGS


def _safe_read_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def _heartbeat_age_seconds() -> float | None:
    heartbeat = _safe_read_csv(SETTINGS.heartbeat_log_path)
    if heartbeat is None or "time" not in heartbeat.columns:
        return None
    ts = pd.to_datetime(heartbeat["time"], errors="coerce", utc=True).dropna()
    if ts.empty:
        return None
    return max(0.0, (pd.Timestamp.utcnow() - ts.iloc[-1]).total_seconds())


def _dashboard_health() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=2) as response:
            body = response.read().decode("utf-8", errors="ignore").strip()
        return {"ok": body.lower() == "ok", "response": body}
    except Exception as exc:
        return {"ok": False, "response": str(exc)}


def build_system_health_report() -> dict:
    dashboard = _dashboard_health()
    heartbeat_age = _heartbeat_age_seconds()
    alerts = _safe_read_csv(SETTINGS.alerts_log_path)
    recent_alert_count = 0
    if alerts is not None and "time" in alerts.columns:
        alerts["time"] = pd.to_datetime(alerts["time"], errors="coerce", utc=True)
        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(hours=24)
        recent_alert_count = int(len(alerts[alerts["time"] >= cutoff]))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_ok": bool(dashboard["ok"]),
        "dashboard_response": dashboard["response"],
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_stale": bool(
            heartbeat_age is None or heartbeat_age > SETTINGS.watchdog_heartbeat_timeout_seconds
        ),
        "recent_alert_count_24h": recent_alert_count,
        "kill_switch_file_exists": os.path.exists(SETTINGS.kill_switch_state_path),
        "portfolio_report_exists": os.path.exists(SETTINGS.portfolio_report_path),
        "symbol_best_params_exists": os.path.exists(SETTINGS.symbol_best_params_path),
    }
    os.makedirs(os.path.dirname(SETTINGS.system_health_path), exist_ok=True)
    with open(SETTINGS.system_health_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    return report


if __name__ == "__main__":
    print(build_system_health_report())
