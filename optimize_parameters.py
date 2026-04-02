import itertools
import json
import os
os.environ.setdefault("MPLCONFIGDIR", os.path.join("logs", ".mplconfig"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import joblib
import pandas as pd
from stable_baselines3 import PPO

from backtest import _aggregate_backtest_summaries, build_symbol_backtest_frame, precompute_rl_actions, simulate_backtest
from config import SETTINGS
from research_profiles import apply_research_profile


PARAM_GRID = {
    "buy_threshold": [0.50, 0.54, 0.58],
    "sell_threshold": [0.40],
    "take_profit_pct": [0.004, 0.005],
    "stop_loss_pct": [0.0025, 0.003],
    "entry_score_threshold": [0.40, 0.46, 0.52],
    "entry_prob_buffer": [0.00, 0.01],
    "entry_min_volume_ratio": [0.75, 0.85],
    "entry_max_atr_pct": [0.006, 0.008],
    "signal_exit_prob_threshold": [0.40, 0.44],
    "mean_reversion_prob_floor": [0.46, 0.50],
    "mean_reversion_rsi_delta_min": [1.0, 1.5],
}

PROFILE_PARAM_GRIDS = {
    "mean_reversion": {
        "buy_threshold": [0.58, 0.62],
        "sell_threshold": [0.40],
        "take_profit_pct": [0.004],
        "stop_loss_pct": [0.0025],
        "entry_score_threshold": [0.52, 0.56],
        "entry_prob_buffer": [0.005],
        "entry_min_volume_ratio": [0.90, 0.95],
        "entry_max_atr_pct": [0.006],
        "signal_exit_prob_threshold": [0.42, 0.44],
        "mean_reversion_prob_floor": [0.54, 0.58],
        "mean_reversion_rsi_delta_min": [1.5, 2.0],
    }
}


def _objective(summary: dict) -> float:
    profit_factor = summary["profit_factor"]
    if profit_factor == float("inf"):
        profit_factor = 5.0
    trade_bonus = min(summary["trade_count"], 40) * 0.025
    stability_bonus = max(0.0, 3.5 - abs(summary.get("symbol_return_std", 0.0))) * 0.20
    win_bonus = max(0.0, summary.get("win_rate_pct", 0.0) - 47.0) * 0.025
    trade_quality = max(0.0, summary.get("avg_trade_pct", 0.0)) * 0.30
    median_bonus = max(0.0, summary.get("median_trade_pct", 0.0)) * 0.18
    downside_penalty = abs(min(0.0, summary.get("worst_trade_pct", 0.0))) * 0.18
    negative_return_penalty = abs(min(0.0, summary.get("total_return_pct", 0.0))) * 0.90
    undertrading_penalty = max(0.0, 12 - summary.get("trade_count", 0)) * 0.12
    return (
        summary["total_return_pct"]
        - 0.55 * summary["max_drawdown_pct"]
        + 0.32 * profit_factor
        + trade_bonus
        + stability_bonus
        + win_bonus
        + trade_quality
        + median_bonus
        - downside_penalty
        - negative_return_penalty
        - undertrading_penalty
    )


def _current_param_state() -> dict:
    keys = list(PARAM_GRID.keys()) + [
        "require_trend_alignment",
        "require_nonnegative_rl",
        "block_dowtrend_longs",
        "enable_signal_exit",
    ]
    return {key: getattr(SETTINGS, key) for key in keys}


def _param_grid_for_profile(profile_name: str | None) -> dict[str, list]:
    return PROFILE_PARAM_GRIDS.get(str(profile_name or ""), PARAM_GRID)


def _apply_params(parameters: dict) -> None:
    for key, value in parameters.items():
        setattr(SETTINGS, key, value)


def run_optimization(
    profile_name: str | None = None,
    symbols: tuple[str, ...] | None = None,
    output_prefix: str | None = None,
) -> None:
    with apply_research_profile(profile_name):
        model = joblib.load(SETTINGS.model_path)
        rl_model = PPO.load(SETTINGS.rl_model_path) if os.path.exists(f"{SETTINGS.rl_model_path}.zip") else None
        symbol_inputs: dict[str, tuple[pd.DataFrame, list[int] | None]] = {}
        for symbol in tuple(symbols or SETTINGS.trading_symbols()):
            try:
                df = build_symbol_backtest_frame(symbol)
            except Exception as exc:
                print(f"[OPTIMIZER] {symbol} skipped: {exc}")
                continue
            rl_action_series = precompute_rl_actions(df, rl_model) if rl_model is not None else None
            symbol_inputs[symbol] = (df, rl_action_series)

        if not symbol_inputs:
            raise ValueError("Optimizasyon icin kullanilabilir sembol verisi bulunamadi.")

        original = _current_param_state()
        results: list[dict] = []
        symbol_results: dict[str, list[dict]] = {symbol: [] for symbol in symbol_inputs}

        param_grid = _param_grid_for_profile(profile_name)
        combinations = list(itertools.product(*(param_grid[key] for key in param_grid)))
        total_trials = len(combinations)
        for trial_index, values in enumerate(combinations, start=1):
            parameters = dict(zip(param_grid.keys(), values))
            parameters.update(
                {
                    "require_trend_alignment": False,
                    "require_nonnegative_rl": False,
                    "block_dowtrend_longs": True,
                    "enable_signal_exit": True,
                }
            )
            _apply_params(parameters)
            symbol_summaries: list[dict] = []
            for symbol, (df, rl_action_series) in symbol_inputs.items():
                _, summary = simulate_backtest(
                    df,
                    model=model,
                    rl_model=rl_model,
                    rl_action_series=rl_action_series,
                    symbol=symbol,
                )
                summary["symbol"] = symbol
                if profile_name:
                    summary["profile"] = profile_name
                symbol_summaries.append(summary)
                symbol_score = _objective(
                    {
                        **summary,
                        "symbol_return_std": 0.0,
                    }
                )
                symbol_results[symbol].append({"score": symbol_score, **parameters, **summary})
            summary = _aggregate_backtest_summaries(symbol_summaries, symbol_count=len(symbol_summaries))
            summary["symbols"] = ",".join(symbol_inputs.keys())
            if profile_name:
                summary["profile"] = profile_name
            summary["symbol_return_std"] = float(pd.Series([item["total_return_pct"] for item in symbol_summaries]).std(ddof=0))
            score = _objective(summary)
            results.append({"score": score, **parameters, **summary})
            if trial_index % 10 == 0 or trial_index == total_trials:
                print(f"trial {trial_index}/{total_trials} best_score_so_far={max(row['score'] for row in results):.4f}")

        _apply_params(original)

    results_df = pd.DataFrame(results).sort_values(by="score", ascending=False).reset_index(drop=True)
    optimization_results_path = SETTINGS.optimization_results_path
    best_params_path = SETTINGS.best_params_path
    symbol_best_params_path = SETTINGS.symbol_best_params_path
    symbol_optimization_results_path = SETTINGS.symbol_optimization_results_path
    if output_prefix:
        optimization_results_path = optimization_results_path.replace(".csv", f"_{output_prefix}.csv")
        best_params_path = best_params_path.replace(".json", f"_{output_prefix}.json")
        symbol_best_params_path = symbol_best_params_path.replace(".json", f"_{output_prefix}.json")
        symbol_optimization_results_path = symbol_optimization_results_path.replace(".csv", f"_{output_prefix}.csv")
    os.makedirs(os.path.dirname(optimization_results_path), exist_ok=True)
    results_df.to_csv(optimization_results_path, index=False)

    best_row = results_df.iloc[0].to_dict()
    best_parameters = {key: best_row[key] for key in _current_param_state().keys() if key in best_row}
    payload = {
        "score": best_row["score"],
        "summary": {
            "total_return_pct": best_row["total_return_pct"],
            "max_drawdown_pct": best_row["max_drawdown_pct"],
            "trade_count": int(best_row["trade_count"]),
            "profit_factor": best_row["profit_factor"],
            "symbol_return_std": best_row.get("symbol_return_std", 0.0),
        },
        "parameters": best_parameters,
    }
    with open(best_params_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    symbol_best_params: dict[str, dict] = {}
    symbol_output_rows: list[dict] = []
    for symbol, rows in symbol_results.items():
        if not rows:
            continue
        symbol_df = pd.DataFrame(rows).sort_values(by="score", ascending=False).reset_index(drop=True)
        symbol_df.to_csv(
            symbol_optimization_results_path.replace(".csv", f"_{symbol}.csv"),
            index=False,
        )
        symbol_row = symbol_df.iloc[0].to_dict()
        symbol_best_params[symbol] = {
            "score": symbol_row["score"],
            "parameters": {key: symbol_row[key] for key in param_grid.keys() if key in symbol_row},
        }
        symbol_output_rows.append(
            {
                "symbol": symbol,
                "score": symbol_row["score"],
                "trade_count": symbol_row.get("trade_count", 0),
                "total_return_pct": symbol_row.get("total_return_pct", 0.0),
                "max_drawdown_pct": symbol_row.get("max_drawdown_pct", 0.0),
                **symbol_best_params[symbol]["parameters"],
            }
        )
    with open(symbol_best_params_path, "w") as f:
        json.dump(symbol_best_params, f, indent=2, sort_keys=True)
    if symbol_output_rows:
        pd.DataFrame(symbol_output_rows).sort_values(by="score", ascending=False).to_csv(
            symbol_optimization_results_path,
            index=False,
        )

    print("Best score:", round(best_row["score"], 4))
    print("Best params saved:", best_params_path)
    print("Optimization results:", optimization_results_path)
    print("Symbol params:", symbol_best_params_path)
    print("Best summary:", payload["summary"])


if __name__ == "__main__":
    run_optimization()
