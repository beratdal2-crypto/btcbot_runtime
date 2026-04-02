import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from live_shadow_analysis import build_live_shadow_analysis


class LiveShadowAnalysisTests(unittest.TestCase):
    def test_live_shadow_analysis_builds_gap_table(self):
        original_values = {
            "trade_log_path": SETTINGS.trade_log_path,
            "shadow_trade_log_path": SETTINGS.shadow_trade_log_path,
            "live_shadow_analysis_path": SETTINGS.live_shadow_analysis_path,
        }
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.trade_log_path = os.path.join(tmpdir, "trades.csv")
                SETTINGS.shadow_trade_log_path = os.path.join(tmpdir, "shadow.csv")
                SETTINGS.live_shadow_analysis_path = os.path.join(tmpdir, "analysis.csv")

                pd.DataFrame([{"symbol": "BTCUSDT", "action": "CLOSE_LONG", "profit_pct": 0.02}]).to_csv(SETTINGS.trade_log_path, index=False)
                pd.DataFrame([{"symbol": "BTCUSDT", "action": "SHADOW_CLOSE", "profit_pct": 0.01}]).to_csv(SETTINGS.shadow_trade_log_path, index=False)

                df = build_live_shadow_analysis()

                self.assertEqual(len(df), 1)
                self.assertAlmostEqual(float(df.iloc[0]["gap_pct"]), 1.0)
                self.assertTrue(os.path.exists(SETTINGS.live_shadow_analysis_path))
        finally:
            for key, value in original_values.items():
                setattr(SETTINGS, key, value)
