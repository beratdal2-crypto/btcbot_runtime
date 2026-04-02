from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from config import SETTINGS
from execution import Position, maybe_close_position


@dataclass
class ShadowState:
    position: Position
    realized_pnl_pct: float = 0.0


def _position_to_dict(position: Position) -> dict:
    return {
        "symbol": position.symbol,
        "side": position.side,
        "entry_price": position.entry_price,
        "qty": position.qty,
        "peak_price": position.peak_price,
        "is_open": position.is_open,
    }


def _position_from_dict(payload: dict | None) -> Position:
    payload = payload or {}
    return Position(
        symbol=str(payload.get("symbol", "")),
        side=payload.get("side"),
        entry_price=float(payload.get("entry_price", 0.0)),
        qty=float(payload.get("qty", 0.0)),
        peak_price=float(payload.get("peak_price", 0.0)),
        is_open=bool(payload.get("is_open", False)),
    )


def load_shadow_state() -> ShadowState:
    if not os.path.exists(SETTINGS.shadow_state_path):
        return ShadowState(position=Position())
    try:
        with open(SETTINGS.shadow_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ShadowState(position=Position())
    return ShadowState(
        position=_position_from_dict(payload.get("position")),
        realized_pnl_pct=float(payload.get("realized_pnl_pct", 0.0)),
    )


def save_shadow_state(state: ShadowState) -> None:
    os.makedirs(os.path.dirname(SETTINGS.shadow_state_path), exist_ok=True)
    with open(SETTINGS.shadow_state_path, "w") as f:
        json.dump(
            {
                "position": _position_to_dict(state.position),
                "realized_pnl_pct": state.realized_pnl_pct,
            },
            f,
            indent=2,
            sort_keys=True,
        )


def ensure_shadow_trade_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.shadow_trade_log_path) or os.path.getsize(SETTINGS.shadow_trade_log_path) == 0:
        with open(SETTINGS.shadow_trade_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "symbol", "action", "price", "qty", "profit_pct", "reason"])


def _log_shadow_trade(symbol: str, action: str, price: float, qty: float, profit_pct: float, reason: str) -> None:
    ensure_shadow_trade_log()
    with open(SETTINGS.shadow_trade_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(timezone.utc).isoformat(), symbol, action, price, qty, profit_pct, reason])


def process_shadow_position(
    state: ShadowState,
    symbol: str,
    current_price: float,
    decision: str,
    force_signal_exit: bool,
) -> ShadowState:
    position = state.position
    if position.is_open:
        updated_position, should_close, pnl_pct, reason = maybe_close_position(position, current_price)
        if force_signal_exit:
            should_close = True
            reason = "signal_exit"
        if should_close:
            _log_shadow_trade(symbol, "SHADOW_CLOSE", current_price, position.qty, pnl_pct, reason)
            state.realized_pnl_pct += pnl_pct
            state.position = Position()
            save_shadow_state(state)
            return state
        state.position = updated_position

    if not state.position.is_open and decision == "BUY":
        qty = 1.0
        state.position = Position(symbol=symbol, side="LONG", entry_price=current_price, qty=qty, peak_price=current_price, is_open=True)
        _log_shadow_trade(symbol, "SHADOW_BUY", current_price, qty, 0.0, "decision")

    save_shadow_state(state)
    return state
