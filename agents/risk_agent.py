def risk_check(volatility: float, daily_pnl_pct: float, max_daily_loss: float = 0.03) -> bool:
    if daily_pnl_pct <= -max_daily_loss:
        return False
    if volatility > 0.02:
        return False
    return True
