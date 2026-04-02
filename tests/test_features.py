import unittest

import pandas as pd

from config import SETTINGS
from features import FEATURE_COLUMNS, build_features


def _ohlcv_frame(rows: int = 120) -> pd.DataFrame:
    open_times = pd.date_range(start="2026-03-23 00:00:00", periods=rows, freq="1min")
    prices = [100 + i for i in range(rows)]
    return pd.DataFrame(
        {
            "open_time": open_times,
            "o": prices,
            "h": [p + 1.5 for p in prices],
            "l": [p - 1.0 for p in prices],
            "c": [p + 1.0 for p in prices],
            "v": [10 + (i % 5) for i in range(rows)],
            "close_time": open_times + pd.Timedelta(minutes=1) - pd.Timedelta(milliseconds=1),
        }
    )


class FeatureTests(unittest.TestCase):
    def test_build_features_includes_extended_feature_columns(self):
        df = build_features(_ohlcv_frame(), imbalance=0.25)

        self.assertFalse(df.empty)
        for column in FEATURE_COLUMNS:
            self.assertIn(column, df.columns)
        self.assertIn("target_r_multiple", df.columns)

    def test_target_uses_minimum_future_return_threshold(self):
        original_horizon = SETTINGS.target_horizon_bars
        original_tp = SETTINGS.target_take_profit_pct
        original_sl = SETTINGS.target_stop_loss_pct
        original_min_r = SETTINGS.target_min_r_multiple
        try:
            SETTINGS.target_horizon_bars = 1
            SETTINGS.target_take_profit_pct = 0.005
            SETTINGS.target_stop_loss_pct = 0.01
            SETTINGS.target_min_r_multiple = 0.25
            built = build_features(_ohlcv_frame(), imbalance=0.0)

            self.assertFalse(built.empty)
            self.assertIn(1, built["target"].tolist())
            self.assertTrue((built["target_r_multiple"] >= -1.0).all())
        finally:
            SETTINGS.target_horizon_bars = original_horizon
            SETTINGS.target_take_profit_pct = original_tp
            SETTINGS.target_stop_loss_pct = original_sl
            SETTINGS.target_min_r_multiple = original_min_r


if __name__ == "__main__":
    unittest.main()
