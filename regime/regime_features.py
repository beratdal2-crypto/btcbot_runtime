from __future__ import annotations
import pandas as pd


def add_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = out["c"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["c"].ewm(span=50, adjust=False).mean()
    out["trend_gap"] = (out["ema20"] - out["ema50"]) / out["c"]
    out["ret_5"] = out["c"].pct_change(5)
    out["ret_15"] = out["c"].pct_change(15)
    out["volatility_20"] = out["c"].pct_change().rolling(20).std()
    out["volume_ma20"] = out["v"].rolling(20).mean()
    out["volume_ratio"] = out["v"] / out["volume_ma20"]
    return out.dropna().reset_index(drop=True)
