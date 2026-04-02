from __future__ import annotations

import itertools
import json
import os

import joblib
import pandas as pd

from backtest import build_symbol_backtest_frame, simulate_backtest
from config import SETTINGS
from research_profiles import apply_research_profile


SWEEP_GRID = {
    "buy_threshold": [0.58, 0.62],
    "entry_score_threshold": [0.52, 0.56],
    "entry_min_volume_ratio": [0.90, 0.95],
    "mean_reversion_prob_floor": [0.54, 0.58],
    "mean_reversion_min_prob_up": [0.58, 0.62],
}


def _score(summary: dict) -> float:
    return (
        summary["total_return_pct"]
        - 0.7 * summary["max_drawdown_pct"]
        + 0.3 * min(summary.get("profit_factor", 0.0), 3.0)
        + 0.04 * min(summary.get("trade_count", 0), 20)
    )


def _current(keys: list[str]) -> dict[str, object]:
    return {key: getattr(SETTINGS, key) for key in keys}


def _apply(values: dict[str, object]) -> None:
    for key, value in values.items():
        setattr(SETTINGS, key, value)


def main() -> None:
    os.makedirs("logs", exist_ok=True)
    with apply_research_profile("mean_reversion"):
        model = joblib.load(SETTINGS.model_path)
        strategy_models = {
            "trend": joblib.load(SETTINGS.trend_model_path),
            "mean_reversion": joblib.load(SETTINGS.mean_reversion_model_path),
        }
        df = build_symbol_backtest_frame("BTCUSDT").tail(480).reset_index(drop=True)
        original = _current(list(SWEEP_GRID.keys()))
        rows: list[dict] = []
        try:
            for values in itertools.product(*(SWEEP_GRID[key] for key in SWEEP_GRID)):
                params = dict(zip(SWEEP_GRID.keys(), values))
                _apply(params)
                _, summary = simulate_backtest(
                    df,
                    model=model,
                    rl_model=None,
                    rl_action_series=None,
                    symbol="BTCUSDT",
                    strategy_models=strategy_models,
                )
                rows.append({**params, **summary, "score": _score(summary)})
        finally:
            _apply(original)

    results = pd.DataFrame(rows).sort_values(by="score", ascending=False).reset_index(drop=True)
    results.to_csv("logs/quick_mean_reversion_sweep.csv", index=False)
    best = results.iloc[0].to_dict()
    payload = {
        "best": {
            "score": best["score"],
            "parameters": {key: best[key] for key in SWEEP_GRID},
            "summary": {
                "trade_count": int(best["trade_count"]),
                "total_return_pct": best["total_return_pct"],
                "max_drawdown_pct": best["max_drawdown_pct"],
                "profit_factor": best["profit_factor"],
            },
        }
    }
    with open("logs/quick_mean_reversion_sweep.json", "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
