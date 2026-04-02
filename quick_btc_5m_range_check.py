from __future__ import annotations

import json
import os

import joblib
import pandas as pd

from backtest import build_symbol_backtest_frame, simulate_backtest
from config import SETTINGS
from research_profiles import apply_research_profile


def main() -> None:
    os.makedirs("logs", exist_ok=True)
    with apply_research_profile("btc_5m_range"):
        df = build_symbol_backtest_frame("BTCUSDT").tail(360).reset_index(drop=True)
        model = joblib.load(SETTINGS.model_path)
        strategy_models = {
            "trend": joblib.load(SETTINGS.trend_model_path),
            "mean_reversion": joblib.load(SETTINGS.mean_reversion_model_path),
        }
        trades_df, bt_summary = simulate_backtest(
            df,
            model=model,
            strategy_models=strategy_models,
            rl_model=None,
            rl_action_series=None,
            symbol="BTCUSDT",
        )
        wf_df = df.tail(120).reset_index(drop=True)
        _, wf_summary = simulate_backtest(
            wf_df,
            model=model,
            strategy_models=strategy_models,
            rl_model=None,
            rl_action_series=None,
            symbol="BTCUSDT",
        )

    trades_df.to_csv("logs/quick_btc_5m_range_backtest.csv", index=False)
    pd.DataFrame([wf_summary]).to_csv("logs/quick_btc_5m_range_walkforward.csv", index=False)
    payload = {
        "backtest": bt_summary,
        "walkforward_like": wf_summary,
        "edge_confirmed": (
            bt_summary.get("total_return_pct", 0.0) > 0
            and wf_summary.get("total_return_pct", 0.0) > 0
        ),
    }
    with open("logs/quick_btc_5m_range_check.json", "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(payload)


if __name__ == "__main__":
    main()
