from __future__ import annotations

import json
import os

import pandas as pd

from config import SETTINGS


def _load_alerts() -> pd.DataFrame | None:
    if not os.path.exists(SETTINGS.alerts_log_path) or os.path.getsize(SETTINGS.alerts_log_path) == 0:
        return None
    df = pd.read_csv(SETTINGS.alerts_log_path)
    if df.empty:
        return None
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df


def _load_self_protection() -> dict:
    if not os.path.exists(SETTINGS.self_protection_state_path):
        return {}
    try:
        with open(SETTINGS.self_protection_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_kill_switch() -> tuple[bool, str]:
    alerts = _load_alerts()
    protection = _load_self_protection()

    if protection.get("mode") == "blocked":
        return True, f"self_protection:{protection.get('reason', 'blocked')}"

    if alerts is None or alerts.empty:
        return False, "ok"

    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(minutes=SETTINGS.kill_switch_window_minutes)
    recent = alerts[alerts["time"] >= cutoff]
    if recent.empty:
        return False, "ok"

    severe = recent[recent["level"].astype(str).isin(["ERROR", "CRITICAL"])]
    if len(severe) >= SETTINGS.kill_switch_error_threshold:
        return True, f"error_threshold:{len(severe)}"

    api_like = recent[
        recent["category"].astype(str).isin(["api", "watchdog", "main_loop", "slippage"])
        & recent["level"].astype(str).isin(["ERROR", "CRITICAL"])
    ]
    if len(api_like) >= SETTINGS.kill_switch_error_threshold:
        return True, f"api_threshold:{len(api_like)}"
    return False, "ok"


def save_kill_switch_state(active: bool, reason: str) -> None:
    os.makedirs(os.path.dirname(SETTINGS.kill_switch_state_path), exist_ok=True)
    with open(SETTINGS.kill_switch_state_path, "w") as f:
        json.dump({"active": active, "reason": reason}, f, indent=2, sort_keys=True)
