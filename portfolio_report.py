from __future__ import annotations

import json
import os

import pandas as pd

from config import SETTINGS


def _safe_load_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def _period_return_from_equity(equity: pd.DataFrame, window: str) -> float:
    if equity.empty or "time" not in equity.columns or "equity_usdt" not in equity.columns:
        return 0.0
    scoped = equity.copy()
    scoped["time"] = pd.to_datetime(scoped["time"], errors="coerce", utc=True)
    scoped = scoped.dropna(subset=["time", "equity_usdt"]).sort_values("time")
    if scoped.empty:
        return 0.0
    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(window)
    scoped = scoped[scoped["time"] >= cutoff]
    if scoped.empty:
        return 0.0
    start = float(scoped["equity_usdt"].iloc[0])
    end = float(scoped["equity_usdt"].iloc[-1])
    if start <= 0:
        return 0.0
    return ((end - start) / start) * 100


def build_portfolio_report() -> dict:
    trades = _safe_load_csv(SETTINGS.trade_log_path)
    equity = _safe_load_csv(SETTINGS.equity_log_path)
    audits = _safe_load_csv(SETTINGS.order_audit_log_path)

    closed = pd.DataFrame()
    if trades is not None and not trades.empty and "action" in trades.columns:
        closed = trades[trades["action"].astype(str).str.startswith("CLOSE", na=False)].copy()
        if not closed.empty:
            closed["profit_pct"] = pd.to_numeric(closed["profit_pct"], errors="coerce").fillna(0.0)
            closed["time"] = pd.to_datetime(closed["time"], errors="coerce", utc=True)

    total_fees = 0.0
    avg_slippage_bps = 0.0
    if audits is not None and not audits.empty:
        total_fees = float(pd.to_numeric(audits.get("estimated_fee_quote"), errors="coerce").fillna(0.0).sum())
        slippage = pd.to_numeric(audits.get("slippage_bps"), errors="coerce").dropna()
        if not slippage.empty:
            avg_slippage_bps = float(slippage.abs().mean())

    summary = {
        "closed_trade_count": int(len(closed)),
        "win_rate_pct": float((closed["profit_pct"] > 0).mean() * 100) if not closed.empty else 0.0,
        "net_profit_pct": float(closed["profit_pct"].sum() * 100) if not closed.empty else 0.0,
        "day_return_pct": _period_return_from_equity(equity, "1D") if equity is not None else 0.0,
        "week_return_pct": _period_return_from_equity(equity, "7D") if equity is not None else 0.0,
        "month_return_pct": _period_return_from_equity(equity, "30D") if equity is not None else 0.0,
        "total_fees_quote": total_fees,
        "avg_slippage_bps": avg_slippage_bps,
    }

    if equity is not None and not equity.empty and "equity_usdt" in equity.columns:
        eq = equity.copy()
        eq["equity_usdt"] = pd.to_numeric(eq["equity_usdt"], errors="coerce")
        eq = eq.dropna(subset=["equity_usdt"])
        if not eq.empty:
            peak = eq["equity_usdt"].cummax()
            drawdown = ((peak - eq["equity_usdt"]) / peak.replace(0, pd.NA)).fillna(0.0)
            summary["max_drawdown_pct"] = float(drawdown.max() * 100)
            summary["current_equity_usdt"] = float(eq["equity_usdt"].iloc[-1])
        else:
            summary["max_drawdown_pct"] = 0.0
            summary["current_equity_usdt"] = 0.0
    else:
        summary["max_drawdown_pct"] = 0.0
        summary["current_equity_usdt"] = 0.0

    periods = pd.DataFrame(
        [
            {"period": "1g", "return_pct": summary["day_return_pct"]},
            {"period": "7g", "return_pct": summary["week_return_pct"]},
            {"period": "30g", "return_pct": summary["month_return_pct"]},
        ]
    )

    coin_contrib = pd.DataFrame(columns=["symbol", "trade_count", "net_profit_pct"])
    if not closed.empty and "symbol" in closed.columns:
        coin_contrib = (
            closed.groupby("symbol")
            .agg(
                trade_count=("action", "count"),
                net_profit_pct=("profit_pct", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).sum() * 100)),
            )
            .reset_index()
            .sort_values("net_profit_pct", ascending=False)
        )

    os.makedirs(os.path.dirname(SETTINGS.portfolio_report_path), exist_ok=True)
    with open(SETTINGS.portfolio_report_path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    periods.to_csv(SETTINGS.portfolio_periods_path, index=False)
    coin_contrib.to_csv(SETTINGS.coin_contribution_path, index=False)
    return summary
