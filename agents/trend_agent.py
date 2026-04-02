import pandas as pd


def trend_signal(df: pd.DataFrame) -> int:
    ema_fast = df["c"].ewm(span=20, adjust=False).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=50, adjust=False).mean().iloc[-1]
    return 1 if ema_fast > ema_slow else -1
