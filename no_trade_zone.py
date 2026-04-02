from __future__ import annotations

from coin_risk import risk_profile_for_symbol


def detect_no_trade_zone(
    symbol: str,
    regime: str,
    prob_up: float | None,
    volume_ratio: float | None,
    atr_pct: float | None,
    spread_bps: float | None,
    depth_notional: float | None,
    last_bar_return_pct: float | None,
    max_entry_spread_bps: float,
    min_entry_depth_notional: float,
    min_probability_edge: float,
) -> tuple[bool, str]:
    profile = risk_profile_for_symbol(symbol)
    min_probability_edge = float(profile.get("min_probability_edge", min_probability_edge) or min_probability_edge)
    if regime == "HIGH_VOLATILITY":
        return True, "rejim_yuksek_volatilite"
    if prob_up is not None and abs(prob_up - 0.5) < min_probability_edge:
        return True, "olasilik_kararsiz"
    if spread_bps is not None and spread_bps > max_entry_spread_bps:
        return True, "spread_genis"
    if depth_notional is not None and depth_notional < min_entry_depth_notional:
        return True, "derinlik_zayif"
    if atr_pct is not None and atr_pct > 0.012:
        return True, "atr_yuksek"
    if volume_ratio is not None and volume_ratio > 2.8:
        return True, "hacim_soku"
    if last_bar_return_pct is not None and abs(last_bar_return_pct) > float(profile["max_single_bar_move_pct"]):
        return True, "bar_spike"
    return False, ""
