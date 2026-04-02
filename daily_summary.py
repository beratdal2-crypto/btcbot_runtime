from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from config import SETTINGS


def _safe_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def build_daily_summary() -> dict:
    trades = _safe_csv(SETTINGS.trade_log_path)
    alerts = _safe_csv(SETTINGS.alerts_log_path)
    comparison = _safe_csv(SETTINGS.live_paper_comparison_path)
    contribution = _safe_csv(SETTINGS.coin_contribution_path)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_count": 0,
        "closed_trade_count": 0,
        "net_profit_pct": 0.0,
        "recent_alert_count": 0,
        "top_coin": "",
        "live_vs_shadow_gap_pct": 0.0,
    }
    if trades is not None and not trades.empty:
        trades["profit_pct"] = pd.to_numeric(trades.get("profit_pct"), errors="coerce").fillna(0.0)
        summary["trade_count"] = int(len(trades))
        closed = trades[trades["action"].astype(str).str.startswith("CLOSE", na=False)]
        summary["closed_trade_count"] = int(len(closed))
        summary["net_profit_pct"] = float(closed["profit_pct"].sum() * 100) if not closed.empty else 0.0
    if alerts is not None and not alerts.empty:
        summary["recent_alert_count"] = int(len(alerts.tail(25)))
    if contribution is not None and not contribution.empty:
        summary["top_coin"] = str(contribution.iloc[0]["symbol"])
    if comparison is not None and not comparison.empty:
        row = comparison.iloc[-1]
        summary["live_vs_shadow_gap_pct"] = float(row.get("live_cum_profit_pct", 0.0) - row.get("shadow_cum_profit_pct", 0.0))

    os.makedirs(os.path.dirname(SETTINGS.daily_summary_path), exist_ok=True)
    with open(SETTINGS.daily_summary_path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    return summary


if __name__ == "__main__":
    print(build_daily_summary())
