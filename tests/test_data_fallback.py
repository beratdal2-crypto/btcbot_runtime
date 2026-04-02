import tempfile
import unittest
from pathlib import Path

import pandas as pd

from config import SETTINGS
from data import _build_ohlcv_from_heartbeat, _cache_market_data, _load_cached_market_data


def _sample_market_df(rows: int) -> pd.DataFrame:
    start = pd.Timestamp("2026-03-23 10:00:00")
    times = pd.date_range(start=start, periods=rows, freq="1min")
    return pd.DataFrame(
        {
            "open_time": times,
            "o": [100 + i for i in range(rows)],
            "h": [101 + i for i in range(rows)],
            "l": [99 + i for i in range(rows)],
            "c": [100.5 + i for i in range(rows)],
            "v": [1.0] * rows,
            "close_time": times + pd.Timedelta(minutes=1) - pd.Timedelta(milliseconds=1),
            "quote_asset_volume": [100.5 + i for i in range(rows)],
            "number_of_trades": [1] * rows,
            "taker_buy_base": [0.5] * rows,
            "taker_buy_quote": [50.25 + i for i in range(rows)],
            "ignore": [0.0] * rows,
        }
    )


class DataFallbackTests(unittest.TestCase):
    def test_build_ohlcv_from_heartbeat_reconstructs_expected_columns(self):
        original_heartbeat = SETTINGS.heartbeat_log_source_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                heartbeat_path = Path(tmpdir) / "heartbeat.csv"
                pd.DataFrame(
                    {
                        "time": [
                            "2026-03-23T10:00:05",
                            "2026-03-23T10:00:40",
                            "2026-03-23T10:01:10",
                            "2026-03-23T10:01:50",
                        ],
                        "price": [100.0, 101.0, 102.0, 99.0],
                    }
                ).to_csv(heartbeat_path, index=False)
                SETTINGS.heartbeat_log_source_path = str(heartbeat_path)

                df = _build_ohlcv_from_heartbeat(interval="1m", limit=None)

                self.assertIsNotNone(df)
                self.assertEqual(list(df.columns[:6]), ["open_time", "o", "h", "l", "c", "v"])
                self.assertEqual(len(df), 2)
                self.assertEqual(float(df.iloc[0]["o"]), 100.0)
                self.assertEqual(float(df.iloc[0]["h"]), 101.0)
                self.assertEqual(float(df.iloc[1]["l"]), 99.0)
        finally:
            SETTINGS.heartbeat_log_source_path = original_heartbeat

    def test_cache_market_data_keeps_larger_snapshot(self):
        original_cache_path = SETTINGS.market_data_cache_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                cache_path = Path(tmpdir) / "market_data_cache.csv"
                SETTINGS.market_data_cache_path = str(cache_path)

                large = _sample_market_df(5)
                small = _sample_market_df(2)
                _cache_market_data(large)
                _cache_market_data(small)

                cached = _load_cached_market_data(limit=None)
                self.assertIsNotNone(cached)
                self.assertEqual(len(cached), 5)
        finally:
            SETTINGS.market_data_cache_path = original_cache_path


if __name__ == "__main__":
    unittest.main()
