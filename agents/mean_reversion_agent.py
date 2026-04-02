from __future__ import annotations

import pandas as pd

from config import SETTINGS


def mean_reversion_signal(df: pd.DataFrame, prob_up: float | None = None) -> tuple[int, float]:
    if df.empty or not SETTINGS.mean_reversion_enabled:
        return 0, 0.0

    if prob_up is not None and prob_up < SETTINGS.mean_reversion_min_model_prob_up:
        return 0, float(prob_up)

    row = df.iloc[-1]
    setup_conditions = [
        float(row.get("rsi", 100.0)) <= SETTINGS.mean_reversion_rsi_max,
        float(row.get("bb_pos", 1.0)) <= SETTINGS.mean_reversion_bb_pos_max,
        float(row.get("range_pos_20", 1.0)) <= SETTINGS.mean_reversion_range_pos_max,
        float(row.get("return_5", 0.0)) <= SETTINGS.mean_reversion_return_5_min,
        float(row.get("atr_pct", 1.0)) <= SETTINGS.mean_reversion_atr_pct_max,
        float(row.get("price_vs_ema20", 1.0)) <= SETTINGS.mean_reversion_price_vs_ema20_max,
    ]
    reversal_confirmed = (
        float(row.get("rsi_delta", 0.0)) >= SETTINGS.mean_reversion_rsi_delta_min
        and (
            float(row.get("body_pct", -1.0)) >= SETTINGS.mean_reversion_body_pct_min
            or float(row.get("lower_wick_pct", 0.0)) >= SETTINGS.mean_reversion_lower_wick_min
        )
        and float(row.get("close_location", 0.0)) >= SETTINGS.mean_reversion_min_close_location
        and float(row.get("signed_volume_proxy", -1.0)) >= SETTINGS.mean_reversion_min_signed_volume_proxy
    )

    hits = sum(1 for item in setup_conditions if item)
    confidence = 0.30 + hits * 0.08 + (0.12 if reversal_confirmed else 0.0)
    if prob_up is not None:
        confidence = max(confidence, float(prob_up))
    confidence = min(confidence, 0.95)

    if SETTINGS.mean_reversion_require_reversal_confirmation and not reversal_confirmed:
        return 0, confidence

    if hits >= 4 and confidence >= SETTINGS.mean_reversion_prob_floor:
        return 1, confidence
    return 0, confidence
