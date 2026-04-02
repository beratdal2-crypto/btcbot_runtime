from __future__ import annotations

import json
import os
from contextlib import contextmanager

import joblib
import pandas as pd

from backtest import build_symbol_backtest_frame, simulate_backtest
from config import SETTINGS


@contextmanager
def _ultra_quick_mode():
    original = {"training_lookback_limit": SETTINGS.training_lookback_limit}
    try:
        SETTINGS.training_lookback_limit = min(SETTINGS.training_lookback_limit, 600)
        yield
    finally:
        for key, value in original.items():
            setattr(SETTINGS, key, value)


def run_ultra_quick_btc_check() -> dict:
    with _ultra_quick_mode():
        df = build_symbol_backtest_frame("BTCUSDT").tail(480).reset_index(drop=True)
        model = joblib.load(SETTINGS.model_path)
        strategy_models: dict[str, object] = {}
        if os.path.exists(SETTINGS.trend_model_path):
            strategy_models["trend"] = joblib.load(SETTINGS.trend_model_path)
        if os.path.exists(SETTINGS.mean_reversion_model_path):
            strategy_models["mean_reversion"] = joblib.load(SETTINGS.mean_reversion_model_path)
        trades_df, bt_summary = simulate_backtest(
            df,
            model=model,
            strategy_models=strategy_models,
            rl_model=None,
            rl_action_series=None,
            symbol="BTCUSDT",
        )

        test_df = df.tail(96).copy()
        _, wf_summary = simulate_backtest(
            test_df,
            model=model,
            strategy_models=strategy_models,
            rl_model=None,
            rl_action_series=None,
            symbol="BTCUSDT",
        )

    backtest_path = "logs/ultra_quick_btc_backtest.csv"
    walkforward_path = "logs/ultra_quick_btc_walkforward.csv"
    output_path = "logs/ultra_quick_btc_check.json"
    os.makedirs("logs", exist_ok=True)
    trades_df.to_csv(backtest_path, index=False)
    pd.DataFrame([wf_summary]).to_csv(walkforward_path, index=False)
    payload = {
        "backtest": bt_summary,
        "walkforward_like": wf_summary,
        "edge_confirmed": (
            bt_summary.get("total_return_pct", 0.0) > 0
            and wf_summary.get("total_return_pct", 0.0) > 0
        ),
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"Ultra quick BTC check JSON: {output_path}")
    print(payload)
    return payload


if __name__ == "__main__":
    run_ultra_quick_btc_check()
