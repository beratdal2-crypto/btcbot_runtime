import unittest

import pandas as pd

from trainer import build_strategy_training_frames


class TrainerBreakoutFrameTests(unittest.TestCase):
    def test_breakout_examples_are_kept_in_trend_frame(self):
        df = pd.DataFrame(
            [
                {
                    "symbol": "ONTUSDT",
                    "ema20": 1.0,
                    "ema50": 1.1,
                    "price_vs_ema20": -0.01,
                    "volume_ratio": 0.9,
                    "breakout_up_20": 0.001,
                    "close_location": 0.6,
                    "range_efficiency": 0.5,
                    "signed_volume_proxy": 0.06,
                    "rsi": 50.0,
                    "bb_pos": 0.5,
                    "range_pos_20": 0.5,
                    "target": 1,
                }
            ]
        )

        frames = build_strategy_training_frames(df)
        self.assertEqual(len(frames["trend"]), 1)


if __name__ == "__main__":
    unittest.main()
