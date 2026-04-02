import unittest

from altcoin_strategy_research import ALTCOIN_PROFILES, ONT_SPECIFIC_PROFILES
from config import SETTINGS
from research_profiles import get_profile_overrides
from strategy_selector import select_symbol_strategy


class AltcoinResearchTests(unittest.TestCase):
    def test_ont_specific_profiles_registered(self):
        self.assertIn("ont_5m_breakout", ONT_SPECIFIC_PROFILES)
        self.assertIn("ont_15m_breakout", ONT_SPECIFIC_PROFILES)
        self.assertIn("ont_15m_pullback", ONT_SPECIFIC_PROFILES)
        self.assertNotIn("ont_5m_breakout", ALTCOIN_PROFILES)

    def test_alt_research_symbols_excludes_primary(self):
        symbols = SETTINGS.alt_research_symbols()
        self.assertNotIn(SETTINGS.primary_symbol(), symbols)
        self.assertGreaterEqual(len(symbols), 1)

    def test_altcoin_breakout_profile_selected_in_5m_uptrend(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "5m"
            strategy = select_symbol_strategy(
                symbol="SOLUSDT",
                regime="UPTREND",
                atr_pct=0.011,
                volume_ratio=1.20,
                coin_score=35.0,
            )
            self.assertEqual(strategy["name"], "alt_5m_breakout")
        finally:
            SETTINGS.research_interval = original_interval

    def test_altcoin_pullback_profile_selected_in_5m_range(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "5m"
            strategy = select_symbol_strategy(
                symbol="SOLUSDT",
                regime="RANGE",
                atr_pct=0.010,
                volume_ratio=1.00,
                coin_score=30.0,
            )
            self.assertEqual(strategy["name"], "alt_5m_pullback")
        finally:
            SETTINGS.research_interval = original_interval

    def test_eth_specific_pullback_profile_selected_before_generic_alt_profile(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "5m"
            strategy = select_symbol_strategy(
                symbol="ETHUSDT",
                regime="RANGE",
                atr_pct=0.010,
                volume_ratio=0.95,
                coin_score=40.0,
            )
            self.assertEqual(strategy["name"], "eth_5m_pullback")
        finally:
            SETTINGS.research_interval = original_interval

    def test_eth_specific_continuation_profile_selected_in_5m_uptrend(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "5m"
            strategy = select_symbol_strategy(
                symbol="ETHUSDT",
                regime="UPTREND",
                atr_pct=0.010,
                volume_ratio=1.05,
                coin_score=40.0,
            )
            self.assertEqual(strategy["name"], "eth_5m_continuation")
        finally:
            SETTINGS.research_interval = original_interval

    def test_ont_specific_breakout_profile_selected_before_generic_alt_profile(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "5m"
            strategy = select_symbol_strategy(
                symbol="ONTUSDT",
                regime="UPTREND",
                atr_pct=0.012,
                volume_ratio=1.06,
                coin_score=28.0,
            )
            self.assertEqual(strategy["name"], "ont_5m_breakout")
        finally:
            SETTINGS.research_interval = original_interval

    def test_ont_specific_15m_pullback_profile_selected_before_generic_alt_profile(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "15m"
            strategy = select_symbol_strategy(
                symbol="ONTUSDT",
                regime="RANGE",
                atr_pct=0.014,
                volume_ratio=0.92,
                coin_score=20.0,
            )
            self.assertEqual(strategy["name"], "ont_15m_pullback")
        finally:
            SETTINGS.research_interval = original_interval

    def test_ont_specific_15m_breakout_profile_selected(self):
        original_interval = SETTINGS.research_interval
        try:
            SETTINGS.research_interval = "15m"
            strategy = select_symbol_strategy(
                symbol="ONTUSDT",
                regime="UPTREND",
                atr_pct=0.017,
                volume_ratio=0.96,
                coin_score=18.0,
            )
            self.assertEqual(strategy["name"], "ont_15m_breakout")
        finally:
            SETTINGS.research_interval = original_interval

    def test_ont_15m_breakout_profile_has_walkforward_overrides(self):
        overrides = get_profile_overrides("ont_15m_breakout")
        self.assertEqual(overrides["walkforward_train_bars"], 144)
        self.assertEqual(overrides["walkforward_test_bars"], 48)
        self.assertEqual(overrides["walkforward_step_bars"], 24)


if __name__ == "__main__":
    unittest.main()
