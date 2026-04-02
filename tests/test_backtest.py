import unittest

from backtest import _warmup_bars


class BacktestTests(unittest.TestCase):
    def test_warmup_bars_scales_for_shorter_series(self):
        self.assertEqual(_warmup_bars(0), 0)
        self.assertEqual(_warmup_bars(18), 20)
        self.assertEqual(_warmup_bars(49), 20)
        self.assertEqual(_warmup_bars(120), 40)
        self.assertEqual(_warmup_bars(500), 60)


if __name__ == "__main__":
    unittest.main()
