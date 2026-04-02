import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from daily_summary import build_daily_summary


class DailySummaryTests(unittest.TestCase):
    def test_daily_summary_collects_outputs(self):
        original_values = {
            "trade_log_path": SETTINGS.trade_log_path,
            "alerts_log_path": SETTINGS.alerts_log_path,
            "live_paper_comparison_path": SETTINGS.live_paper_comparison_path,
            "coin_contribution_path": SETTINGS.coin_contribution_path,
            "daily_summary_path": SETTINGS.daily_summary_path,
        }
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.trade_log_path = os.path.join(tmpdir, "trades.csv")
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                SETTINGS.live_paper_comparison_path = os.path.join(tmpdir, "comparison.csv")
                SETTINGS.coin_contribution_path = os.path.join(tmpdir, "contribution.csv")
                SETTINGS.daily_summary_path = os.path.join(tmpdir, "summary.json")

                pd.DataFrame(
                    [
                        {"time": "2026-01-01T00:00:00Z", "symbol": "BTCUSDT", "action": "BUY", "profit_pct": 0.0},
                        {"time": "2026-01-01T00:20:00Z", "symbol": "BTCUSDT", "action": "CLOSE_LONG", "profit_pct": 0.02},
                    ]
                ).to_csv(SETTINGS.trade_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "level": "WARN"}]).to_csv(SETTINGS.alerts_log_path, index=False)
                pd.DataFrame([{"live_cum_profit_pct": 3.0, "shadow_cum_profit_pct": 1.0}]).to_csv(SETTINGS.live_paper_comparison_path, index=False)
                pd.DataFrame([{"symbol": "BTCUSDT", "return_pct": 2.0}]).to_csv(SETTINGS.coin_contribution_path, index=False)

                report = build_daily_summary()

                self.assertEqual(report["closed_trade_count"], 1)
                self.assertEqual(report["top_coin"], "BTCUSDT")
                self.assertTrue(os.path.exists(SETTINGS.daily_summary_path))
        finally:
            for key, value in original_values.items():
                setattr(SETTINGS, key, value)
