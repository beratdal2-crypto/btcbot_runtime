from __future__ import annotations

import os

import pandas as pd

from config import SETTINGS


def _safe_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def build_live_shadow_analysis() -> pd.DataFrame:
    live = _safe_csv(SETTINGS.trade_log_path)
    shadow = _safe_csv(SETTINGS.shadow_trade_log_path)
    rows: list[dict] = []
    symbols = set()
    if live is not None and "symbol" in live.columns:
        symbols.update(str(x).upper() for x in live["symbol"].dropna().tolist())
    if shadow is not None and "symbol" in shadow.columns:
        symbols.update(str(x).upper() for x in shadow["symbol"].dropna().tolist())

    for symbol in sorted(symbols):
        live_closed = pd.DataFrame() if live is None else live[(live["symbol"].astype(str).str.upper() == symbol) & (live["action"].astype(str).str.startswith("CLOSE", na=False))].copy()
        shadow_closed = pd.DataFrame() if shadow is None else shadow[(shadow["symbol"].astype(str).str.upper() == symbol) & (shadow["action"].astype(str).str.contains("CLOSE", na=False))].copy()
        live_pnl = float(pd.to_numeric(live_closed.get("profit_pct"), errors="coerce").fillna(0.0).sum() * 100) if not live_closed.empty else 0.0
        shadow_pnl = float(pd.to_numeric(shadow_closed.get("profit_pct"), errors="coerce").fillna(0.0).sum() * 100) if not shadow_closed.empty else 0.0
        rows.append(
            {
                "symbol": symbol,
                "live_trade_count": int(len(live_closed)),
                "shadow_trade_count": int(len(shadow_closed)),
                "live_profit_pct": live_pnl,
                "shadow_profit_pct": shadow_pnl,
                "gap_pct": live_pnl - shadow_pnl,
            }
        )
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(SETTINGS.live_shadow_analysis_path), exist_ok=True)
    df.to_csv(SETTINGS.live_shadow_analysis_path, index=False)
    return df


if __name__ == "__main__":
    print(build_live_shadow_analysis())
