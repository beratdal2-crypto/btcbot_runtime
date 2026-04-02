def detect_regime(row) -> str:
    trend_gap = float(row["trend_gap"])
    ret_15 = float(row["ret_15"])
    vol = float(row["volatility_20"])

    if vol > 0.012:
        return "HIGH_VOLATILITY"
    if trend_gap > 0.002 and ret_15 > 0:
        return "UPTREND"
    if trend_gap < -0.002 and ret_15 < 0:
        return "DOWNTREND"
    return "RANGE"
