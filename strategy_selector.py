from __future__ import annotations

from config import SETTINGS
from coin_risk import risk_profile_for_symbol


def select_symbol_strategy(
    symbol: str,
    regime: str,
    atr_pct: float,
    volume_ratio: float,
    coin_score: float,
) -> dict[str, float | str]:
    profile = risk_profile_for_symbol(symbol)
    research_interval = SETTINGS.research_interval_value()
    strategy = {
        "name": "balanced",
        "buy_threshold_offset": 0.010,
        "entry_threshold_offset": 0.010,
        "spread_multiplier": 0.94,
        "depth_multiplier": 1.08,
        "size_multiplier": 0.85,
    }

    profile_name = str(profile.get("name", "default"))
    if (
        symbol.upper() == "BTCUSDT"
        and SETTINGS.btc_mean_reversion_only
        and not (
            regime == "RANGE"
            and atr_pct <= 0.008
            and volume_ratio >= 0.95
            and coin_score >= 20
        )
    ):
        strategy.update(
            {
                "name": "defensive",
                "buy_threshold_offset": 0.025,
                "entry_threshold_offset": 0.020,
                "spread_multiplier": 0.85,
                "depth_multiplier": 1.20,
                "size_multiplier": 0.55,
            }
        )
    elif (
        symbol.upper() == "ETHUSDT"
        and research_interval == "5m"
        and regime == "UPTREND"
        and atr_pct <= 0.011
        and volume_ratio >= 1.00
        and coin_score >= 35
    ):
        strategy.update(
            {
                "name": "eth_5m_continuation",
                "buy_threshold_offset": 0.006,
                "entry_threshold_offset": 0.006,
                "spread_multiplier": 0.95,
                "depth_multiplier": 1.05,
                "size_multiplier": 0.26,
            }
        )
    elif (
        symbol.upper() == "ETHUSDT"
        and research_interval == "5m"
        and regime == "RANGE"
        and atr_pct <= 0.012
        and volume_ratio >= 0.92
        and coin_score >= 35
    ):
        strategy.update(
            {
                "name": "eth_5m_pullback",
                "buy_threshold_offset": 0.010,
                "entry_threshold_offset": 0.008,
                "spread_multiplier": 0.92,
                "depth_multiplier": 1.10,
                "size_multiplier": 0.26,
            }
        )
    elif (
        symbol.upper() == "ONTUSDT"
        and research_interval == "15m"
        and regime in {"RANGE", "UPTREND"}
        and atr_pct <= 0.020
        and volume_ratio >= 0.10
        and coin_score >= 16
    ):
        strategy.update(
            {
                "name": "ont_15m_breakout",
                "buy_threshold_offset": -0.008,
                "entry_threshold_offset": -0.010,
                "spread_multiplier": 1.12,
                "depth_multiplier": 1.02,
                "size_multiplier": 0.22,
            }
        )
    elif (
        symbol.upper() == "ONTUSDT"
        and research_interval == "15m"
        and regime == "RANGE"
        and atr_pct <= 0.018
        and volume_ratio < 0.10
        and coin_score >= 16
    ):
        strategy.update(
            {
                "name": "ont_15m_pullback",
                "buy_threshold_offset": 0.006,
                "entry_threshold_offset": 0.004,
                "spread_multiplier": 0.95,
                "depth_multiplier": 1.04,
                "size_multiplier": 0.20,
            }
        )
    elif (
        symbol.upper() == "ONTUSDT"
        and research_interval == "5m"
        and regime == "UPTREND"
        and atr_pct <= 0.016
        and volume_ratio >= 0.98
        and coin_score >= 18
    ):
        strategy.update(
            {
                "name": "ont_5m_breakout",
                "buy_threshold_offset": 0.008,
                "entry_threshold_offset": 0.006,
                "spread_multiplier": 0.94,
                "depth_multiplier": 1.06,
                "size_multiplier": 0.22,
            }
        )
    elif (
        symbol.upper() != "BTCUSDT"
        and research_interval == "5m"
        and regime == "UPTREND"
        and atr_pct <= 0.014
        and volume_ratio >= 1.15
        and coin_score >= 25
    ):
        strategy.update(
            {
                "name": "alt_5m_breakout",
                "buy_threshold_offset": 0.018,
                "entry_threshold_offset": 0.016,
                "spread_multiplier": 0.86,
                "depth_multiplier": 1.18,
                "size_multiplier": 0.22,
            }
        )
    elif (
        symbol.upper() != "BTCUSDT"
        and research_interval == "5m"
        and regime in {"RANGE", "UPTREND"}
        and atr_pct <= 0.012
        and volume_ratio >= 0.95
        and coin_score >= 25
    ):
        strategy.update(
            {
                "name": "alt_5m_pullback",
                "buy_threshold_offset": 0.012,
                "entry_threshold_offset": 0.010,
                "spread_multiplier": 0.88,
                "depth_multiplier": 1.16,
                "size_multiplier": 0.24,
            }
        )
    elif profile_name in {"meme", "high_beta"} or atr_pct >= 0.0055:
        strategy.update(
            {
                "name": "defensive",
                "buy_threshold_offset": 0.015,
                "entry_threshold_offset": 0.015,
                "spread_multiplier": 0.88,
                "depth_multiplier": 1.18,
                "size_multiplier": 0.78,
            }
        )
    elif regime == "UPTREND" and volume_ratio >= 1.15 and coin_score >= 55:
        strategy.update(
            {
                "name": "breakout",
                "buy_threshold_offset": -0.010,
                "entry_threshold_offset": -0.010,
                "spread_multiplier": 1.08,
                "depth_multiplier": 0.92,
                "size_multiplier": 1.10,
            }
        )
    elif (
        symbol.upper() == "BTCUSDT"
        and research_interval == "5m"
        and regime == "UPTREND"
        and atr_pct <= 0.012
        and volume_ratio >= 1.10
        and coin_score >= 15
    ):
        strategy.update(
            {
                "name": "btc_5m_breakout",
                "buy_threshold_offset": 0.020,
                "entry_threshold_offset": 0.018,
                "spread_multiplier": 0.90,
                "depth_multiplier": 1.15,
                "size_multiplier": 0.28,
            }
        )
    elif (
        symbol.upper() == "BTCUSDT"
        and research_interval == "5m"
        and regime == "RANGE"
        and atr_pct <= 0.010
        and volume_ratio >= 1.00
        and coin_score >= 15
    ):
        strategy.update(
            {
                "name": "btc_5m_range",
                "buy_threshold_offset": 0.012,
                "entry_threshold_offset": 0.012,
                "spread_multiplier": 0.90,
                "depth_multiplier": 1.12,
                "size_multiplier": 0.30,
            }
        )
    elif (
        symbol.upper() == "BTCUSDT"
        and regime == "RANGE"
        and atr_pct <= 0.008
        and volume_ratio >= 0.95
        and coin_score >= 20
    ):
        strategy.update(
            {
                "name": "mean_reversion",
                "buy_threshold_offset": 0.000,
                "entry_threshold_offset": -0.004,
                "spread_multiplier": 0.92,
                "depth_multiplier": 1.08,
                "size_multiplier": 0.40,
            }
        )
    elif regime == "RANGE":
        strategy.update(
            {
                "name": "range_balance",
                "buy_threshold_offset": 0.006,
                "entry_threshold_offset": 0.004,
                "spread_multiplier": 0.95,
                "depth_multiplier": 1.05,
                "size_multiplier": 0.92,
            }
        )
    return strategy
