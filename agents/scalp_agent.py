from __future__ import annotations
import pandas as pd
from features import FEATURE_COLUMNS


def scalp_signal(model, df: pd.DataFrame, buy_threshold: float = 0.60, sell_threshold: float = 0.40) -> tuple[int, float]:
    x = df[FEATURE_COLUMNS].iloc[-1:]
    prob_up = float(model.predict_proba(x)[0][1])

    if prob_up >= buy_threshold:
        return 1, prob_up
    if prob_up <= sell_threshold:
        return -1, prob_up
    return 0, prob_up
