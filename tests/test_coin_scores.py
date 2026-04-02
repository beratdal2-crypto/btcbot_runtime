import os
import tempfile
import unittest

import pandas as pd

from coin_scores import compute_coin_scores, live_entry_guard, refresh_coin_scores, select_tradeable_symbols
from config import SETTINGS


class CoinScoreTests(unittest.TestCase):
    def test_compute_coin_scores_marks_strong_symbol_eligible(self):
        backtest_trades = pd.DataFrame(
            [
                {"symbol": "BTCUSDT", "return_pct": 0.010, "net_pnl": 10},
                {"symbol": "BTCUSDT", "return_pct": 0.005, "net_pnl": 5},
                {"symbol": "ETHUSDT", "return_pct": -0.004, "net_pnl": -4},
            ]
        )
        walkforward = pd.DataFrame(
            [
                {"symbol": "BTCUSDT", "trade_count": 8, "total_return_pct": 0.8, "win_rate_pct": 62, "max_drawdown_pct": 4.5},
                {"symbol": "ETHUSDT", "trade_count": 1, "total_return_pct": -1.2, "win_rate_pct": 0, "max_drawdown_pct": 14.0},
            ]
        )

        scores = compute_coin_scores(backtest_trades=backtest_trades, walkforward=walkforward, configured_symbols=("BTCUSDT", "ETHUSDT"))
        btc = scores.loc[scores["symbol"] == "BTCUSDT"].iloc[0]
        eth = scores.loc[scores["symbol"] == "ETHUSDT"].iloc[0]

        self.assertTrue(bool(btc["eligible"]))
        self.assertGreater(float(btc["score"]), float(eth["score"]))
        self.assertFalse(bool(eth["eligible"]))
        self.assertTrue(bool(eth["hard_block"]))

    def test_select_tradeable_symbols_keeps_primary_and_positive_secondaries_only(self):
        original_path = SETTINGS.coin_scores_path
        original_symbol = SETTINGS.symbol
        original_primary = SETTINGS.primary_symbol_csv
        original_secondary = SETTINGS.secondary_symbols_csv
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.coin_scores_path = os.path.join(tmpdir, "coin_scores.csv")
                SETTINGS.symbol = "BTCUSDT"
                SETTINGS.primary_symbol_csv = "BTCUSDT"
                SETTINGS.secondary_symbols_csv = "ETHUSDT,XRPUSDT"
                pd.DataFrame(
                    [
                        {"symbol": "BTCUSDT", "score": 62, "eligible": True, "hard_block": False, "bt_total_return_pct": 0.4, "wf_avg_return_pct": 0.1, "total_trade_count": 2},
                        {"symbol": "ETHUSDT", "score": 58, "eligible": True, "hard_block": False, "bt_total_return_pct": 0.6, "wf_avg_return_pct": 0.2, "total_trade_count": 3},
                        {"symbol": "XRPUSDT", "score": 57, "eligible": True, "hard_block": False, "bt_total_return_pct": 0.5, "wf_avg_return_pct": -0.1, "total_trade_count": 3},
                    ]
                ).to_csv(SETTINGS.coin_scores_path, index=False)

                selected, _ = select_tradeable_symbols(("BTCUSDT", "ETHUSDT", "XRPUSDT"))
                self.assertEqual(selected, ("BTCUSDT", "ETHUSDT"))
        finally:
            SETTINGS.coin_scores_path = original_path
            SETTINGS.symbol = original_symbol
            SETTINGS.primary_symbol_csv = original_primary
            SETTINGS.secondary_symbols_csv = original_secondary

    def test_refresh_coin_scores_writes_csv(self):
        original_path = SETTINGS.coin_scores_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.coin_scores_path = os.path.join(tmpdir, "coin_scores.csv")
                backtest_trades = pd.DataFrame([{"symbol": "BTCUSDT", "return_pct": 0.01, "net_pnl": 1.0}])
                walkforward = pd.DataFrame([{"symbol": "BTCUSDT", "trade_count": 5, "total_return_pct": 0.4, "win_rate_pct": 50, "max_drawdown_pct": 5.0}])

                refresh_coin_scores(backtest_trades=backtest_trades, walkforward=walkforward)

                self.assertTrue(os.path.exists(SETTINGS.coin_scores_path))
        finally:
            SETTINGS.coin_scores_path = original_path

    def test_live_entry_guard_blocks_hard_blocked_symbol(self):
        scores = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "score": 9.3,
                    "eligible": False,
                    "hard_block": True,
                    "reason": "skor_dusuk,hard_block",
                }
            ]
        )
        allowed, reason = live_entry_guard("BTCUSDT", scores=scores)

        self.assertFalse(allowed)
        self.assertIn("hard_block", reason)

    def test_live_entry_guard_allows_symbol_above_live_threshold(self):
        scores = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "score": 28.0,
                    "eligible": True,
                    "hard_block": False,
                    "reason": "uygun",
                }
            ]
        )
        allowed, reason = live_entry_guard("BTCUSDT", scores=scores)

        self.assertTrue(allowed)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
