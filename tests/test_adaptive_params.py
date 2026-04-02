import unittest
import json
import os
import tempfile

from adaptive_params import symbol_threshold_overrides
from config import SETTINGS


class AdaptiveParamsTests(unittest.TestCase):
    def test_stronger_coin_gets_more_permissive_thresholds(self):
        weak = symbol_threshold_overrides("LTCUSDT", coin_score=20)
        strong = symbol_threshold_overrides("LTCUSDT", coin_score=80)

        self.assertLess(strong["buy_threshold"], weak["buy_threshold"])
        self.assertLess(strong["entry_score_threshold"], weak["entry_score_threshold"])
        self.assertGreater(strong["max_entry_spread_bps"], weak["max_entry_spread_bps"])

    def test_symbol_specific_best_params_override_defaults(self):
        original_path = SETTINGS.symbol_best_params_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.symbol_best_params_path = os.path.join(tmpdir, "symbol_params.json")
                with open(SETTINGS.symbol_best_params_path, "w") as f:
                    json.dump({"BTCUSDT": {"parameters": {"buy_threshold": 0.66, "signal_exit_prob_threshold": 0.39}}}, f)
                overrides = symbol_threshold_overrides("BTCUSDT", coin_score=50)
                self.assertEqual(overrides["buy_threshold"], 0.66)
                self.assertEqual(overrides["signal_exit_prob_threshold"], 0.39)
        finally:
            SETTINGS.symbol_best_params_path = original_path


if __name__ == "__main__":
    unittest.main()
