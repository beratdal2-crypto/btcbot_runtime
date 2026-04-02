from __future__ import annotations

import json
import os
import time

import pandas as pd

from config import SETTINGS


def _load_state() -> dict[str, dict]:
    if not os.path.exists(SETTINGS.coin_cooldown_state_path):
        return {}
    try:
        with open(SETTINGS.coin_cooldown_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(symbol).upper(): value for symbol, value in payload.items() if isinstance(value, dict)}


def _save_state(state: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(SETTINGS.coin_cooldown_state_path), exist_ok=True)
    with open(SETTINGS.coin_cooldown_state_path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def record_trade_outcome(symbol: str, pnl_pct: float, event_time: float | None = None) -> None:
    symbol = symbol.upper()
    now = event_time or time.time()
    state = _load_state()
    current = state.get(
        symbol,
        {
            "consecutive_losses": 0,
            "cooldown_until": 0.0,
            "last_pnl_pct": 0.0,
            "last_updated_at": 0.0,
        },
    )

    if pnl_pct < 0:
        current["consecutive_losses"] = int(current.get("consecutive_losses", 0)) + 1
    else:
        current["consecutive_losses"] = 0

    current["last_pnl_pct"] = float(pnl_pct)
    current["last_updated_at"] = float(now)

    if SETTINGS.coin_cooldown_enabled and current["consecutive_losses"] >= SETTINGS.coin_max_consecutive_losses:
        current["cooldown_until"] = float(now + SETTINGS.coin_cooldown_minutes * 60)
        current["consecutive_losses"] = 0
    elif float(current.get("cooldown_until", 0.0)) <= now:
        current["cooldown_until"] = 0.0

    state[symbol] = current
    _save_state(state)


def filter_symbols_by_cooldown(symbols: tuple[str, ...], now: float | None = None) -> tuple[tuple[str, ...], pd.DataFrame]:
    now = now or time.time()
    state = _load_state()
    rows: list[dict] = []
    eligible: list[str] = []

    for symbol in symbols:
        entry = state.get(symbol.upper(), {})
        cooldown_until = float(entry.get("cooldown_until", 0.0))
        is_cooling = SETTINGS.coin_cooldown_enabled and cooldown_until > now
        cooldown_left_seconds = max(0, int(cooldown_until - now))
        if not is_cooling:
            eligible.append(symbol)
        rows.append(
            {
                "symbol": symbol.upper(),
                "cooldown_active": is_cooling,
                "cooldown_left_minutes": round(cooldown_left_seconds / 60, 1),
                "last_pnl_pct": float(entry.get("last_pnl_pct", 0.0)) * 100,
                "last_updated_at": float(entry.get("last_updated_at", 0.0)),
            }
        )

    df = pd.DataFrame(rows)
    return tuple(eligible), df


def load_cooldown_state_frame() -> pd.DataFrame | None:
    state = _load_state()
    if not state:
        return None
    rows = []
    now = time.time()
    for symbol, entry in state.items():
        cooldown_until = float(entry.get("cooldown_until", 0.0))
        rows.append(
            {
                "symbol": symbol,
                "cooldown_active": cooldown_until > now,
                "cooldown_left_minutes": round(max(0.0, cooldown_until - now) / 60, 1),
                "last_pnl_pct": float(entry.get("last_pnl_pct", 0.0)) * 100,
                "last_updated_at": float(entry.get("last_updated_at", 0.0)),
            }
        )
    return pd.DataFrame(rows)
