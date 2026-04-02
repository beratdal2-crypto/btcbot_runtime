import unittest

from config import SETTINGS
from position_sizing import compute_position_fraction


class PositionSizingTests(unittest.TestCase):
    def test_higher_coin_score_increases_fraction(self):
        low = compute_position_fraction(base_fraction=0.05, atr_pct=0.003, coin_score=20)
        high = compute_position_fraction(base_fraction=0.05, atr_pct=0.003, coin_score=80)
        self.assertGreater(high, low)

    def test_high_volatility_reduces_fraction(self):
        calm = compute_position_fraction(base_fraction=0.05, atr_pct=0.002, coin_score=60)
        volatile = compute_position_fraction(base_fraction=0.05, atr_pct=0.010, coin_score=60)
        self.assertGreater(calm, volatile)

    def test_fraction_is_clamped(self):
        fraction = compute_position_fraction(base_fraction=0.9, atr_pct=0.0001, coin_score=100)
        self.assertLessEqual(fraction, SETTINGS.position_size_max_fraction)
        self.assertGreaterEqual(fraction, SETTINGS.position_size_min_fraction)


if __name__ == "__main__":
    unittest.main()
