import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from config import SETTINGS
from data import (
    archive_latest_klines,
    _merge_market_data,
    _regularize_market_df,
    _write_market_archive,
    get_market_data_archive_path,
    get_market_data_cache_path,
    get_research_klines_df,
    load_market_data_archive,
)


def _market_df(start: str, prices: list[float]) -> pd.DataFrame:
    open_times = pd.date_range(start=start, periods=len(prices), freq="1min")
    return pd.DataFrame(
        {
            "open_time": open_times,
            "o": prices,
            "h": [p + 1 for p in prices],
            "l": [p - 1 for p in prices],
            "c": [p + 0.5 for p in prices],
            "v": [1.0] * len(prices),
            "close_time": open_times + pd.Timedelta(minutes=1) - pd.Timedelta(milliseconds=1),
            "quote_asset_volume": [p + 0.5 for p in prices],
            "number_of_trades": [1] * len(prices),
            "taker_buy_base": [0.5] * len(prices),
            "taker_buy_quote": [p * 0.5 for p in prices],
            "ignore": [0.0] * len(prices),
        }
    )


class DataArchiveTests(unittest.TestCase):
    def test_market_data_archive_path_uses_symbol_suffix(self):
        base_path = SETTINGS.market_data_archive_path
        expected_root = str(Path(base_path).with_suffix(""))
        expected_ext = Path(base_path).suffix or ".csv"

        self.assertEqual(get_market_data_archive_path(SETTINGS.symbol), base_path)
        self.assertEqual(
            get_market_data_archive_path("ETHUSDT"),
            f"{expected_root}_ETHUSDT{expected_ext}",
        )

    def test_market_data_cache_path_uses_symbol_suffix(self):
        base_path = SETTINGS.market_data_cache_path
        expected_root = str(Path(base_path).with_suffix(""))
        expected_ext = Path(base_path).suffix or ".csv"

        self.assertEqual(get_market_data_cache_path(SETTINGS.symbol), base_path)
        self.assertEqual(
            get_market_data_cache_path("SOLUSDT"),
            f"{expected_root}_SOLUSDT{expected_ext}",
        )

    def test_merge_market_data_deduplicates_open_time(self):
        existing = _market_df("2026-03-23 10:00:00", [100, 101, 102])
        incoming = _market_df("2026-03-23 10:02:00", [202, 203])
        merged = _merge_market_data(existing, incoming)

        self.assertEqual(len(merged), 4)
        self.assertEqual(float(merged.iloc[2]["o"]), 202.0)
        self.assertEqual(float(merged.iloc[3]["o"]), 203.0)

    def test_research_klines_prefers_archive(self):
        original_archive = SETTINGS.market_data_archive_path
        original_training_limit = SETTINGS.training_lookback_limit
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_path = Path(tmpdir) / "market_data_archive.csv"
                SETTINGS.market_data_archive_path = str(archive_path)
                SETTINGS.training_lookback_limit = 3

                archived = _market_df("2026-03-23 10:00:00", [100, 101, 102, 103, 104])
                _write_market_archive(archived)

                loaded = load_market_data_archive(limit=None)
                research = get_research_klines_df(limit=3)

                self.assertIsNotNone(loaded)
                self.assertEqual(len(loaded), 5)
                self.assertEqual(len(research), 3)
                self.assertEqual(float(research.iloc[-1]["o"]), 104.0)
        finally:
            SETTINGS.market_data_archive_path = original_archive
            SETTINGS.training_lookback_limit = original_training_limit

    def test_archive_latest_klines_backfills_multiple_batches(self):
        original_archive = SETTINGS.market_data_archive_path
        original_batch_limit = SETTINGS.archive_batch_limit
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.market_data_archive_path = str(Path(tmpdir) / "market_data_archive.csv")
                SETTINGS.archive_batch_limit = 2

                older = _market_df("2026-03-23 10:00:00", [100, 101])
                newer = _market_df("2026-03-23 10:02:00", [102, 103])

                def _rows(df: pd.DataFrame) -> list[list]:
                    return df.astype({"open_time": "datetime64[ns]", "close_time": "datetime64[ns]"}).assign(
                        open_time=lambda frame: (frame["open_time"].astype("int64") // 10**6),
                        close_time=lambda frame: (frame["close_time"].astype("int64") // 10**6),
                    ).values.tolist()

                with patch("data._call_client_method", side_effect=[_rows(newer), _rows(older)]) as call_mock:
                    archived = archive_latest_klines(symbol="BTCUSDT", backfill_bars=4, force_refresh=True)

                self.assertEqual(call_mock.call_count, 2)
                self.assertEqual(len(archived), 4)
                self.assertEqual(float(archived.iloc[0]["o"]), 100.0)
                self.assertEqual(float(archived.iloc[-1]["o"]), 103.0)
        finally:
            SETTINGS.market_data_archive_path = original_archive
            SETTINGS.archive_batch_limit = original_batch_limit

    def test_archive_latest_klines_extends_older_history_when_existing_is_short(self):
        original_archive = SETTINGS.market_data_archive_path
        original_batch_limit = SETTINGS.archive_batch_limit
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.market_data_archive_path = str(Path(tmpdir) / "market_data_archive.csv")
                SETTINGS.archive_batch_limit = 2

                existing = _market_df("2026-03-23 10:02:00", [102, 103])
                _write_market_archive(existing)
                older = _market_df("2026-03-23 10:00:00", [100, 101])

                def _rows(df: pd.DataFrame) -> list[list]:
                    return df.astype({"open_time": "datetime64[ns]", "close_time": "datetime64[ns]"}).assign(
                        open_time=lambda frame: (frame["open_time"].astype("int64") // 10**6),
                        close_time=lambda frame: (frame["close_time"].astype("int64") // 10**6),
                    ).values.tolist()

                with patch("data._call_client_method", side_effect=[_rows(older), []]) as call_mock:
                    archived = archive_latest_klines(symbol="BTCUSDT", backfill_bars=4, force_refresh=False)

                self.assertGreaterEqual(call_mock.call_count, 1)
                self.assertEqual(len(archived), 4)
                self.assertEqual(float(archived.iloc[0]["o"]), 100.0)
                self.assertEqual(float(archived.iloc[-1]["o"]), 103.0)
        finally:
            SETTINGS.market_data_archive_path = original_archive
            SETTINGS.archive_batch_limit = original_batch_limit

    def test_regularize_market_df_fills_missing_minutes(self):
        raw = _market_df("2026-03-23 10:00:00", [100, 101, 102]).iloc[[0, 2]].reset_index(drop=True)

        regularized = _regularize_market_df(raw)

        self.assertEqual(len(regularized), 3)
        self.assertEqual(str(regularized.iloc[1]["open_time"]), "2026-03-23 10:01:00")
        self.assertEqual(float(regularized.iloc[1]["o"]), 100.5)
        self.assertEqual(float(regularized.iloc[1]["c"]), 100.5)
        self.assertEqual(float(regularized.iloc[1]["v"]), 0.0)

    def test_research_archive_can_resample_to_five_minutes(self):
        original_archive = SETTINGS.market_data_archive_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_path = Path(tmpdir) / "market_data_archive.csv"
                SETTINGS.market_data_archive_path = str(archive_path)

                archived = _market_df(
                    "2026-03-23 10:00:00",
                    [100, 101, 102, 103, 104, 105],
                )
                _write_market_archive(archived)

                research = get_research_klines_df(limit=10, interval="5m")

                self.assertEqual(len(research), 2)
                self.assertEqual(float(research.iloc[0]["o"]), 100.0)
                self.assertEqual(float(research.iloc[0]["c"]), 104.5)
        finally:
            SETTINGS.market_data_archive_path = original_archive


if __name__ == "__main__":
    unittest.main()
