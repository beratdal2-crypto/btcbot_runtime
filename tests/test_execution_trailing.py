import unittest

from execution import Position, _calculate_slippage_bps, maybe_close_position


class ExecutionTrailingTests(unittest.TestCase):
    def test_break_even_stop_closes_after_pullback(self):
        position = Position(symbol="BTCUSDT", side="LONG", entry_price=100.0, qty=1.0, peak_price=100.0, is_open=True)
        position, should_close, _, _ = maybe_close_position(position, 100.35)
        self.assertFalse(should_close)

        _, should_close, pnl_pct, reason = maybe_close_position(position, 100.02)
        self.assertTrue(should_close)
        self.assertGreaterEqual(pnl_pct, 0.0)
        self.assertIn(reason, {"trailing", "tp"})

    def test_trailing_stop_uses_peak_price(self):
        position = Position(symbol="BTCUSDT", side="LONG", entry_price=100.0, qty=1.0, peak_price=100.0, is_open=True)
        position, should_close, _, _ = maybe_close_position(position, 100.7)
        self.assertFalse(should_close)
        self.assertGreater(position.peak_price, 100.0)

        _, should_close, _, reason = maybe_close_position(position, 100.4)
        self.assertTrue(should_close)
        self.assertEqual(reason, "trailing")

    def test_slippage_helper_buy_and_sell(self):
        self.assertGreater(_calculate_slippage_bps(100.0, 100.2, "BUY"), 0)
        self.assertGreater(_calculate_slippage_bps(100.0, 99.8, "SELL"), 0)


if __name__ == "__main__":
    unittest.main()
