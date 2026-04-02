from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone

import pandas as pd

from alerts import log_alert
from config import SETTINGS
from notifications import notify_event


def _load_state() -> dict:
    if not os.path.exists(SETTINGS.watchdog_state_path):
        return {}
    try:
        with open(SETTINGS.watchdog_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS.watchdog_state_path), exist_ok=True)
    with open(SETTINGS.watchdog_state_path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def latest_heartbeat_age_seconds() -> float | None:
    if not os.path.exists(SETTINGS.heartbeat_log_path) or os.path.getsize(SETTINGS.heartbeat_log_path) == 0:
        return None
    heartbeat = pd.read_csv(SETTINGS.heartbeat_log_path)
    if heartbeat.empty or "time" not in heartbeat.columns:
        return None
    latest = pd.to_datetime(heartbeat["time"], errors="coerce").dropna()
    if latest.empty:
        return None
    last_time = latest.iloc[-1].to_pydatetime().replace(tzinfo=timezone.utc)
    return max(0.0, time.time() - last_time.timestamp())


def recent_error_count() -> int:
    if not os.path.exists("/Users/beratdal/btcbot_runtime/logs/bot.err"):
        return 0
    try:
        with open("/Users/beratdal/btcbot_runtime/logs/bot.err", "r") as f:
            lines = f.readlines()[-100:]
    except OSError:
        return 0
    patterns = ("Hata:", "SSL", "Operation not permitted", "Traceback")
    return sum(1 for line in lines if any(pattern in line for pattern in patterns))


def should_restart_runner() -> tuple[bool, str]:
    age = latest_heartbeat_age_seconds()
    if age is None:
        return False, "heartbeat_yok"
    if age > SETTINGS.watchdog_heartbeat_timeout_seconds:
        return True, f"heartbeat_gecikmesi:{int(age)}"
    error_count = recent_error_count()
    if error_count >= SETTINGS.watchdog_error_threshold:
        return True, f"hata_sayisi:{error_count}"
    return False, "saglikli"


def run_watchdog() -> None:
    should_restart, reason = should_restart_runner()
    state = _load_state()
    state["checked_at"] = datetime.now(timezone.utc).isoformat()
    state["last_reason"] = reason
    state["restart_needed"] = should_restart

    if should_restart:
        command = ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.berat.btcbot.runner"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        state["last_restart_at"] = datetime.now(timezone.utc).isoformat()
        state["last_restart_returncode"] = result.returncode
        log_alert("ERROR", "watchdog", "Runner yeniden baslatildi", details=reason)
        notify_event("ERROR", "watchdog", "Watchdog restart atti", reason)
    elif reason != "saglikli":
        log_alert("WARN", "watchdog", "Watchdog uyarisi", details=reason)
        notify_event("WARN", "watchdog", "Watchdog uyarisi", reason)
    _save_state(state)
    print(reason)


if __name__ == "__main__":
    run_watchdog()
