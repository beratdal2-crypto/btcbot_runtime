import unittest

from walkforward import _resolve_walkforward_window_sizes


class WalkforwardTests(unittest.TestCase):
    def test_resolve_walkforward_window_sizes_adapts_to_small_datasets(self):
        train_bars, test_bars, step_bars = _resolve_walkforward_window_sizes(49)

        self.assertGreaterEqual(train_bars, 25)
        self.assertGreaterEqual(test_bars, 24)
        self.assertLessEqual(train_bars + test_bars, 49)
        self.assertGreaterEqual(step_bars, 8)
        self.assertLessEqual(step_bars, test_bars)


if __name__ == "__main__":
    unittest.main()
