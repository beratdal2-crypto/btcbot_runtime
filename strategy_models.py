from __future__ import annotations

import pandas as pd

from config import SETTINGS
from features import FEATURE_COLUMNS


def _is_mean_reversion_strategy(strategy_name: str) -> bool:
    return strategy_name in {
        "mean_reversion",
        "btc_5m_range",
        "alt_5m_pullback",
        "eth_5m_pullback",
        "ont_15m_pullback",
    }


def is_breakout_strategy(strategy_name: str) -> bool:
    return "breakout" in strategy_name


def strategy_model_key(strategy_name: str) -> str:
    return "mean_reversion" if _is_mean_reversion_strategy(strategy_name) else "trend"


def select_strategy_model(
    strategy_name: str,
    strategy_models: dict[str, object] | None = None,
    symbol_model=None,
    default_model=None,
):
    strategy_models = strategy_models or {}
    model = strategy_models.get(strategy_model_key(strategy_name))
    if model is not None:
        return model
    if symbol_model is not None:
        return symbol_model
    return default_model


def model_probability(model, df: pd.DataFrame) -> float:
    if model is None:
        return 0.5
    x = df[FEATURE_COLUMNS].iloc[-1:]
    return float(model.predict_proba(x)[0][1])


def strategy_edge_passes(
    strategy_name: str,
    active_probability: float,
    alternate_probability: float,
) -> bool:
    min_margin = (
        SETTINGS.mean_reversion_edge_min_margin
        if _is_mean_reversion_strategy(strategy_name)
        else SETTINGS.strategy_edge_min_margin
    )
    return (active_probability - alternate_probability) >= min_margin


def strategy_probability_passes(strategy_name: str, active_probability: float) -> bool:
    if _is_mean_reversion_strategy(strategy_name):
        min_probability = SETTINGS.mean_reversion_min_prob_up
    elif is_breakout_strategy(strategy_name):
        min_probability = SETTINGS.breakout_min_prob_up
    else:
        min_probability = SETTINGS.trend_min_prob_up
    return active_probability >= min_probability


def strategy_model_confirmation_passes(strategy_name: str, model_probability_value: float) -> bool:
    if not _is_mean_reversion_strategy(strategy_name):
        return True
    return model_probability_value >= SETTINGS.mean_reversion_min_model_prob_up


def enforce_strategy_signal_quality(
    strategy_name: str,
    scalp: int,
    active_probability: float,
    alternate_probability: float,
    model_probability_value: float | None = None,
) -> int:
    if scalp != 1:
        return scalp
    if model_probability_value is not None and not strategy_model_confirmation_passes(strategy_name, model_probability_value):
        return 0
    if not strategy_probability_passes(strategy_name, active_probability):
        return 0
    if not strategy_edge_passes(strategy_name, active_probability, alternate_probability):
        return 0
    return scalp


def should_force_ont_breakout_bias(
    symbol: str,
    regime: str,
    breakout_up_20: float,
    close_location: float,
    range_efficiency: float,
    volume_ratio: float,
) -> bool:
    return (
        symbol.upper() == "ONTUSDT"
        and regime in {"RANGE", "UPTREND"}
        and breakout_up_20 >= (SETTINGS.breakout_min_breakout_up_20 * 0.45)
        and close_location >= max(0.40, SETTINGS.breakout_min_close_location - 0.08)
        and range_efficiency >= max(0.26, SETTINGS.breakout_min_range_efficiency - 0.12)
        and volume_ratio >= max(0.72, SETTINGS.breakout_min_volume_ratio - 0.22)
    )


def apply_breakout_signal_bias(
    symbol: str,
    strategy_name: str,
    regime: str,
    trend: int,
    scalp: int,
    active_probability: float,
    breakout_signal: int,
    breakout_confidence: float,
) -> tuple[int, float]:
    if not is_breakout_strategy(strategy_name) or breakout_signal <= 0:
        return scalp, active_probability

    boosted_scalp = max(scalp, 1)
    boosted_probability = min(0.95, max(active_probability, breakout_confidence + 0.03))
    if symbol.upper() == "ONTUSDT" and regime in {"RANGE", "UPTREND"} and trend >= 0:
        boosted_probability = min(0.95, boosted_probability + 0.02)
    return boosted_scalp, boosted_probability
