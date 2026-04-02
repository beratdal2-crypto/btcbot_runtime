def regime_weights(regime: str) -> dict:
    if regime == "UPTREND":
        return {"trend": 0.70, "scalp": 0.20, "rl": 0.10}
    if regime == "DOWNTREND":
        return {"trend": 0.55, "scalp": 0.15, "rl": 0.30}
    if regime == "RANGE":
        return {"trend": 0.15, "scalp": 0.70, "rl": 0.15}
    if regime == "HIGH_VOLATILITY":
        return {"trend": 0.10, "scalp": 0.10, "rl": 0.20}
    return {"trend": 0.33, "scalp": 0.33, "rl": 0.34}
