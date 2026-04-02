from __future__ import annotations

import json
import os
from contextlib import contextmanager
from itertools import product

import pandas as pd

from backtest import run_backtest
from config import SETTINGS
from walkforward import run_walkforward


RESULTS_PATH = "logs/ont_pullback_sweep.csv"
BEST_PATH = "logs/ont_pullback_best.json"


@contextmanager
def _temporary_settings(overrides: dict[str, object]):
    original = {key: getattr(SETTINGS, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(SETTINGS, key, value)
        yield
    finally:
        for key, value in original.items():
            setattr(SETTINGS, key, value)


def _score(bt_summary: dict, wf_df: pd.DataFrame) -> float:
    bt_return = float(bt_summary.get("total_return_pct", 0.0))
    bt_dd = float(bt_summary.get("max_drawdown_pct", 0.0))
    bt_pf = float(bt_summary.get("profit_factor", 0.0))
    bt_trades = int(bt_summary.get("trade_count", 0))

    if wf_df.empty:
        wf_avg_return = 0.0
        wf_avg_dd = 0.0
        wf_trade_count = 0
        wf_zero_folds = 0
    else:
        wf_avg_return = float(pd.to_numeric(wf_df["total_return_pct"], errors="coerce").fillna(0.0).mean())
        wf_avg_dd = float(pd.to_numeric(wf_df["max_drawdown_pct"], errors="coerce").fillna(0.0).mean())
        wf_trade_count = int(pd.to_numeric(wf_df["trade_count"], errors="coerce").fillna(0).sum())
        wf_zero_folds = int((pd.to_numeric(wf_df["trade_count"], errors="coerce").fillna(0) <= 0).sum())

    pf_term = 0.0 if bt_pf == float("inf") else bt_pf
    return (
        bt_return * 0.35
        + wf_avg_return * 1.40
        - bt_dd * 0.25
        - wf_avg_dd * 0.50
        + pf_term * 0.20
        + min(bt_trades, 8) * 0.05
        + min(wf_trade_count, 8) * 0.08
        - wf_zero_folds * 0.20
    )


def main() -> pd.DataFrame:
    os.makedirs("logs", exist_ok=True)

    grid = {
        "entry_score_threshold": [0.52, 0.54, 0.56],
        "entry_min_volume_ratio": [0.90, 0.95, 1.00],
        "mean_reversion_prob_floor": [0.44, 0.46, 0.48],
        "mean_reversion_min_model_prob_up": [0.38, 0.40, 0.42],
    }

    rows: list[dict[str, object]] = []
    for entry_score_threshold, entry_min_volume_ratio, prob_floor, model_prob_floor in product(
        grid["entry_score_threshold"],
        grid["entry_min_volume_ratio"],
        grid["mean_reversion_prob_floor"],
        grid["mean_reversion_min_model_prob_up"],
    ):
        overrides = {
            "entry_score_threshold": entry_score_threshold,
            "entry_min_volume_ratio": entry_min_volume_ratio,
            "mean_reversion_prob_floor": prob_floor,
            "mean_reversion_min_model_prob_up": model_prob_floor,
        }
        with _temporary_settings(overrides):
            _, bt_summary = run_backtest(
                profile_name="alt_5m_pullback",
                symbols=("ONTUSDT",),
                trades_path="logs/ont_pullback_grid_backtest_trades.csv",
                summary_path="logs/ont_pullback_grid_backtest_summary.csv",
                refresh_scores=False,
            )
            wf_df = run_walkforward(
                profile_name="alt_5m_pullback",
                symbols=("ONTUSDT",),
                output_path="logs/ont_pullback_grid_walkforward.csv",
                refresh_scores=False,
            )

        row = {
            **overrides,
            "bt_trade_count": int(bt_summary.get("trade_count", 0)),
            "bt_total_return_pct": float(bt_summary.get("total_return_pct", 0.0)),
            "bt_max_drawdown_pct": float(bt_summary.get("max_drawdown_pct", 0.0)),
            "bt_profit_factor": float(bt_summary.get("profit_factor", 0.0))
            if bt_summary.get("profit_factor", 0.0) != float("inf")
            else 5.0,
            "wf_fold_count": int(len(wf_df)) if not wf_df.empty else 0,
            "wf_trade_count": int(pd.to_numeric(wf_df.get("trade_count"), errors="coerce").fillna(0).sum()) if not wf_df.empty else 0,
            "wf_avg_return_pct": float(pd.to_numeric(wf_df.get("total_return_pct"), errors="coerce").fillna(0.0).mean()) if not wf_df.empty else 0.0,
            "wf_avg_max_drawdown_pct": float(pd.to_numeric(wf_df.get("max_drawdown_pct"), errors="coerce").fillna(0.0).mean()) if not wf_df.empty else 0.0,
        }
        row["research_score"] = _score(bt_summary, wf_df)
        rows.append(row)
        print(row)

    results = pd.DataFrame(rows).sort_values(
        ["research_score", "wf_avg_return_pct", "bt_total_return_pct"],
        ascending=False,
    ).reset_index(drop=True)
    results.to_csv(RESULTS_PATH, index=False)
    if not results.empty:
        with open(BEST_PATH, "w") as f:
            json.dump(results.iloc[0].to_dict(), f, indent=2, sort_keys=True)
    print(results.head(10).to_string(index=False))
    return results


if __name__ == "__main__":
    main()
