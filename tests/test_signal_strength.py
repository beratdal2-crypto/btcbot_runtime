import unittest

from signal_strength import evaluate_signal_readiness


class SignalStrengthTests(unittest.TestCase):
    def test_ont_breakout_strong_ready_when_all_three_align(self):
        readiness = evaluate_signal_readiness(
            symbol="ONTUSDT",
            strategy_name="ont_15m_breakout",
            regime="RANGE",
            trend=0,
            breakout_signal=1,
            prob_up=0.56,
            buy_threshold=0.55,
            volume_ratio=0.15,
            spread_bps=5.0,
            depth_notional=6000.0,
            max_entry_spread_bps=6.0,
            min_entry_depth_notional=8000.0,
        )
        self.assertTrue(readiness.regime_ready)
        self.assertTrue(readiness.probability_ready)
        self.assertTrue(readiness.liquidity_ready)
        self.assertTrue(readiness.strong_ready)

    def test_ont_breakout_reports_missing_parts(self):
        readiness = evaluate_signal_readiness(
            symbol="ONTUSDT",
            strategy_name="ont_15m_breakout",
            regime="RANGE",
            trend=-1,
            breakout_signal=0,
            prob_up=0.49,
            buy_threshold=0.55,
            volume_ratio=0.02,
            spread_bps=12.0,
            depth_notional=1000.0,
            max_entry_spread_bps=6.0,
            min_entry_depth_notional=8000.0,
        )
        self.assertFalse(readiness.strong_ready)
        self.assertEqual(readiness.missing_parts, "rejim,olasilik,likidite")


if __name__ == "__main__":
    unittest.main()
