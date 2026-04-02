import unittest

import pandas as pd

from config import SETTINGS
from research_profiles import apply_research_profile, profile_names
from trainer import build_strategy_training_frames


class ResearchProfilesTests(unittest.TestCase):
    def test_profile_names_include_expected_profiles(self):
        names = profile_names()
        self.assertIn("balanced", names)
        self.assertIn("trend", names)
        self.assertIn("mean_reversion", names)

    def test_apply_research_profile_restores_settings(self):
        original = SETTINGS.mean_reversion_enabled
        with apply_research_profile("trend"):
            self.assertFalse(SETTINGS.mean_reversion_enabled)
        self.assertEqual(SETTINGS.mean_reversion_enabled, original)

    def test_build_strategy_training_frames_splits_regimes(self):
        df = pd.DataFrame(
            [
                {
                    "ema20": 105,
                    "ema50": 100,
                    "price_vs_ema20": 0.002,
                    "volume_ratio": 1.0,
                    "rsi": 55,
                    "bb_pos": 0.8,
                    "range_pos_20": 0.7,
                    "target": 1,
                },
                {
                    "ema20": 99,
                    "ema50": 101,
                    "price_vs_ema20": -0.004,
                    "volume_ratio": 0.95,
                    "rsi": 34,
                    "bb_pos": 0.1,
                    "range_pos_20": 0.15,
                    "target": 0,
                },
            ]
        )
        frames = build_strategy_training_frames(df)

        self.assertEqual(len(frames["trend"]), 1)
        self.assertEqual(len(frames["mean_reversion"]), 1)


if __name__ == "__main__":
    unittest.main()
