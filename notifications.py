from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from config import SETTINGS


def ensure_notification_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.notification_log_path) or os.path.getsize(SETTINGS.notification_log_path) == 0:
        with open(SETTINGS.notification_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "channel", "level", "category", "title", "message", "delivered", "details"])


def _log_notification(channel: str, level: str, category: str, title: str, message: str, delivered: bool, details: str = "") -> None:
    ensure_notification_log()
    with open(SETTINGS.notification_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                channel,
                level,
                category,
                title,
                message,
                delivered,
                details,
            ]
        )


def _telegram_enabled() -> bool:
    return bool(
        SETTINGS.notification_enabled
        and SETTINGS.telegram_bot_token
        and SETTINGS.telegram_chat_id
    )


def _send_telegram_message(text: str) -> tuple[bool, str]:
    if not _telegram_enabled():
        return False, "telegram_disabled"
    url = f"https://api.telegram.org/bot{SETTINGS.telegram_bot_token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": SETTINGS.telegram_chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(url, data=payload, timeout=SETTINGS.notification_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return bool(body.get("ok")), ""
    except Exception as exc:
        return False, str(exc)


def notify_event(level: str, category: str, title: str, message: str) -> None:
    text = f"[{level}] {title}\n{message}"
    delivered, details = _send_telegram_message(text)
    _log_notification("telegram" if _telegram_enabled() else "log", level, category, title, message, delivered, details)
