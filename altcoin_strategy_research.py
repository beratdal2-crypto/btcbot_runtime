from __future__ import annotations

import json
import os
from contextlib import contextmanager

import pandas as pd

from backtest import run_backtest
from coin_scores import merge_profile_report_into_coin_scores
from config import SETTINGS
from walkforward import run_walkforward


ALTCOIN_PROFILE_REPORT_PATH = "logs/altcoin_strategy_profiles.csv"
BEST_ALTCOIN_PROFILE_PATH = "logs/best_altcoin_strategy.json"
ALTCOIN_PROFILES: tuple[str, ...] = (
    "balanced",
    "trend",
    "mean_reversion",
    "alt_5m_breakout",
    "alt_5m_pullback",
    "eth_5m_pullback",
    "eth_5m_continuation",
)

ONT_SPECIFIC_PROFILES: tuple[str, ...] = (
    "ont_5m_breakout",
    "ont_15m_breakout",
    "ont_15m_pullback",
)


@contextmanager
def _faster_research_mode():
    original_timesteps = SETTINGS.walkforward_rl_timesteps
    original_interval = SETTINGS.walkforward_rl_retrain_interval
    try:
        SETTINGS.walkforward_rl_timesteps = min(original_timesteps, 1000)
        SETTINGS.walkforward_rl_retrain_interval = max(SETTINGS.walkforward_rl_retrain_interval, 2)
        yield
    finally:
        SETTINGS.walkforward_rl_timesteps = original_timesteps
        SETTINGS.walkforward_rl_retrain_interval = original_interval


def _safe_metric(df: pd.DataFrame, column: str, reducer: str = "mean") -> float:
    if df.empty or column not in df.columns:
        return 0.0
    series = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    if reducer == "sum":
        return float(series.sum())
    return float(series.mean())


def run_altcoin_strategy_research(symbols: tuple[str, ...] | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    active_symbols = tuple(symbols or SETTINGS.alt_research_symbols())

    with _faster_research_mode():
        for symbol in active_symbols:
            profiles = list(ALTCOIN_PROFILES)
            if symbol.upper() == "ONTUSDT":
                profiles.extend(ONT_SPECIFIC_PROFILES)
            for profile in profiles:
                prefix = f"{symbol.lower()}_{profile}"
                trades_path = os.path.join("logs", f"{prefix}_backtest_trades.csv")
                summary_path = os.path.join("logs", f"{prefix}_backtest_summary.csv")
                wf_path = os.path.join("logs", f"{prefix}_walkforward.csv")

                _, bt_summary = run_backtest(
                    profile_name=profile,
                    symbols=(symbol,),
                    trades_path=trades_path,
                    summary_path=summary_path,
                    refresh_scores=False,
                )
                wf_df = run_walkforward(
                    profile_name=profile,
                    symbols=(symbol,),
                    output_path=wf_path,
                    refresh_scores=False,
                )
                rows.append(
                    {
                        "symbol": symbol,
                        "profile": profile,
                        "bt_trade_count": int(bt_summary.get("trade_count", 0)),
                        "bt_total_return_pct": float(bt_summary.get("total_return_pct", 0.0)),
                        "bt_max_drawdown_pct": float(bt_summary.get("max_drawdown_pct", 0.0)),
                        "bt_profit_factor": float(bt_summary.get("profit_factor", 0.0))
                        if bt_summary.get("profit_factor", 0.0) != float("inf")
                        else 5.0,
                        "wf_fold_count": int(len(wf_df)) if not wf_df.empty else 0,
                        "wf_trade_count": int(_safe_metric(wf_df, "trade_count", reducer="sum")),
                        "wf_avg_return_pct": _safe_metric(wf_df, "total_return_pct"),
                        "wf_avg_max_drawdown_pct": _safe_metric(wf_df, "max_drawdown_pct"),
                        "wf_avg_win_rate_pct": _safe_metric(wf_df, "win_rate_pct"),
                    }
                )

    results_df = pd.DataFrame(rows)
    if results_df.empty:
        os.makedirs("logs", exist_ok=True)
        results_df.to_csv(ALTCOIN_PROFILE_REPORT_PATH, index=False)
        return results_df

    results_df["research_score"] = (
        results_df["bt_total_return_pct"] * 0.30
        + results_df["wf_avg_return_pct"] * 1.40
        - results_df["bt_max_drawdown_pct"] * 0.25
        - results_df["wf_avg_max_drawdown_pct"] * 0.45
        + results_df["bt_profit_factor"] * 0.18
        + results_df["wf_trade_count"].clip(upper=20) * 0.04
    )

    ordered = results_df.sort_values(
        ["research_score", "wf_avg_return_pct", "bt_total_return_pct"],
        ascending=False,
    ).reset_index(drop=True)
    os.makedirs("logs", exist_ok=True)
    ordered.to_csv(ALTCOIN_PROFILE_REPORT_PATH, index=False)
    with open(BEST_ALTCOIN_PROFILE_PATH, "w") as f:
        json.dump(ordered.iloc[0].to_dict(), f, indent=2, sort_keys=True)
    merge_profile_report_into_coin_scores(ALTCOIN_PROFILE_REPORT_PATH)
    print(f"Altcoin strategy research CSV: {ALTCOIN_PROFILE_REPORT_PATH}")
    print(ordered.to_string(index=False))
    return ordered


if __name__ == "__main__":
    run_altcoin_strategy_research()
