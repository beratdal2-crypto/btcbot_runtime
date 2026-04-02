from config import SETTINGS


def _countertrend_long_allowed(
    regime: str,
    prob_up: float | None,
    volume_ratio: float | None,
    atr_pct: float | None,
) -> bool:
    if not SETTINGS.allow_countertrend_reversion:
        return False
    if regime not in {"RANGE", "DOWNTREND"}:
        return False
    if prob_up is None or prob_up < SETTINGS.countertrend_reversion_prob_threshold:
        return False
    if volume_ratio is not None and volume_ratio < SETTINGS.countertrend_reversion_min_volume_ratio:
        return False
    if atr_pct is not None and atr_pct > SETTINGS.countertrend_reversion_max_atr_pct:
        return False
    return True


def _long_entry_allowed(
    trend: int,
    scalp: int,
    rl_action: int,
    regime: str,
    prob_up: float | None,
    volume_ratio: float | None,
    atr_pct: float | None,
    spread_bps: float | None,
    depth_notional: float | None,
    max_entry_spread_bps: float | None,
    min_entry_depth_notional: float | None,
) -> bool:
    countertrend_allowed = _countertrend_long_allowed(
        regime=regime,
        prob_up=prob_up,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
    )

    if SETTINGS.block_dowtrend_longs and regime == "DOWNTREND" and not countertrend_allowed:
        return False
    if SETTINGS.require_trend_alignment and trend < 0 and not countertrend_allowed:
        return False
    if scalp <= 0:
        return False
    if SETTINGS.require_nonnegative_rl and rl_action < 0:
        return False
    if prob_up is not None and prob_up < SETTINGS.buy_threshold + SETTINGS.entry_prob_buffer:
        return False
    if volume_ratio is not None and volume_ratio < SETTINGS.entry_min_volume_ratio:
        return False
    if atr_pct is not None and atr_pct > SETTINGS.entry_max_atr_pct:
        return False
    spread_limit = SETTINGS.max_entry_spread_bps if max_entry_spread_bps is None else max_entry_spread_bps
    depth_limit = SETTINGS.min_entry_depth_notional if min_entry_depth_notional is None else min_entry_depth_notional
    if spread_bps is not None and spread_bps > spread_limit:
        return False
    if depth_notional is not None and depth_notional < depth_limit:
        return False
    return True


def final_decision(
    trend: int,
    scalp: int,
    rl_action: int,
    weights: dict,
    risk_ok: bool,
    regime: str,
    long_only: bool = True,
    prob_up: float | None = None,
    volume_ratio: float | None = None,
    atr_pct: float | None = None,
    spread_bps: float | None = None,
    depth_notional: float | None = None,
    entry_score_threshold: float | None = None,
    max_entry_spread_bps: float | None = None,
    min_entry_depth_notional: float | None = None,
    no_trade_zone_active: bool = False,
) -> str:
    if not risk_ok:
        return "HOLD"
    if regime == "HIGH_VOLATILITY":
        return "HOLD"
    if no_trade_zone_active and SETTINGS.no_trade_zone_enabled:
        return "HOLD"

    score = (
        trend * weights.get("trend", 0.0)
        + scalp * weights.get("scalp", 0.0)
        + rl_action * weights.get("rl", 0.0)
    )

    score_threshold = SETTINGS.entry_score_threshold if entry_score_threshold is None else entry_score_threshold

    if score > score_threshold:
        if long_only and not _long_entry_allowed(
            trend=trend,
            scalp=scalp,
            rl_action=rl_action,
            regime=regime,
            prob_up=prob_up,
            volume_ratio=volume_ratio,
            atr_pct=atr_pct,
            spread_bps=spread_bps,
            depth_notional=depth_notional,
            max_entry_spread_bps=max_entry_spread_bps,
            min_entry_depth_notional=min_entry_depth_notional,
        ):
            return "HOLD"
        return "BUY"
    if (
        long_only
        and scalp > 0
        and _countertrend_long_allowed(
            regime=regime,
            prob_up=prob_up,
            volume_ratio=volume_ratio,
            atr_pct=atr_pct,
        )
        and _long_entry_allowed(
            trend=trend,
            scalp=scalp,
            rl_action=rl_action,
            regime=regime,
            prob_up=prob_up,
            volume_ratio=volume_ratio,
            atr_pct=atr_pct,
            spread_bps=spread_bps,
            depth_notional=depth_notional,
            max_entry_spread_bps=max_entry_spread_bps,
            min_entry_depth_notional=min_entry_depth_notional,
        )
    ):
        return "BUY"
    if score < -score_threshold:
        return "HOLD" if long_only else "SELL"
    return "HOLD"
