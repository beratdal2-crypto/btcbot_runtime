from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalReadiness:
    regime_ready: bool
    probability_ready: bool
    liquidity_ready: bool

    @property
    def strong_ready(self) -> bool:
        return self.regime_ready and self.probability_ready and self.liquidity_ready

    @property
    def missing_parts(self) -> str:
        missing: list[str] = []
        if not self.regime_ready:
            missing.append("rejim")
        if not self.probability_ready:
            missing.append("olasilik")
        if not self.liquidity_ready:
            missing.append("likidite")
        return ",".join(missing)


def evaluate_signal_readiness(
    *,
    symbol: str,
    strategy_name: str,
    regime: str,
    trend: int,
    breakout_signal: int,
    prob_up: float,
    buy_threshold: float,
    volume_ratio: float,
    spread_bps: float,
    depth_notional: float,
    max_entry_spread_bps: float,
    min_entry_depth_notional: float,
) -> SignalReadiness:
    is_ont_breakout = symbol.upper() == "ONTUSDT" and "breakout" in strategy_name
    regime_ready = regime in {"RANGE", "UPTREND"} and (trend >= 0 or (is_ont_breakout and breakout_signal > 0))
    probability_floor = max(0.50, buy_threshold - (0.04 if is_ont_breakout else 0.02))
    probability_ready = prob_up >= probability_floor
    liquidity_ready = (
        volume_ratio >= (0.10 if is_ont_breakout else 0.80)
        and spread_bps <= (max_entry_spread_bps * (1.10 if is_ont_breakout else 1.0))
        and depth_notional >= (min_entry_depth_notional * (0.65 if is_ont_breakout else 1.0))
    )
    return SignalReadiness(
        regime_ready=regime_ready,
        probability_ready=probability_ready,
        liquidity_ready=liquidity_ready,
    )
