import unittest

from strategy_models import (
    apply_breakout_signal_bias,
    enforce_strategy_signal_quality,
    is_breakout_strategy,
    should_force_ont_breakout_bias,
)


class StrategyModelQualityTests(unittest.TestCase):
    def test_mean_reversion_buy_blocked_when_probability_below_minimum(self):
        result = enforce_strategy_signal_quality(
            "mean_reversion",
            scalp=1,
            active_probability=0.33,
            alternate_probability=0.20,
            model_probability_value=0.33,
        )
        self.assertEqual(result, 0)

    def test_mean_reversion_buy_allowed_when_probability_and_margin_are_strong(self):
        result = enforce_strategy_signal_quality(
            "mean_reversion",
            scalp=1,
            active_probability=0.70,
            alternate_probability=0.60,
            model_probability_value=0.70,
        )
        self.assertEqual(result, 1)

    def test_btc_5m_range_uses_mean_reversion_rules(self):
        result = enforce_strategy_signal_quality(
            "btc_5m_range",
            scalp=1,
            active_probability=0.70,
            alternate_probability=0.60,
            model_probability_value=0.70,
        )
        self.assertEqual(result, 1)

    def test_mean_reversion_buy_blocked_when_model_probability_is_too_low(self):
        result = enforce_strategy_signal_quality(
            "mean_reversion",
            scalp=1,
            active_probability=0.70,
            alternate_probability=0.60,
            model_probability_value=0.33,
        )
        self.assertEqual(result, 0)

    def test_ont_breakout_is_treated_as_breakout_strategy(self):
        self.assertTrue(is_breakout_strategy("ont_15m_breakout"))

    def test_force_ont_breakout_bias_requires_constructive_regime(self):
        self.assertTrue(
            should_force_ont_breakout_bias(
                symbol="ONTUSDT",
                regime="RANGE",
                breakout_up_20=0.0005,
                close_location=0.50,
                range_efficiency=0.35,
                volume_ratio=0.85,
            )
        )
        self.assertFalse(
            should_force_ont_breakout_bias(
                symbol="ONTUSDT",
                regime="DOWNTREND",
                breakout_up_20=0.0005,
                close_location=0.50,
                range_efficiency=0.35,
                volume_ratio=0.85,
            )
        )

    def test_breakout_signal_bias_promotes_breakout_scalp(self):
        scalp, probability = apply_breakout_signal_bias(
            symbol="ONTUSDT",
            strategy_name="ont_15m_breakout",
            regime="RANGE",
            trend=1,
            scalp=0,
            active_probability=0.49,
            breakout_signal=1,
            breakout_confidence=0.55,
        )
        self.assertEqual(scalp, 1)
        self.assertGreaterEqual(probability, 0.58)


if __name__ == "__main__":
    unittest.main()
