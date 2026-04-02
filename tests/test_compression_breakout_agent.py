import unittest

import pandas as pd

from agents.compression_breakout_agent import compression_breakout_signal


class CompressionBreakoutAgentTests(unittest.TestCase):
    def test_breakout_setup_emits_buy_signal(self):
        df = pd.DataFrame(
            [
                {
                    "bb_width": 0.012,
                    "breakout_up_20": 0.003,
                    "volume_ratio": 1.6,
                    "close_location": 0.82,
                    "range_efficiency": 0.70,
                    "signed_volume_proxy": 0.45,
                    "price_vs_ema20": 0.002,
                }
            ]
        )
        signal, confidence = compression_breakout_signal(df, prob_up=0.68)
        self.assertEqual(signal, 1)
        self.assertGreaterEqual(confidence, 0.68)

    def test_weak_breakout_stays_neutral(self):
        df = pd.DataFrame(
            [
                {
                    "bb_width": 0.030,
                    "breakout_up_20": -0.001,
                    "volume_ratio": 0.9,
                    "close_location": 0.40,
                    "range_efficiency": 0.20,
                    "signed_volume_proxy": -0.10,
                    "price_vs_ema20": -0.001,
                }
            ]
        )
        signal, _ = compression_breakout_signal(df, prob_up=0.52)
        self.assertEqual(signal, 0)


if __name__ == "__main__":
    unittest.main()
