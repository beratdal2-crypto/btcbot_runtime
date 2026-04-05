from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
os.environ.setdefault("MPLCONFIGDIR", os.path.join("logs", ".mplconfig"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import joblib
import pandas as pd
from stable_baselines3 import PPO

from coin_scores import load_coin_scores, refresh_coin_scores
from config import SETTINGS
from data import get_research_klines_df
from adaptive_params import symbol_threshold_overrides
from features import build_features
from regime.regime_features import add_regime_features
from regime.regime_detector import detect_regime
from regime.regime_router import regime_weights
from agents.trend_agent import trend_signal
from agents.scalp_agent import scalp_signal
from agents.compression_breakout_agent import compression_breakout_signal
from agents.mean_reversion_agent import mean_reversion_signal
from agents.fusion import final_decision
from agents.exit_agent import should_signal_exit
from position_sizing import compute_position_fraction
from rl_infer import get_rl_action_from_df
from research_profiles import apply_research_profile
from strategy_selector import select_symbol_strategy
from strategy_models import enforce_strategy_signal_quality, is_breakout_strategy, model_probability, select_strategy_model
from model_bootstrap import ensure_base_models


def _safe_imbalance(symbol: str) -> float:
    return 0.5


def _warmup_bars(df_length: int) -> int:
    if df_length <= 0:
        return 0
    return min(60, max(20, df_length // 3))


@dataclass
class SimPosition:
    side: str
    entry_price: float
    qty: float
    entry_index: int
    entry_time: str
    entry_fee: float


def _apply_slippage(price: float, side: str, slippage_rate: float) -> float:
    if side == "BUY":
        return price * (1 + slippage_rate)
    return price * (1 - slippage_rate)


def _deterministic_fraction(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) / 0xFFFFFFFF


def prepare_backtest_frame(raw: pd.DataFrame, imbalance: float) -> pd.DataFrame:
    feat_df = build_features(raw, imbalance)
    regime_df = add_regime_features(raw)[["close_time", "trend_gap", "ret_15", "volatility_20"]]
    merged = feat_df.merge(regime_df, on="close_time", how="inner")
    return merged.reset_index(drop=True)


def build_symbol_backtest_frame(symbol: str) -> pd.DataFrame:
    raw = get_research_klines_df(limit=SETTINGS.training_lookback_limit, symbol=symbol)
    imbalance = _safe_imbalance(symbol)
    return prepare_backtest_frame(raw, imbalance)


def precompute_rl_actions(df: pd.DataFrame, rl_model, warmup_bars: int | None = None) -> list[int]:
    actions = [0] * len(df)
    if rl_model is None:
        return actions
    warmup_bars = _warmup_bars(len(df)) if warmup_bars is None else warmup_bars
    for i in range(warmup_bars, len(df)):
        window = df.iloc[: i + 1].copy()
        actions[i] = get_rl_action_from_df(window, model=rl_model)
    return actions


def simulate_backtest(
    df: pd.DataFrame,
    model,
    strategy_models: dict[str, object] | None = None,
    rl_model=None,
    rl_action_series: list[int] | None = None,
    fee_rate: float | None = None,
    slippage_rate: float | None = None,
    risk_fraction: float | None = None,
    starting_equity: float | None = None,
    coin_score: float | None = None,
    symbol: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    fee_rate = SETTINGS.backtest_fee_rate if fee_rate is None else fee_rate
    slippage_rate = SETTINGS.backtest_slippage_rate if slippage_rate is None else slippage_rate
    risk_fraction = SETTINGS.backtest_risk_fraction if risk_fraction is None else risk_fraction
    starting_equity = SETTINGS.starting_equity if starting_equity is None else starting_equity

    equity = starting_equity
    peak_equity = equity
    max_drawdown = 0.0
    position: SimPosition | None = None
    trades: list[dict] = []

    warmup_bars = _warmup_bars(len(df))
    for i in range(warmup_bars, len(df)):
        window = df.iloc[: i + 1].copy()
        row = window.iloc[-1]

        regime = detect_regime(row)
        weights = regime_weights(regime)
        effective_symbol = symbol or str(row.get("symbol", SETTINGS.symbol))
        threshold_overrides = symbol_threshold_overrides(effective_symbol, coin_score=coin_score)
        strategy = select_symbol_strategy(
            symbol=effective_symbol,
            regime=regime,
            atr_pct=float(row.get("atr_pct", 0.0)),
            volume_ratio=float(row.get("volume_ratio", 1.0)),
            coin_score=coin_score or 50.0,
        )
        threshold_overrides["buy_threshold"] = max(
            0.48,
            min(0.75, threshold_overrides["buy_threshold"] + float(strategy["buy_threshold_offset"])),
        )
        threshold_overrides["entry_score_threshold"] = max(
            0.40,
            min(0.72, threshold_overrides["entry_score_threshold"] + float(strategy["entry_threshold_offset"])),
        )
        threshold_overrides["max_entry_spread_bps"] = max(
            4.0,
            float(threshold_overrides["max_entry_spread_bps"]) * float(strategy["spread_multiplier"]),
        )
        threshold_overrides["min_entry_depth_notional"] = max(
            500.0,
            float(threshold_overrides["min_entry_depth_notional"]) * float(strategy["depth_multiplier"]),
        )
        trend = trend_signal(window)
        active_model = select_strategy_model(
            str(strategy["name"]),
            strategy_models=strategy_models,
            default_model=model,
        )
        scalp, prob_up = scalp_signal(
            active_model,
            window,
            threshold_overrides["buy_threshold"],
            threshold_overrides["sell_threshold"],
        )
        model_prob_up = prob_up
        alternate_key = "trend" if str(strategy["name"]) == "mean_reversion" else "mean_reversion"
        alternate_model = (strategy_models or {}).get(alternate_key)
        alternate_prob = model_probability(alternate_model, window) if alternate_model is not None else 0.5
        scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
        mr_signal, mr_confidence = mean_reversion_signal(window, prob_up=prob_up)
        if strategy["name"] == "mean_reversion" and mr_signal > scalp:
            scalp = mr_signal
            prob_up = max(prob_up, mr_confidence)
            scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
        breakout_signal, breakout_confidence = compression_breakout_signal(window, prob_up=prob_up)
        if is_breakout_strategy(str(strategy["name"])) and breakout_signal > scalp:
            scalp = breakout_signal
            prob_up = max(prob_up, breakout_confidence)
            scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
        rl_action = rl_action_series[i] if rl_action_series is not None else get_rl_action_from_df(window, model=rl_model) if rl_model is not None else 0
        decision = final_decision(
            trend=trend,
            scalp=scalp,
            rl_action=rl_action,
            weights=weights,
            risk_ok=True,
            regime=regime,
            long_only=SETTINGS.long_only,
            prob_up=prob_up,
            volume_ratio=float(row["volume_ratio"]),
            atr_pct=float(row["atr_pct"]),
            entry_score_threshold=threshold_overrides["entry_score_threshold"],
            max_entry_spread_bps=threshold_overrides["max_entry_spread_bps"],
            min_entry_depth_notional=threshold_overrides["min_entry_depth_notional"],
        )

        current_price = float(row["c"])
        current_time = str(row["close_time"])

        if position is None and decision in {"BUY", "SELL"}:
            if decision == "SELL" and SETTINGS.long_only:
                peak_equity = max(peak_equity, equity)
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0)
                continue

            position_fraction = compute_position_fraction(
                base_fraction=risk_fraction,
                atr_pct=float(row.get("atr_pct", 0.0)),
                coin_score=coin_score,
                symbol=effective_symbol,
            )
            position_fraction *= float(strategy["size_multiplier"])
            position_fraction = max(SETTINGS.position_size_min_fraction, min(SETTINGS.position_size_max_fraction, position_fraction))
            notional = equity * position_fraction
            if notional <= 0:
                peak_equity = max(peak_equity, equity)
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0)
                continue

            side = "BUY" if decision == "BUY" else "SELL"
            if _deterministic_fraction(f"reject:{current_time}:{i}") < SETTINGS.backtest_reject_rate:
                peak_equity = max(peak_equity, equity)
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0)
                continue
            entry_price = _apply_slippage(current_price, side, slippage_rate)
            partial_fill = SETTINGS.backtest_partial_fill_floor + (1 - SETTINGS.backtest_partial_fill_floor) * _deterministic_fraction(f"fill:{current_time}:{i}")
            qty = (notional / entry_price) * partial_fill
            entry_fee = notional * fee_rate
            equity -= notional + entry_fee
            position = SimPosition(
                side=side,
                entry_price=entry_price,
                qty=qty,
                entry_index=i,
                entry_time=current_time,
                entry_fee=entry_fee,
            )

        elif position and position.side == "BUY":
            gross_return = (current_price - position.entry_price) / position.entry_price
            force_signal_exit = should_signal_exit(
                position_side="LONG",
                regime=regime,
                trend=trend,
                scalp=scalp,
                rl_action=rl_action,
                prob_up=prob_up,
            )
            if force_signal_exit or gross_return >= SETTINGS.take_profit_pct or gross_return <= -SETTINGS.stop_loss_pct:
                exit_price = _apply_slippage(current_price, "SELL", slippage_rate)
                exit_notional = exit_price * position.qty
                exit_fee = exit_notional * fee_rate
                gross_pnl = (exit_price - position.entry_price) * position.qty
                net_pnl = gross_pnl - position.entry_fee - exit_fee
                trade_return_pct = net_pnl / (position.entry_price * position.qty)
                equity += exit_notional - exit_fee
                trades.append(
                    {
                        "side": position.side,
                        "regime": regime,
                        "prob_up": prob_up,
                        "rl_action": rl_action,
                        "entry_time": position.entry_time,
                        "exit_time": current_time,
                        "entry_price": position.entry_price,
                        "exit_price": exit_price,
                        "qty": position.qty,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "return_pct": trade_return_pct,
                        "bars_held": i - position.entry_index,
                        "entry_fee": position.entry_fee,
                        "exit_fee": exit_fee,
                        "exit_reason": "signal" if force_signal_exit else "tp_sl",
                    }
                )
                position = None

        elif position and position.side == "SELL":
            gross_return = (position.entry_price - current_price) / position.entry_price
            if gross_return >= SETTINGS.take_profit_pct or gross_return <= -SETTINGS.stop_loss_pct:
                exit_price = _apply_slippage(current_price, "BUY", slippage_rate)
                exit_notional = exit_price * position.qty
                exit_fee = exit_notional * fee_rate
                gross_pnl = (position.entry_price - exit_price) * position.qty
                net_pnl = gross_pnl - position.entry_fee - exit_fee
                trade_return_pct = net_pnl / (position.entry_price * position.qty)
                equity += (position.entry_price * position.qty) + net_pnl
                trades.append(
                    {
                        "side": position.side,
                        "regime": regime,
                        "prob_up": prob_up,
                        "rl_action": rl_action,
                        "entry_time": position.entry_time,
                        "exit_time": current_time,
                        "entry_price": position.entry_price,
                        "exit_price": exit_price,
                        "qty": position.qty,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "return_pct": trade_return_pct,
                        "bars_held": i - position.entry_index,
                        "entry_fee": position.entry_fee,
                        "exit_fee": exit_fee,
                    }
                )
                position = None

        peak_equity = max(peak_equity, equity)
        if peak_equity > 0:
            max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)

    if position is not None:
        row = df.iloc[-1]
        current_price = float(row["c"])
        current_time = str(row["close_time"])
        if position.side == "BUY":
            exit_price = _apply_slippage(current_price, "SELL", slippage_rate)
            exit_notional = exit_price * position.qty
            exit_fee = exit_notional * fee_rate
            gross_pnl = (exit_price - position.entry_price) * position.qty
            net_pnl = gross_pnl - position.entry_fee - exit_fee
            trade_return_pct = net_pnl / (position.entry_price * position.qty)
            equity += exit_notional - exit_fee
        else:
            exit_price = _apply_slippage(current_price, "BUY", slippage_rate)
            exit_notional = exit_price * position.qty
            exit_fee = exit_notional * fee_rate
            gross_pnl = (position.entry_price - exit_price) * position.qty
            net_pnl = gross_pnl - position.entry_fee - exit_fee
            trade_return_pct = net_pnl / (position.entry_price * position.qty)
            equity += (position.entry_price * position.qty) + net_pnl

        trades.append(
            {
                "side": position.side,
                "regime": "FORCED_EXIT",
                "prob_up": None,
                "rl_action": None,
                "entry_time": position.entry_time,
                "exit_time": current_time,
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "qty": position.qty,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "return_pct": trade_return_pct,
                "bars_held": (len(df) - 1) - position.entry_index,
                "entry_fee": position.entry_fee,
                "exit_fee": exit_fee,
                "exit_reason": "forced_end",
            }
        )

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, {
            "trade_count": 0,
            "starting_equity": starting_equity,
            "ending_equity": equity,
            "total_return_pct": 0.0,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "total_fees": 0.0,
            "win_rate_pct": 0.0,
            "avg_trade_pct": 0.0,
            "median_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "max_drawdown_pct": max_drawdown * 100,
            "profit_factor": 0.0,
            "avg_bars_held": 0.0,
        }

    returns = trades_df["return_pct"]
    gross_pnl = float(trades_df["gross_pnl"].sum())
    net_pnl = float(trades_df["net_pnl"].sum())
    total_fees = float(trades_df["entry_fee"].sum() + trades_df["exit_fee"].sum())
    ending_equity = float(equity)
    total_return_pct = (ending_equity - starting_equity) / starting_equity
    losses = trades_df.loc[trades_df["net_pnl"] < 0, "net_pnl"]
    profits = trades_df.loc[trades_df["net_pnl"] > 0, "net_pnl"]
    profit_factor = float(profits.sum() / abs(losses.sum())) if not losses.empty else float("inf")

    summary = {
        "trade_count": int(len(trades_df)),
        "starting_equity": float(starting_equity),
        "ending_equity": ending_equity,
        "total_return_pct": float(total_return_pct * 100),
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "total_fees": total_fees,
        "win_rate_pct": float((returns > 0).mean() * 100),
        "avg_trade_pct": float(returns.mean() * 100),
        "median_trade_pct": float(returns.median() * 100),
        "worst_trade_pct": float(returns.min() * 100),
        "max_drawdown_pct": float(max_drawdown * 100),
        "profit_factor": profit_factor,
        "avg_bars_held": float(trades_df["bars_held"].mean()),
    }
    return trades_df, summary


def _save_backtest_outputs(
    trades_df: pd.DataFrame,
    summary: dict,
    trades_path: str | None = None,
    summary_path: str | None = None,
) -> None:
    trades_path = trades_path or SETTINGS.backtest_trades_path
    summary_path = summary_path or SETTINGS.backtest_summary_path
    os.makedirs(os.path.dirname(trades_path), exist_ok=True)
    trades_df.to_csv(trades_path, index=False)
    pd.DataFrame([summary]).to_csv(summary_path, index=False)


def _aggregate_backtest_summaries(summaries: list[dict], symbol_count: int) -> dict:
    if not summaries:
        return {
            "trade_count": 0,
            "starting_equity": 0.0,
            "ending_equity": 0.0,
            "total_return_pct": 0.0,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "total_fees": 0.0,
            "win_rate_pct": 0.0,
            "avg_trade_pct": 0.0,
            "median_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "avg_bars_held": 0.0,
            "symbol_count": symbol_count,
        }

    finite_profit_factors = [
        summary["profit_factor"]
        for summary in summaries
        if summary["profit_factor"] != float("inf")
    ]
    return {
        "trade_count": int(sum(summary["trade_count"] for summary in summaries)),
        "starting_equity": float(sum(summary["starting_equity"] for summary in summaries)),
        "ending_equity": float(sum(summary["ending_equity"] for summary in summaries)),
        "total_return_pct": float(sum(summary["total_return_pct"] for summary in summaries) / len(summaries)),
        "gross_pnl": float(sum(summary["gross_pnl"] for summary in summaries)),
        "net_pnl": float(sum(summary["net_pnl"] for summary in summaries)),
        "total_fees": float(sum(summary["total_fees"] for summary in summaries)),
        "win_rate_pct": float(sum(summary["win_rate_pct"] for summary in summaries) / len(summaries)),
        "avg_trade_pct": float(sum(summary["avg_trade_pct"] for summary in summaries) / len(summaries)),
        "median_trade_pct": float(sum(summary["median_trade_pct"] for summary in summaries) / len(summaries)),
        "worst_trade_pct": float(min(summary["worst_trade_pct"] for summary in summaries)),
        "max_drawdown_pct": float(max(summary["max_drawdown_pct"] for summary in summaries)),
        "profit_factor": float(sum(finite_profit_factors) / len(finite_profit_factors)) if finite_profit_factors else float("inf"),
        "avg_bars_held": float(sum(summary["avg_bars_held"] for summary in summaries) / len(summaries)),
        "symbol_count": symbol_count,
    }


def run_backtest(
    profile_name: str | None = None,
    symbols: tuple[str, ...] | None = None,
    trades_path: str | None = None,
    summary_path: str | None = None,
    refresh_scores: bool = True,
) -> tuple[pd.DataFrame, dict]:
    with apply_research_profile(profile_name):
        ensure_base_models()
        model = joblib.load(SETTINGS.model_path)
        strategy_models: dict[str, object] = {}
        if os.path.exists(SETTINGS.trend_model_path):
            strategy_models["trend"] = joblib.load(SETTINGS.trend_model_path)
        if os.path.exists(SETTINGS.mean_reversion_model_path):
            strategy_models["mean_reversion"] = joblib.load(SETTINGS.mean_reversion_model_path)
        rl_model = PPO.load(SETTINGS.rl_model_path) if os.path.exists(f"{SETTINGS.rl_model_path}.zip") else None
        existing_scores = load_coin_scores()
        score_lookup = {}
        if existing_scores is not None and not existing_scores.empty and "symbol" in existing_scores.columns:
            score_lookup = {
                str(row["symbol"]).upper(): float(row.get("score", 50.0))
                for _, row in existing_scores.iterrows()
            }
        active_symbols = tuple(symbols or SETTINGS.trading_symbols())
        all_trades: list[pd.DataFrame] = []
        summaries: list[dict] = []
        for symbol in active_symbols:
            try:
                backtest_df = build_symbol_backtest_frame(symbol)
            except Exception as exc:
                print(f"[BACKTEST] {symbol} skipped: {exc}")
                continue
            rl_action_series = precompute_rl_actions(backtest_df, rl_model) if rl_model is not None else None
            trades_df, summary = simulate_backtest(
                backtest_df,
                model=model,
                strategy_models=strategy_models,
                rl_model=rl_model,
                rl_action_series=rl_action_series,
                coin_score=score_lookup.get(symbol, 50.0),
                symbol=symbol,
            )
            summary["symbol"] = symbol
            if profile_name:
                summary["profile"] = profile_name
            summaries.append(summary)
            if not trades_df.empty:
                trades_df = trades_df.copy()
                trades_df.insert(0, "symbol", symbol)
                if profile_name:
                    trades_df.insert(1, "profile", profile_name)
                all_trades.append(trades_df)

        trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
        summary = _aggregate_backtest_summaries(summaries, symbol_count=len(summaries))
        summary["symbols"] = ",".join(item["symbol"] for item in summaries) if summaries else ""
        if profile_name:
            summary["profile"] = profile_name
        _save_backtest_outputs(trades_df, summary, trades_path=trades_path, summary_path=summary_path)
        if refresh_scores:
            refresh_coin_scores(backtest_trades=trades_df)
    if trades_df.empty:
        print("Hic trade olusmadi.")
        print(f"Ozet CSV: {summary_path or SETTINGS.backtest_summary_path}")
        print(f"Trade CSV: {trades_path or SETTINGS.backtest_trades_path}")
        return trades_df, summary

    print("Trade sayısı:", summary["trade_count"])
    print("Win rate:", round(summary["win_rate_pct"], 2), "%")
    print("Baslangic equity:", round(summary["starting_equity"], 2))
    print("Bitis equity:", round(summary["ending_equity"], 2))
    print("Toplam getiri:", round(summary["total_return_pct"], 2), "%")
    print("Brut PnL:", round(summary["gross_pnl"], 4))
    print("Net PnL:", round(summary["net_pnl"], 4))
    print("Toplam fee:", round(summary["total_fees"], 4))
    print("Ortalama trade:", round(summary["avg_trade_pct"], 3), "%")
    print("Medyan trade:", round(summary["median_trade_pct"], 3), "%")
    print("En kötü trade:", round(summary["worst_trade_pct"], 3), "%")
    print("Max drawdown:", round(summary["max_drawdown_pct"], 2), "%")
    print("Profit factor:", round(summary["profit_factor"], 3) if summary["profit_factor"] != float("inf") else "inf")
    print("Ortalama bar elde tutma:", round(summary["avg_bars_held"], 2))
    print("Sembol sayisi:", summary["symbol_count"])
    print(f"Trade CSV: {trades_path or SETTINGS.backtest_trades_path}")
    print(f"Ozet CSV: {summary_path or SETTINGS.backtest_summary_path}")
    print("")
    print("Son 5 trade:")
    print(
        trades_df[
            ["side", "entry_time", "exit_time", "entry_price", "exit_price", "net_pnl", "return_pct", "bars_held", "rl_action"]
        ]
        .tail(5)
        .to_string(index=False)
    )
    return trades_df, summary


if __name__ == "__main__":
    run_backtest()
