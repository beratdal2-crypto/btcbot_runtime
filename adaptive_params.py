from __future__ import annotations

import json
import os

from coin_risk import risk_profile_for_symbol
from config import SETTINGS


def _load_symbol_best_params() -> dict[str, dict]:
    if not os.path.exists(SETTINGS.symbol_best_params_path):
        return {}
    try:
        with open(SETTINGS.symbol_best_params_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key).upper(): value for key, value in payload.items() if isinstance(value, dict)}


def symbol_threshold_overrides(symbol: str, coin_score: float | None = None) -> dict[str, float]:
    score = 50.0 if coin_score is None else max(0.0, min(100.0, coin_score))
    score_offset = (score - 50.0) / 50.0
    profile = risk_profile_for_symbol(symbol)
    buy_threshold = max(0.48, min(0.72, SETTINGS.buy_threshold - score_offset * 0.03 + float(profile["buy_threshold_offset"])))
    entry_score_threshold = max(0.40, min(0.68, SETTINGS.entry_score_threshold - score_offset * 0.04 + float(profile["entry_threshold_offset"])))
    spread_bps_limit = max(4.0, (SETTINGS.max_entry_spread_bps + score_offset * 4.0) * float(profile["spread_multiplier"]))
    depth_limit = max(500.0, (SETTINGS.min_entry_depth_notional - score_offset * 600.0) * float(profile["depth_multiplier"]))
    overrides = {
        "buy_threshold": buy_threshold,
        "sell_threshold": 1.0 - buy_threshold,
        "entry_score_threshold": entry_score_threshold,
        "max_entry_spread_bps": spread_bps_limit,
        "min_entry_depth_notional": depth_limit,
        "take_profit_pct": SETTINGS.take_profit_pct,
        "stop_loss_pct": SETTINGS.stop_loss_pct,
        "signal_exit_prob_threshold": SETTINGS.signal_exit_prob_threshold,
        "profile_name": str(profile["name"]),
    }
    symbol_payload = _load_symbol_best_params().get(symbol.upper(), {})
    params = symbol_payload.get("parameters", {})
    for key in list(overrides.keys()):
        if key in params:
            overrides[key] = params[key]
    return overrides
