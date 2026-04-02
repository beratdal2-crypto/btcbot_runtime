from __future__ import annotations

import pandas as pd

from config import SETTINGS


def compression_breakout_signal(df: pd.DataFrame, prob_up: float | None = None) -> tuple[int, float]:
    if df.empty:
        return 0, 0.0

    row = df.iloc[-1]
    setup_conditions = [
        float(row.get("bb_width", 1.0)) <= SETTINGS.breakout_max_bb_width,
        float(row.get("breakout_up_20", -1.0)) >= SETTINGS.breakout_min_breakout_up_20,
        float(row.get("volume_ratio", 0.0)) >= SETTINGS.breakout_min_volume_ratio,
        float(row.get("close_location", 0.0)) >= SETTINGS.breakout_min_close_location,
        float(row.get("range_efficiency", 0.0)) >= SETTINGS.breakout_min_range_efficiency,
        float(row.get("signed_volume_proxy", -1.0)) >= SETTINGS.breakout_min_signed_volume_proxy,
        float(row.get("price_vs_ema20", -1.0)) >= SETTINGS.breakout_min_price_vs_ema20,
    ]
    hits = sum(1 for item in setup_conditions if item)
    confidence = 0.25 + hits * 0.08
    if prob_up is not None:
        confidence = max(confidence, float(prob_up))
    confidence = min(confidence, 0.95)

    if hits >= 5 and confidence >= SETTINGS.breakout_prob_floor:
        return 1, confidence
    return 0, confidence
