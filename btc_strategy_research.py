from __future__ import annotations

import os
from contextlib import contextmanager
import json

import pandas as pd

from backtest import run_backtest
from config import SETTINGS
from profile_guard import BEST_PROFILE_PATH
from research_profiles import profile_names
from walkforward import run_walkforward


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


def run_btc_strategy_research() -> pd.DataFrame:
    rows: list[dict] = []
    with _faster_research_mode():
        for profile in profile_names():
            suffix = f"btc_{profile}"
            trades_path = os.path.join("logs", f"{suffix}_backtest_trades.csv")
            summary_path = os.path.join("logs", f"{suffix}_backtest_summary.csv")
            wf_path = os.path.join("logs", f"{suffix}_walkforward.csv")

            _, bt_summary = run_backtest(
                profile_name=profile,
                symbols=("BTCUSDT",),
                trades_path=trades_path,
                summary_path=summary_path,
                refresh_scores=False,
            )
            wf_df = run_walkforward(
                profile_name=profile,
                symbols=("BTCUSDT",),
                output_path=wf_path,
                refresh_scores=False,
            )
            rows.append(
                {
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
    results_df["research_score"] = (
        results_df["bt_total_return_pct"] * 0.25
        + results_df["wf_avg_return_pct"] * 1.35
        - results_df["bt_max_drawdown_pct"] * 0.25
        - results_df["wf_avg_max_drawdown_pct"] * 0.45
        + results_df["bt_profit_factor"] * 0.15
        + results_df["wf_trade_count"].clip(upper=20) * 0.05
    )
    output_path = os.path.join("logs", "btc_strategy_profiles.csv")
    ordered = results_df.sort_values("research_score", ascending=False).reset_index(drop=True)
    ordered.to_csv(output_path, index=False)
    if not ordered.empty:
        os.makedirs(os.path.dirname(BEST_PROFILE_PATH), exist_ok=True)
        with open(BEST_PROFILE_PATH, "w") as f:
            json.dump(ordered.iloc[0].to_dict(), f, indent=2, sort_keys=True)
    print(f"Strategy research CSV: {output_path}")
    print(ordered.to_string(index=False))
    return ordered


if __name__ == "__main__":
    run_btc_strategy_research()
