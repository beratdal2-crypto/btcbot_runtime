import unittest

from config import SETTINGS
from strategy_selector import select_symbol_strategy


class StrategySelectorTests(unittest.TestCase):
    def test_defensive_profile_selected_for_high_beta_symbol(self):
        result = select_symbol_strategy("DOGEUSDT", "UPTREND", atr_pct=0.006, volume_ratio=1.1, coin_score=55)
        self.assertEqual(result["name"], "defensive")

    def test_breakout_selected_for_strong_uptrend(self):
        original_flag = SETTINGS.btc_mean_reversion_only
        try:
            SETTINGS.btc_mean_reversion_only = False
            result = select_symbol_strategy("BTCUSDT", "UPTREND", atr_pct=0.002, volume_ratio=1.3, coin_score=70)
            self.assertEqual(result["name"], "breakout")
        finally:
            SETTINGS.btc_mean_reversion_only = original_flag

    def test_mean_reversion_selected_for_btc_range(self):
        result = select_symbol_strategy("BTCUSDT", "RANGE", atr_pct=0.004, volume_ratio=1.0, coin_score=50)
        self.assertEqual(result["name"], "mean_reversion")

    def test_ont_15m_breakout_spread_is_relaxed(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "15m"
            result = select_symbol_strategy("ONTUSDT", "UPTREND", atr_pct=0.01, volume_ratio=1.0, coin_score=20)
            self.assertEqual(result["name"], "ont_15m_breakout")
            self.assertGreater(result["spread_multiplier"], 1.0)
        finally:
            SETTINGS.research_interval = original_interval

    def test_ont_range_prefers_breakout_when_conditions_are_moderately_constructive(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "15m"
            result = select_symbol_strategy("ONTUSDT", "RANGE", atr_pct=0.01, volume_ratio=0.16, coin_score=20)
            self.assertEqual(result["name"], "ont_15m_breakout")
        finally:
            SETTINGS.research_interval = original_interval
