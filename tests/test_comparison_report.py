import os
import tempfile
import unittest

import pandas as pd

from comparison_report import build_live_paper_comparison
from config import SETTINGS


class ComparisonReportTests(unittest.TestCase):
    def test_build_live_paper_comparison_creates_output(self):
        original_trade = SETTINGS.trade_log_path
        original_backtest = SETTINGS.backtest_summary_path
        original_out = SETTINGS.live_paper_comparison_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.trade_log_path = os.path.join(tmpdir, "trades.csv")
                SETTINGS.backtest_summary_path = os.path.join(tmpdir, "backtest_summary.csv")
                SETTINGS.live_paper_comparison_path = os.path.join(tmpdir, "compare.csv")
                pd.DataFrame([{"action": "CLOSE_LONG", "profit_pct": 0.01}]).to_csv(SETTINGS.trade_log_path, index=False)
                pd.DataFrame([{"trade_count": 2, "total_return_pct": 1.5, "win_rate_pct": 55.0}]).to_csv(SETTINGS.backtest_summary_path, index=False)

                df = build_live_paper_comparison()

                self.assertTrue(os.path.exists(SETTINGS.live_paper_comparison_path))
                self.assertEqual(int(df.iloc[0]["live_trade_count"]), 1)
        finally:
            SETTINGS.trade_log_path = original_trade
            SETTINGS.backtest_summary_path = original_backtest
            SETTINGS.live_paper_comparison_path = original_out


if __name__ == "__main__":
    unittest.main()
