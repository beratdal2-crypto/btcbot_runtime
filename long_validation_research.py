from __future__ import annotations

import json
import os
from contextlib import contextmanager

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from backtest import simulate_backtest
from config import SETTINGS
from data import get_research_klines_df
from features import FEATURE_COLUMNS, build_features
from regime.regime_features import add_regime_features


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


def _evaluate_interval_horizon(interval: str, horizon: int) -> dict[str, object]:
    with _temporary_settings({"research_interval": interval, "target_horizon_bars": horizon}):
        raw = get_research_klines_df(
            limit=SETTINGS.long_validation_lookback_limit,
            symbol="BTCUSDT",
            interval=interval,
        )
        feat = add_regime_features(build_features(raw, imbalance=0.5))
        if len(feat) < 120:
            return {
                "interval": interval,
                "horizon": horizon,
                "rows": int(len(feat)),
                "train_rows": 0,
                "test_rows": 0,
                "trade_count": 0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "status": "insufficient_rows",
            }

        split = max(80, int(len(feat) * 0.75))
        train_df = feat.iloc[:split].copy()
        test_df = feat.iloc[split:].copy()
        model = RandomForestClassifier(
            n_estimators=160,
            max_depth=8,
            min_samples_split=16,
            min_samples_leaf=8,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=42,
        )
        model.fit(train_df[FEATURE_COLUMNS], train_df["target"])
        _, summary = simulate_backtest(
            test_df.reset_index(drop=True),
            model=model,
            strategy_models=None,
            rl_model=None,
            rl_action_series=None,
            symbol="BTCUSDT",
        )
        return {
            "interval": interval,
            "horizon": horizon,
            "rows": int(len(feat)),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "trade_count": int(summary.get("trade_count", 0)),
            "total_return_pct": float(summary.get("total_return_pct", 0.0)),
            "max_drawdown_pct": float(summary.get("max_drawdown_pct", 0.0)),
            "profit_factor": float(summary.get("profit_factor", 0.0)),
            "status": "ok",
        }


def main() -> None:
    os.makedirs("logs", exist_ok=True)
    rows: list[dict[str, object]] = []
    for interval in SETTINGS.long_validation_intervals():
        for horizon in SETTINGS.long_validation_horizons():
            row = _evaluate_interval_horizon(interval, horizon)
            rows.append(row)
            df = pd.DataFrame(rows).sort_values(
                by=["total_return_pct", "max_drawdown_pct", "trade_count"],
                ascending=[False, True, False],
            )
            df.to_csv("logs/long_validation_matrix.csv", index=False)
            best = df.iloc[0].to_dict() if not df.empty else {}
            with open("logs/long_validation_best.json", "w") as f:
                json.dump({"best": best, "rows": rows}, f, indent=2, sort_keys=True)
            print({"completed": len(rows), "last": row, "best": best})


if __name__ == "__main__":
    main()
