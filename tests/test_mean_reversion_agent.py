import unittest

import pandas as pd

from agents.mean_reversion_agent import mean_reversion_signal


class MeanReversionAgentTests(unittest.TestCase):
    def test_oversold_setup_emits_buy_signal(self):
        df = pd.DataFrame(
            [
                {
                    "rsi": 35.0,
                    "bb_pos": 0.12,
                    "range_pos_20": 0.18,
                    "return_5": -0.006,
                    "atr_pct": 0.004,
                    "rsi_delta": 2.5,
                    "body_pct": 0.25,
                    "lower_wick_pct": 0.35,
                    "price_vs_ema20": -0.003,
                    "close_location": 0.55,
                    "signed_volume_proxy": 0.20,
                }
            ]
        )

        signal, confidence = mean_reversion_signal(df, prob_up=0.50)

        self.assertEqual(signal, 1)
        self.assertGreaterEqual(confidence, 0.50)

    def test_non_oversold_setup_stays_neutral(self):
        df = pd.DataFrame(
            [
                {
                    "rsi": 56.0,
                    "bb_pos": 0.62,
                    "range_pos_20": 0.68,
                    "return_5": 0.002,
                    "atr_pct": 0.004,
                    "rsi_delta": -0.2,
                    "body_pct": -0.10,
                    "lower_wick_pct": 0.05,
                    "price_vs_ema20": 0.001,
                    "close_location": 0.25,
                    "signed_volume_proxy": -0.10,
                }
            ]
        )

        signal, _ = mean_reversion_signal(df, prob_up=0.40)

        self.assertEqual(signal, 0)

    def test_oversold_without_reversal_confirmation_stays_neutral(self):
        df = pd.DataFrame(
            [
                {
                    "rsi": 34.0,
                    "bb_pos": 0.10,
                    "range_pos_20": 0.14,
                    "return_5": -0.008,
                    "atr_pct": 0.004,
                    "rsi_delta": -0.5,
                    "body_pct": -0.20,
                    "lower_wick_pct": 0.08,
                    "price_vs_ema20": -0.004,
                    "close_location": 0.22,
                    "signed_volume_proxy": -0.15,
                }
            ]
        )

        signal, _ = mean_reversion_signal(df, prob_up=0.55)

        self.assertEqual(signal, 0)

    def test_oversold_without_close_quality_stays_neutral(self):
        df = pd.DataFrame(
            [
                {
                    "rsi": 35.0,
                    "bb_pos": 0.12,
                    "range_pos_20": 0.18,
                    "return_5": -0.006,
                    "atr_pct": 0.004,
                    "rsi_delta": 2.5,
                    "body_pct": 0.25,
                    "lower_wick_pct": 0.35,
                    "price_vs_ema20": -0.003,
                    "close_location": 0.20,
                    "signed_volume_proxy": -0.10,
                }
            ]
        )

        signal, _ = mean_reversion_signal(df, prob_up=0.60)

        self.assertEqual(signal, 0)

    def test_oversold_with_low_model_probability_stays_neutral(self):
        df = pd.DataFrame(
            [
                {
                    "rsi": 35.0,
                    "bb_pos": 0.12,
                    "range_pos_20": 0.18,
                    "return_5": -0.006,
                    "atr_pct": 0.004,
                    "rsi_delta": 2.5,
                    "body_pct": 0.25,
                    "lower_wick_pct": 0.35,
                    "price_vs_ema20": -0.003,
                    "close_location": 0.55,
                    "signed_volume_proxy": 0.20,
                }
            ]
        )

        signal, confidence = mean_reversion_signal(df, prob_up=0.33)

        self.assertEqual(signal, 0)
        self.assertEqual(confidence, 0.33)


if __name__ == "__main__":
    unittest.main()
