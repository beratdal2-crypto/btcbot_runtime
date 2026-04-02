from __future__ import annotations


_DEFAULT_PROFILE = {
    "name": "default",
    "size_multiplier": 1.0,
    "spread_multiplier": 1.0,
    "depth_multiplier": 1.0,
    "buy_threshold_offset": 0.0,
    "entry_threshold_offset": 0.0,
    "max_single_bar_move_pct": 1.2,
    "min_probability_edge": None,
    "feature_depth_boost": 1.0,
    "feature_signed_volume_boost": 1.0,
    "feature_liquidity_stress_scale": 1.0,
}


_PROFILES = {
    "BTCUSDT": {
        "name": "major",
        "size_multiplier": 1.0,
        "spread_multiplier": 1.15,
        "depth_multiplier": 0.95,
        "buy_threshold_offset": -0.01,
        "entry_threshold_offset": -0.015,
        "max_single_bar_move_pct": 0.9,
    },
    "ETHUSDT": {
        "name": "major",
        "size_multiplier": 0.95,
        "spread_multiplier": 1.05,
        "depth_multiplier": 1.0,
        "buy_threshold_offset": 0.0,
        "entry_threshold_offset": 0.0,
        "max_single_bar_move_pct": 1.0,
    },
    "BNBUSDT": {
        "name": "large_alt",
        "size_multiplier": 0.85,
        "spread_multiplier": 0.95,
        "depth_multiplier": 1.1,
        "buy_threshold_offset": 0.01,
        "entry_threshold_offset": 0.01,
        "max_single_bar_move_pct": 1.0,
    },
    "SOLUSDT": {
        "name": "high_beta",
        "size_multiplier": 0.78,
        "spread_multiplier": 0.85,
        "depth_multiplier": 1.15,
        "buy_threshold_offset": 0.015,
        "entry_threshold_offset": 0.015,
        "max_single_bar_move_pct": 0.8,
    },
    "XRPUSDT": {
        "name": "alt",
        "size_multiplier": 0.82,
        "spread_multiplier": 0.82,
        "depth_multiplier": 1.15,
        "buy_threshold_offset": 0.015,
        "entry_threshold_offset": 0.015,
        "max_single_bar_move_pct": 0.85,
    },
    "ADAUSDT": {
        "name": "alt",
        "size_multiplier": 0.76,
        "spread_multiplier": 0.80,
        "depth_multiplier": 1.20,
        "buy_threshold_offset": 0.02,
        "entry_threshold_offset": 0.02,
        "max_single_bar_move_pct": 0.75,
    },
    "AVAXUSDT": {
        "name": "high_beta",
        "size_multiplier": 0.72,
        "spread_multiplier": 0.78,
        "depth_multiplier": 1.25,
        "buy_threshold_offset": 0.025,
        "entry_threshold_offset": 0.02,
        "max_single_bar_move_pct": 0.7,
    },
    "DOGEUSDT": {
        "name": "meme",
        "size_multiplier": 0.60,
        "spread_multiplier": 0.72,
        "depth_multiplier": 1.35,
        "buy_threshold_offset": 0.03,
        "entry_threshold_offset": 0.025,
        "max_single_bar_move_pct": 0.65,
    },
    "ONTUSDT": {
        "name": "alt",
        "size_multiplier": 0.74,
        "spread_multiplier": 1.10,
        "depth_multiplier": 1.22,
        "buy_threshold_offset": 0.012,
        "entry_threshold_offset": 0.012,
        "max_single_bar_move_pct": 0.72,
        "min_probability_edge": 0.018,
        "feature_depth_boost": 1.12,
        "feature_signed_volume_boost": 1.18,
        "feature_liquidity_stress_scale": 0.84,
    },
    "STGUSDT": {
        "name": "alt",
        "size_multiplier": 0.68,
        "spread_multiplier": 0.74,
        "depth_multiplier": 1.28,
        "buy_threshold_offset": 0.024,
        "entry_threshold_offset": 0.02,
        "max_single_bar_move_pct": 0.68,
    },
}


def risk_profile_for_symbol(symbol: str) -> dict[str, float | str]:
    merged = dict(_DEFAULT_PROFILE)
    merged.update(_PROFILES.get(symbol.upper(), {}))
    return merged
