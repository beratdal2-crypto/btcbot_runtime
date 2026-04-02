from __future__ import annotations
import pandas as pd
import numpy as np
import ta
from config import SETTINGS
from coin_risk import risk_profile_for_symbol

FEATURE_COLUMNS = [
    "return",
    "ema20",
    "ema50",
    "rsi",
    "vol",
    "micro_return",
    "momentum",
    "speed",
    "atr_pct",
    "volume_ratio",
    "imbalance",
    "ema_gap_pct",
    "price_vs_ema20",
    "price_vs_ema50",
    "rsi_delta",
    "return_5",
    "return_15",
    "vol_ratio",
    "range_pos_20",
    "breakout_up_20",
    "breakout_down_20",
    "bb_width",
    "bb_pos",
    "volume_zscore",
    "body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "spread_proxy_bps",
    "close_location",
    "range_efficiency",
    "signed_volume_proxy",
    "liquidity_stress",
    "micro_spread_bps",
    "micro_depth_log",
    "micro_bid_ask_skew",
]


def _compute_target_r_multiple(out: pd.DataFrame) -> np.ndarray:
    closes = pd.to_numeric(out["c"], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out["h"], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out["l"], errors="coerce").to_numpy(dtype=float)
    horizon = max(1, SETTINGS.target_horizon_bars)
    tp_pct = max(1e-6, SETTINGS.target_take_profit_pct)
    sl_pct = max(1e-6, SETTINGS.target_stop_loss_pct)
    positive_r = tp_pct / sl_pct

    values = np.full(len(out), np.nan, dtype=float)
    for idx in range(len(out)):
        end_idx = min(len(out), idx + horizon + 1)
        if idx + 1 >= end_idx:
            continue
        entry = closes[idx]
        if not np.isfinite(entry) or entry <= 0:
            continue

        tp_price = entry * (1 + tp_pct)
        sl_price = entry * (1 - sl_pct)
        future_highs = highs[idx + 1:end_idx]
        future_lows = lows[idx + 1:end_idx]
        future_closes = closes[idx + 1:end_idx]
        result = np.nan

        for future_high, future_low in zip(future_highs, future_lows):
            hit_tp = np.isfinite(future_high) and future_high >= tp_price
            hit_sl = np.isfinite(future_low) and future_low <= sl_price
            if hit_tp and hit_sl:
                result = -1.0
                break
            if hit_sl:
                result = -1.0
                break
            if hit_tp:
                result = positive_r
                break

        if np.isnan(result):
            final_close = future_closes[-1]
            terminal_return = (final_close / entry) - 1.0 if np.isfinite(final_close) else 0.0
            result = float(np.clip(terminal_return / sl_pct, -1.0, positive_r))
        values[idx] = result
    return values


def build_features(
    df: pd.DataFrame,
    imbalance: float,
    microstructure: dict | None = None,
    symbol: str | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if "quote_asset_volume" not in out.columns:
        out["quote_asset_volume"] = pd.to_numeric(out["c"], errors="coerce") * pd.to_numeric(out["v"], errors="coerce")

    out["return"] = out["c"].pct_change()
    out["ema20"] = out["c"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["c"].ewm(span=50, adjust=False).mean()
    out["rsi"] = ta.momentum.RSIIndicator(close=out["c"], window=14).rsi()
    out["vol"] = out["return"].rolling(20).std()

    out["micro_return"] = out["c"].pct_change(3)
    out["momentum"] = out["c"] - out["c"].shift(3)
    out["speed"] = out["momentum"].rolling(5).mean()

    atr = ta.volatility.AverageTrueRange(
        high=out["h"], low=out["l"], close=out["c"], window=14
    ).average_true_range()
    out["atr_pct"] = atr / out["c"]

    out["vol_ma20"] = out["v"].rolling(20).mean()
    out["volume_ratio"] = np.where(out["vol_ma20"] > 0, out["v"] / out["vol_ma20"], 1.0)
    out["volume_std20"] = out["v"].rolling(20).std()
    out["volume_zscore"] = np.where(
        out["volume_std20"] > 0,
        (out["v"] - out["vol_ma20"]) / out["volume_std20"],
        0.0,
    )

    out["ema_gap_pct"] = np.where(out["c"] > 0, (out["ema20"] - out["ema50"]) / out["c"], 0.0)
    out["price_vs_ema20"] = np.where(out["c"] > 0, (out["c"] - out["ema20"]) / out["c"], 0.0)
    out["price_vs_ema50"] = np.where(out["c"] > 0, (out["c"] - out["ema50"]) / out["c"], 0.0)
    out["rsi_delta"] = out["rsi"].diff(3)
    out["return_5"] = out["c"].pct_change(5)
    out["return_15"] = out["c"].pct_change(15)
    out["vol_regime"] = out["vol"].rolling(60).mean()
    out["vol_ratio"] = np.where(out["vol_regime"] > 0, out["vol"] / out["vol_regime"], 1.0)

    rolling_high_20 = out["h"].rolling(20).max().shift(1)
    rolling_low_20 = out["l"].rolling(20).min().shift(1)
    range_width = rolling_high_20 - rolling_low_20
    out["range_pos_20"] = np.where(range_width > 0, (out["c"] - rolling_low_20) / range_width, 0.5)
    out["breakout_up_20"] = np.where(rolling_high_20 > 0, out["c"] / rolling_high_20 - 1.0, 0.0)
    out["breakout_down_20"] = np.where(rolling_low_20 > 0, out["c"] / rolling_low_20 - 1.0, 0.0)

    bb = ta.volatility.BollingerBands(close=out["c"], window=20, window_dev=2)
    bb_high = bb.bollinger_hband()
    bb_low = bb.bollinger_lband()
    bb_width = bb_high - bb_low
    out["bb_width"] = np.where(out["c"] > 0, bb_width / out["c"], 0.0)
    out["bb_pos"] = np.where(bb_width > 0, (out["c"] - bb_low) / bb_width, 0.5)

    candle_range = (out["h"] - out["l"]).replace(0, np.nan)
    out["body_pct"] = (out["c"] - out["o"]) / candle_range
    out["upper_wick_pct"] = (out["h"] - np.maximum(out["o"], out["c"])) / candle_range
    out["lower_wick_pct"] = (np.minimum(out["o"], out["c"]) - out["l"]) / candle_range

    out["spread_proxy_bps"] = np.where(out["c"] > 0, ((out["h"] - out["l"]) / out["c"]) * 10000, 0.0)
    out["close_location"] = np.where(candle_range > 0, (out["c"] - out["l"]) / candle_range, 0.5)
    out["range_efficiency"] = np.where(candle_range > 0, np.abs(out["c"] - out["o"]) / candle_range, 0.0)
    out["signed_volume_proxy"] = np.sign(out["c"] - out["o"]) * out["volume_ratio"]
    out["liquidity_stress"] = np.where(
        (out["v"] > 0) & np.isfinite(out["spread_proxy_bps"]),
        out["spread_proxy_bps"] / np.log1p(out["v"]),
        0.0,
    )

    out["imbalance"] = imbalance
    microstructure = microstructure or {}
    micro_spread_bps = float(microstructure.get("spread_bps", np.nan))
    micro_depth = float(microstructure.get("total_depth_notional", np.nan))
    micro_bid_ask_skew = float(microstructure.get("imbalance", imbalance))
    out["micro_spread_bps"] = micro_spread_bps if np.isfinite(micro_spread_bps) else out["spread_proxy_bps"]
    out["micro_depth_log"] = np.log1p(micro_depth) if np.isfinite(micro_depth) and micro_depth > 0 else np.log1p(out["quote_asset_volume"].rolling(20).mean().fillna(0.0))
    out["micro_bid_ask_skew"] = micro_bid_ask_skew if np.isfinite(micro_bid_ask_skew) else imbalance

    if symbol:
        profile = risk_profile_for_symbol(symbol)
        if symbol.upper() == "ONTUSDT":
            # ONT is structurally thinner than majors; damp raw liquidity penalties
            # so breakout continuation examples do not get over-penalized.
            depth_boost = float(profile.get("feature_depth_boost", 1.12))
            signed_volume_boost = float(profile.get("feature_signed_volume_boost", 1.18))
            liquidity_stress_scale = float(profile.get("feature_liquidity_stress_scale", 0.84))
            out["signed_volume_proxy"] = out["signed_volume_proxy"] * signed_volume_boost
            out["liquidity_stress"] = out["liquidity_stress"] * liquidity_stress_scale
            out["micro_depth_log"] = out["micro_depth_log"] + np.log1p(max(depth_boost - 1.0, 0.0))

    out["target_r_multiple"] = _compute_target_r_multiple(out)
    out["target"] = np.where(
        pd.notna(out["target_r_multiple"]),
        (out["target_r_multiple"] > SETTINGS.target_min_r_multiple).astype(int),
        np.nan,
    )

    out = out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    return out
