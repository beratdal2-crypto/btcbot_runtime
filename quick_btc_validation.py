from __future__ import annotations

import json
import os
from contextlib import contextmanager

from backtest import run_backtest
from btc_strategy_research import run_btc_strategy_research
from config import SETTINGS
from walkforward import run_walkforward


@contextmanager
def _quick_mode():
    original = {
        "training_lookback_limit": SETTINGS.training_lookback_limit,
        "walkforward_rl_timesteps": SETTINGS.walkforward_rl_timesteps,
        "walkforward_rl_retrain_interval": SETTINGS.walkforward_rl_retrain_interval,
        "walkforward_train_bars": SETTINGS.walkforward_train_bars,
        "walkforward_test_bars": SETTINGS.walkforward_test_bars,
        "walkforward_step_bars": SETTINGS.walkforward_step_bars,
    }
    try:
        SETTINGS.training_lookback_limit = min(SETTINGS.training_lookback_limit, 3000)
        SETTINGS.walkforward_rl_timesteps = min(SETTINGS.walkforward_rl_timesteps, 500)
        SETTINGS.walkforward_rl_retrain_interval = max(SETTINGS.walkforward_rl_retrain_interval, 3)
        SETTINGS.walkforward_train_bars = min(SETTINGS.walkforward_train_bars, 180)
        SETTINGS.walkforward_test_bars = min(SETTINGS.walkforward_test_bars, 60)
        SETTINGS.walkforward_step_bars = min(SETTINGS.walkforward_step_bars, 60)
        yield
    finally:
        for key, value in original.items():
            setattr(SETTINGS, key, value)


def run_quick_btc_validation() -> dict:
    with _quick_mode():
        _, bt_summary = run_backtest(
            profile_name=None,
            symbols=("BTCUSDT",),
            trades_path="logs/quick_btc_backtest_trades.csv",
            summary_path="logs/quick_btc_backtest_summary.csv",
            refresh_scores=False,
        )
        wf_df = run_walkforward(
            profile_name=None,
            symbols=("BTCUSDT",),
            output_path="logs/quick_btc_walkforward.csv",
            refresh_scores=False,
        )
        profiles_df = run_btc_strategy_research()

    summary = {
        "bt_trade_count": int(bt_summary.get("trade_count", 0)),
        "bt_total_return_pct": float(bt_summary.get("total_return_pct", 0.0)),
        "bt_max_drawdown_pct": float(bt_summary.get("max_drawdown_pct", 0.0)),
        "wf_fold_count": int(len(wf_df)),
        "wf_trade_count": int(wf_df["trade_count"].sum()) if not wf_df.empty and "trade_count" in wf_df.columns else 0,
        "wf_avg_return_pct": float(wf_df["total_return_pct"].mean()) if not wf_df.empty and "total_return_pct" in wf_df.columns else 0.0,
        "best_profile": profiles_df.iloc[0].to_dict() if not profiles_df.empty else {},
    }
    output_path = "logs/quick_btc_validation.json"
    os.makedirs("logs", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"Quick BTC validation JSON: {output_path}")
    print(summary)
    return summary


if __name__ == "__main__":
    run_quick_btc_validation()
