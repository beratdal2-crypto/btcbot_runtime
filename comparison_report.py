from __future__ import annotations

import os

import pandas as pd

from config import SETTINGS


def _safe_load_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def build_live_paper_comparison() -> pd.DataFrame:
    backtest = _safe_load_csv(SETTINGS.backtest_summary_path)
    trades = _safe_load_csv(SETTINGS.trade_log_path)
    portfolio_periods = _safe_load_csv(SETTINGS.portfolio_periods_path)
    shadow = _safe_load_csv(SETTINGS.shadow_trade_log_path)

    live_trade_count = 0
    live_cum_profit_pct = 0.0
    live_win_rate_pct = 0.0
    if trades is not None and not trades.empty:
        closed = trades[trades["action"].astype(str).str.startswith("CLOSE", na=False)].copy()
        if not closed.empty:
            pnl = pd.to_numeric(closed["profit_pct"], errors="coerce").fillna(0.0)
            live_trade_count = int(len(closed))
            live_cum_profit_pct = float(pnl.sum() * 100)
            live_win_rate_pct = float((pnl > 0).mean() * 100)

    backtest_trade_count = 0
    backtest_total_return_pct = 0.0
    backtest_win_rate_pct = 0.0
    if backtest is not None and not backtest.empty:
        row = backtest.iloc[-1]
        backtest_trade_count = int(row.get("trade_count", 0))
        backtest_total_return_pct = float(row.get("total_return_pct", 0.0))
        backtest_win_rate_pct = float(row.get("win_rate_pct", 0.0))

    shadow_trade_count = 0
    shadow_cum_profit_pct = 0.0
    if shadow is not None and not shadow.empty:
        closed = shadow[shadow["action"].astype(str).str.contains("CLOSE", na=False)].copy()
        if not closed.empty:
            pnl = pd.to_numeric(closed["profit_pct"], errors="coerce").fillna(0.0)
            shadow_trade_count = int(len(closed))
            shadow_cum_profit_pct = float(pnl.sum() * 100)

    df = pd.DataFrame(
        [
            {
                "live_trade_count": live_trade_count,
                "live_cum_profit_pct": live_cum_profit_pct,
                "live_win_rate_pct": live_win_rate_pct,
                "backtest_trade_count": backtest_trade_count,
                "backtest_total_return_pct": backtest_total_return_pct,
                "backtest_win_rate_pct": backtest_win_rate_pct,
                "shadow_trade_count": shadow_trade_count,
                "shadow_cum_profit_pct": shadow_cum_profit_pct,
                "delta_trade_count": live_trade_count - backtest_trade_count,
                "delta_return_pct": live_cum_profit_pct - backtest_total_return_pct,
                "delta_win_rate_pct": live_win_rate_pct - backtest_win_rate_pct,
                "live_7g_return_pct": float(
                    portfolio_periods.loc[portfolio_periods["period"] == "7g", "return_pct"].iloc[0]
                ) if portfolio_periods is not None and not portfolio_periods.empty and "period" in portfolio_periods.columns else 0.0,
            }
        ]
    )
    os.makedirs(os.path.dirname(SETTINGS.live_paper_comparison_path), exist_ok=True)
    df.to_csv(SETTINGS.live_paper_comparison_path, index=False)
    return df
