import os
os.environ.setdefault("MPLCONFIGDIR", os.path.join("logs", ".mplconfig"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import hashlib
import json
import contextlib
import pandas as pd
from stable_baselines3 import PPO

from backtest import build_symbol_backtest_frame, precompute_rl_actions, simulate_backtest
from coin_scores import refresh_coin_scores
from config import SETTINGS
from research_profiles import apply_research_profile
from rl_train import train_rl_model_on_df
from trainer import build_strategy_training_frames, train_model_on_df
import joblib


def _resolve_walkforward_window_sizes(total_rows: int) -> tuple[int, int, int]:
    train_bars = SETTINGS.walkforward_train_bars
    test_bars = SETTINGS.walkforward_test_bars
    step_bars = SETTINGS.walkforward_step_bars

    if total_rows >= train_bars + test_bars:
        return train_bars, test_bars, step_bars

    adaptive_train = max(25, int(total_rows * 0.52))
    adaptive_test = max(24, int(total_rows * 0.33))
    adaptive_step = max(12, min(adaptive_test, int(total_rows * 0.16)))

    while adaptive_train + adaptive_test > total_rows and adaptive_train > 25:
        adaptive_train -= 5
    while adaptive_train + adaptive_test > total_rows and adaptive_test > 24:
        adaptive_test -= 4

    adaptive_step = max(8, min(adaptive_step, adaptive_test))
    return adaptive_train, adaptive_test, adaptive_step


def _cache_key(symbol: str, train_df: pd.DataFrame, test_df: pd.DataFrame) -> str:
    train_end = str(train_df["close_time"].iloc[-1])
    test_end = str(test_df["close_time"].iloc[-1])
    raw = f"{symbol}|{len(train_df)}|{len(test_df)}|{train_end}|{test_end}|{SETTINGS.walkforward_rl_timesteps}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_paths(cache_key: str) -> tuple[str, str, str]:
    os.makedirs(SETTINGS.walkforward_cache_dir, exist_ok=True)
    model_path = os.path.join(SETTINGS.walkforward_cache_dir, f"{cache_key}_model.pkl")
    rl_path = os.path.join(SETTINGS.walkforward_cache_dir, f"{cache_key}_rl.zip")
    actions_path = os.path.join(SETTINGS.walkforward_cache_dir, f"{cache_key}_actions.json")
    return model_path, rl_path, actions_path


def run_walkforward(
    profile_name: str | None = None,
    symbols: tuple[str, ...] | None = None,
    output_path: str | None = None,
    refresh_scores: bool = True,
) -> pd.DataFrame:
    target_horizon = SETTINGS.target_horizon_bars
    output_path = output_path or SETTINGS.walkforward_results_path

    with apply_research_profile(profile_name):
        results = []
        last_window_sizes: tuple[int, int, int] | None = None

        for symbol in tuple(symbols or SETTINGS.trading_symbols()):
            try:
                df = build_symbol_backtest_frame(symbol)
            except Exception as exc:
                print(f"[WALKFORWARD] {symbol} skipped: {exc}")
                continue
            train_bars, test_bars, step_bars = _resolve_walkforward_window_sizes(len(df))
            last_window_sizes = (train_bars, test_bars, step_bars)
            fold = 0
            latest_rl_model = None

            for train_end in range(train_bars, len(df) - test_bars + 1, step_bars):
                fold += 1
                train_df = df.iloc[:train_end].copy()
                test_df = df.iloc[train_end: train_end + test_bars].copy()
                train_fit_df = train_df.iloc[:-target_horizon].copy()

                if len(train_fit_df) < 20 or len(test_df) < 24:
                    continue
                if train_fit_df["target"].nunique() < 2:
                    continue

                cache_key = _cache_key(symbol, train_fit_df, test_df)
                model_cache_path, rl_cache_path, actions_cache_path = _cache_paths(cache_key)

                if SETTINGS.walkforward_cache_enabled and os.path.exists(model_cache_path):
                    model = joblib.load(model_cache_path)
                else:
                    model = train_model_on_df(train_fit_df)
                    if SETTINGS.walkforward_cache_enabled:
                        joblib.dump(model, model_cache_path)
                strategy_models: dict[str, object] = {}
                for strategy_name, strategy_df in build_strategy_training_frames(train_fit_df).items():
                    if len(strategy_df) < SETTINGS.strategy_model_min_rows:
                        continue
                    if strategy_df["target"].nunique() < 2:
                        continue
                    strategy_models[strategy_name] = train_model_on_df(strategy_df)

                need_retrain_rl = (
                    latest_rl_model is None
                    or ((fold - 1) % max(1, SETTINGS.walkforward_rl_retrain_interval) == 0)
                )
                if SETTINGS.walkforward_cache_enabled and os.path.exists(rl_cache_path):
                    rl_model = PPO.load(rl_cache_path)
                elif need_retrain_rl:
                    rl_timesteps = min(SETTINGS.walkforward_rl_timesteps, max(1000, len(train_fit_df) * 10))
                    rl_model = train_rl_model_on_df(train_fit_df, total_timesteps=rl_timesteps)
                    if rl_model is not None and SETTINGS.walkforward_cache_enabled:
                        rl_model.save(rl_cache_path.replace(".zip", ""))
                else:
                    rl_model = latest_rl_model
                latest_rl_model = rl_model

                if SETTINGS.walkforward_cache_enabled and os.path.exists(actions_cache_path):
                    with open(actions_cache_path, "r") as f:
                        rl_action_series = json.load(f)
                else:
                    rl_action_series = precompute_rl_actions(test_df, rl_model) if rl_model is not None else None
                    if rl_action_series is not None and SETTINGS.walkforward_cache_enabled:
                        with open(actions_cache_path, "w") as f:
                            json.dump(rl_action_series, f)
                _, summary = simulate_backtest(
                    test_df,
                    model=model,
                    strategy_models=strategy_models,
                    rl_model=rl_model,
                    rl_action_series=rl_action_series,
                    starting_equity=SETTINGS.starting_equity,
                    symbol=symbol,
                )

                summary.update(
                    {
                        "symbol": symbol,
                        "fold": fold,
                        "train_start": str(train_df["close_time"].iloc[0]),
                        "train_end": str(train_df["close_time"].iloc[-1]),
                        "test_start": str(test_df["close_time"].iloc[0]),
                        "test_end": str(test_df["close_time"].iloc[-1]),
                        "train_rows": len(train_fit_df),
                        "test_rows": len(test_df),
                    }
                )
                if profile_name:
                    summary["profile"] = profile_name
                results.append(summary)
                print(
                    f"symbol={symbol} fold={fold} trades={summary['trade_count']} "
                    f"return={summary['total_return_pct']:.2f}% "
                    f"win_rate={summary['win_rate_pct']:.2f}% "
                    f"max_dd={summary['max_drawdown_pct']:.2f}%"
                )

        if not results:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            pd.DataFrame(
                columns=[
                    "fold", "trade_count", "starting_equity", "ending_equity", "total_return_pct",
                    "gross_pnl", "net_pnl", "total_fees", "win_rate_pct", "avg_trade_pct",
                    "median_trade_pct", "worst_trade_pct", "max_drawdown_pct", "profit_factor",
                    "avg_bars_held", "train_start", "train_end", "test_start", "test_end",
                    "train_rows", "test_rows",
                ]
            ).to_csv(output_path, index=False)
            print("Walk-forward icin yeterli veri veya gecerli fold bulunamadi.")
            print(f"CSV: {output_path}")
            return pd.DataFrame()

        results_df = pd.DataFrame(results)
        results_df.to_csv(output_path, index=False)
        if refresh_scores:
            refresh_coin_scores(walkforward=results_df)

    print("")
    print("Walk-forward ozeti")
    print("Fold sayisi:", len(results_df))
    if last_window_sizes is not None:
        print("Train/Test/Step:", last_window_sizes[0], "/", last_window_sizes[1], "/", last_window_sizes[2])
    print("Sembol sayisi:", results_df["symbol"].nunique() if "symbol" in results_df.columns else 0)
    print("Ortalama getiri:", round(results_df["total_return_pct"].mean(), 3), "%")
    print("Ortalama win rate:", round(results_df["win_rate_pct"].mean(), 3), "%")
    print("Ortalama max drawdown:", round(results_df["max_drawdown_pct"].mean(), 3), "%")
    print("Toplam trade:", int(results_df["trade_count"].sum()))
    print(f"CSV: {output_path}")
    return results_df


if __name__ == "__main__":
    run_walkforward()
