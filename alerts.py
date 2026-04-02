from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

import pandas as pd

from config import SETTINGS


def ensure_alert_log() -> None:
    try:
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(SETTINGS.alerts_log_path) or os.path.getsize(SETTINGS.alerts_log_path) == 0:
            with open(SETTINGS.alerts_log_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "level", "category", "symbol", "message", "details"])
    except OSError:
        return


def log_alert(level: str, category: str, message: str, details: str = "", symbol: str = "") -> None:
    ensure_alert_log()
    try:
        with open(SETTINGS.alerts_log_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.now(timezone.utc).isoformat(),
                    level.upper(),
                    category,
                    symbol,
                    message,
                    details,
                ]
            )
    except OSError:
        return


def load_recent_alerts(limit: int = 50) -> pd.DataFrame | None:
    if not os.path.exists(SETTINGS.alerts_log_path) or os.path.getsize(SETTINGS.alerts_log_path) == 0:
        return None
    df = pd.read_csv(SETTINGS.alerts_log_path)
    if df.empty:
        return None
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df.tail(limit).reset_index(drop=True)
