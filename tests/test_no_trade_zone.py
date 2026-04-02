import unittest

from no_trade_zone import detect_no_trade_zone


class NoTradeZoneTests(unittest.TestCase):
    def test_blocks_uncertain_probability(self):
        active, reason = detect_no_trade_zone(
            symbol="BTCUSDT",
            regime="UPTREND",
            prob_up=0.53,
            volume_ratio=1.0,
            atr_pct=0.003,
            spread_bps=4.0,
            depth_notional=10000.0,
            last_bar_return_pct=0.1,
            max_entry_spread_bps=10.0,
            min_entry_depth_notional=1000.0,
            min_probability_edge=0.05,
        )
        self.assertTrue(active)
        self.assertEqual(reason, "olasilik_kararsiz")

    def test_blocks_spike_for_high_beta_coin(self):
        active, reason = detect_no_trade_zone(
            symbol="DOGEUSDT",
            regime="UPTREND",
            prob_up=0.75,
            volume_ratio=1.0,
            atr_pct=0.003,
            spread_bps=4.0,
            depth_notional=10000.0,
            last_bar_return_pct=1.2,
            max_entry_spread_bps=10.0,
            min_entry_depth_notional=1000.0,
            min_probability_edge=0.05,
        )
        self.assertTrue(active)
        self.assertEqual(reason, "bar_spike")

    def test_ont_uses_symbol_specific_probability_edge(self):
        active, reason = detect_no_trade_zone(
            symbol="ONTUSDT",
            regime="RANGE",
            prob_up=0.476,
            volume_ratio=1.0,
            atr_pct=0.003,
            spread_bps=4.0,
            depth_notional=10000.0,
            last_bar_return_pct=0.1,
            max_entry_spread_bps=10.0,
            min_entry_depth_notional=1000.0,
            min_probability_edge=0.045,
        )
        self.assertFalse(active)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
