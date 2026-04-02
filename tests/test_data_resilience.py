import json
import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
import data


class DataResilienceTests(unittest.TestCase):
    def test_get_symbol_info_cached_falls_back_to_disk_cache(self):
        original_cache_path = SETTINGS.symbol_info_cache_path
        original_call = data._call_client_method
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.symbol_info_cache_path = os.path.join(tmpdir, "symbol_info_cache.json")
                with open(SETTINGS.symbol_info_cache_path, "w") as f:
                    json.dump({"BTCUSDT": {"symbol": "BTCUSDT", "filters": []}}, f)

                def failing_call(*args, **kwargs):
                    raise RuntimeError("network down")

                data._call_client_method = failing_call
                info = data.get_symbol_info_cached("BTCUSDT")

                self.assertEqual(info["symbol"], "BTCUSDT")
        finally:
            SETTINGS.symbol_info_cache_path = original_cache_path
            data._call_client_method = original_call

    def test_ordered_base_endpoints_prioritizes_last_success(self):
        original_endpoints = SETTINGS.base_endpoints_csv
        try:
            SETTINGS.base_endpoints_csv = "1,2,3"
            data._LAST_SUCCESSFUL_ENDPOINT = "2"
            self.assertEqual(data._ordered_base_endpoints()[0], "2")
        finally:
            SETTINGS.base_endpoints_csv = original_endpoints
            data._LAST_SUCCESSFUL_ENDPOINT = None

    def test_transient_api_error_is_detected(self):
        self.assertTrue(data._is_transient_api_error(RuntimeError("SSL record layer failure")))
        self.assertFalse(data._is_transient_api_error(RuntimeError("permission denied")))

    def test_get_last_price_falls_back_to_cached_close(self):
        original_cache_path = SETTINGS.market_data_cache_path
        original_call = data._call_client_method
        original_ws = data.load_websocket_snapshot
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.market_data_cache_path = os.path.join(tmpdir, "market_cache.csv")
                df = pd.DataFrame(
                    [
                        {
                            "open_time": "2026-03-28T10:00:00Z",
                            "o": 1.0,
                            "h": 1.2,
                            "l": 0.9,
                            "c": 1.1,
                            "v": 10.0,
                            "close_time": "2026-03-28T10:00:59.999Z",
                            "quote_asset_volume": 11.0,
                            "number_of_trades": 3,
                            "taker_buy_base": 5.0,
                            "taker_buy_quote": 5.5,
                            "ignore": 0.0,
                        }
                    ]
                )
                df.to_csv(SETTINGS.market_data_cache_path, index=False)

                def failing_call(*args, **kwargs):
                    raise RuntimeError("ssl failed")

                data._call_client_method = failing_call
                data.load_websocket_snapshot = lambda symbol=None: None
                price = data.get_last_price("BTCUSDT")
                self.assertEqual(price, 1.1)
        finally:
            SETTINGS.market_data_cache_path = original_cache_path
            data._call_client_method = original_call
            data.load_websocket_snapshot = original_ws

    def test_get_klines_df_falls_back_to_archive_for_non_primary_symbol(self):
        original_archive_path = SETTINGS.market_data_archive_path
        original_cache_path = SETTINGS.market_data_cache_path
        original_call = data._call_client_method
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.market_data_archive_path = os.path.join(tmpdir, "archive.csv")
                SETTINGS.market_data_cache_path = os.path.join(tmpdir, "cache.csv")
                archive_path = data.get_market_data_archive_path("ONTUSDT")
                df = pd.DataFrame(
                    [
                        {
                            "open_time": "2026-03-28T10:00:00Z",
                            "o": 1.0,
                            "h": 1.1,
                            "l": 0.95,
                            "c": 1.05,
                            "v": 10.0,
                            "close_time": "2026-03-28T10:00:59.999Z",
                            "quote_asset_volume": 10.5,
                            "number_of_trades": 4,
                            "taker_buy_base": 4.0,
                            "taker_buy_quote": 4.2,
                            "ignore": 0.0,
                        }
                    ]
                )
                df.to_csv(archive_path, index=False)

                def failing_call(*args, **kwargs):
                    raise RuntimeError("network down")

                data._call_client_method = failing_call
                out = data.get_klines_df(symbol="ONTUSDT", interval="1m", limit=1)
                self.assertEqual(len(out), 1)
                self.assertEqual(float(out["c"].iloc[-1]), 1.05)
        finally:
            SETTINGS.market_data_archive_path = original_archive_path
            SETTINGS.market_data_cache_path = original_cache_path
            data._call_client_method = original_call


if __name__ == "__main__":
    unittest.main()
