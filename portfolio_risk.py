from __future__ import annotations

from dataclasses import dataclass
import json
import os

import pandas as pd

from config import SETTINGS


@dataclass
class PortfolioRiskResult:
    allow_entries: bool
    reason: str
    size_multiplier: float = 1.0
    mode: str = "normal"
    drawdown_pct: float = 0.0
    consecutive_losses: int = 0


def evaluate_portfolio_risk(
    trades: pd.DataFrame | None,
    equity: pd.DataFrame | None,
) -> PortfolioRiskResult:
    if trades is None:
        trades = pd.DataFrame()

    trades = trades.copy()
    if not trades.empty and "time" in trades.columns:
        trades["time"] = pd.to_datetime(trades["time"], errors="coerce", utc=True)
        today = pd.Timestamp.utcnow().normalize()
        today_trades = trades[trades["time"] >= today]
    else:
        today_trades = trades

    if not today_trades.empty and len(today_trades) >= SETTINGS.max_trades_per_day:
        result = PortfolioRiskResult(False, "gunluk_islem_limiti", mode="blocked")
        _save_self_protection_state(result)
        return result

    consecutive_losses = 0
    if not today_trades.empty and "action" in today_trades.columns:
        recent_closed = today_trades[today_trades["action"].astype(str).str.startswith("CLOSE", na=False)]
        for pnl in reversed(pd.to_numeric(recent_closed.get("profit_pct"), errors="coerce").fillna(0.0).tolist()):
            if pnl < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= SETTINGS.portfolio_max_consecutive_losses:
            result = PortfolioRiskResult(False, "ardisik_zararlar", mode="blocked", consecutive_losses=consecutive_losses)
            _save_self_protection_state(result)
            return result

    drawdown_pct = 0.0
    if equity is not None and not equity.empty and "equity_usdt" in equity.columns:
        eq = equity.copy()
        if "time" in eq.columns:
            eq["time"] = pd.to_datetime(eq["time"], errors="coerce", utc=True)
            eq = eq[eq["time"] >= pd.Timestamp.utcnow().normalize()]
        if not eq.empty:
            start_equity = float(eq["equity_usdt"].iloc[0])
            current_equity = float(eq["equity_usdt"].iloc[-1])
            if start_equity > 0:
                drawdown_pct = ((start_equity - current_equity) / start_equity) * 100
                if drawdown_pct >= SETTINGS.portfolio_max_daily_drawdown_pct:
                    result = PortfolioRiskResult(False, "gunluk_equity_drawdown", mode="blocked", drawdown_pct=drawdown_pct, consecutive_losses=consecutive_losses)
                    _save_self_protection_state(result)
                    return result
                if drawdown_pct >= SETTINGS.portfolio_caution_drawdown_pct:
                    result = PortfolioRiskResult(True, "temkinli_mod", size_multiplier=0.6, mode="caution", drawdown_pct=drawdown_pct, consecutive_losses=consecutive_losses)
                    _save_self_protection_state(result)
                    return result

    if SETTINGS.self_protection_enabled:
        if consecutive_losses >= SETTINGS.self_protection_max_loss_streak or drawdown_pct >= SETTINGS.self_protection_drawdown_pct:
            result = PortfolioRiskResult(
                True,
                "self_protection",
                size_multiplier=SETTINGS.self_protection_reduced_size_multiplier,
                mode="self_protection",
                drawdown_pct=drawdown_pct,
                consecutive_losses=consecutive_losses,
            )
            _save_self_protection_state(result)
            return result

    result = PortfolioRiskResult(True, "ok", mode="normal", drawdown_pct=drawdown_pct, consecutive_losses=consecutive_losses)
    _save_self_protection_state(result)
    return result


def _save_self_protection_state(result: PortfolioRiskResult) -> None:
    os.makedirs(os.path.dirname(SETTINGS.self_protection_state_path), exist_ok=True)
    with open(SETTINGS.self_protection_state_path, "w") as f:
        json.dump(
            {
                "allow_entries": result.allow_entries,
                "reason": result.reason,
                "size_multiplier": result.size_multiplier,
                "mode": result.mode,
                "drawdown_pct": result.drawdown_pct,
                "consecutive_losses": result.consecutive_losses,
            },
            f,
            indent=2,
            sort_keys=True,
        )
