from __future__ import annotations

from coin_risk import risk_profile_for_symbol
from config import SETTINGS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_factor(coin_score: float | None) -> float:
    if coin_score is None:
        return 1.0
    normalized = _clamp(coin_score / 100.0, 0.0, 1.0)
    raw = SETTINGS.sizing_score_floor + (SETTINGS.sizing_score_ceiling - SETTINGS.sizing_score_floor) * normalized
    return _clamp(raw, SETTINGS.sizing_score_floor, SETTINGS.sizing_score_ceiling)


def volatility_factor(atr_pct: float | None) -> float:
    if atr_pct is None or atr_pct <= 0:
        return 1.0
    raw = SETTINGS.sizing_target_atr_pct / max(atr_pct, 1e-6)
    return _clamp(raw, SETTINGS.sizing_min_volatility_factor, SETTINGS.sizing_max_volatility_factor)


def compute_position_fraction(
    base_fraction: float | None = None,
    atr_pct: float | None = None,
    coin_score: float | None = None,
    confidence: float | None = None,
    symbol: str | None = None,
) -> float:
    base = SETTINGS.risk_per_trade if base_fraction is None else base_fraction
    sized = base
    profile = risk_profile_for_symbol(symbol or SETTINGS.symbol)
    if SETTINGS.dynamic_sizing_enabled:
        sized *= score_factor(coin_score)
        sized *= volatility_factor(atr_pct)
        if confidence is not None:
            sized *= _clamp(0.75 + max(0.0, confidence) * 1.2, 0.75, 1.55)
        sized *= float(profile["size_multiplier"])
    return _clamp(
        sized,
        SETTINGS.position_size_min_fraction,
        SETTINGS.position_size_max_fraction,
    )
