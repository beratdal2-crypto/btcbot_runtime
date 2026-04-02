import unittest

from agents.fusion import final_decision


class FusionTests(unittest.TestCase):
    def test_buy_requires_quality_filters(self):
        decision = final_decision(
            trend=1,
            scalp=1,
            rl_action=0,
            weights={"trend": 0.7, "scalp": 0.2, "rl": 0.1},
            risk_ok=True,
            regime="UPTREND",
            long_only=True,
            prob_up=0.58,
            volume_ratio=0.70,
            atr_pct=0.002,
        )
        self.assertEqual(decision, "HOLD")

    def test_buy_allowed_when_quality_is_good(self):
        decision = final_decision(
            trend=1,
            scalp=1,
            rl_action=1,
            weights={"trend": 0.7, "scalp": 0.2, "rl": 0.1},
            risk_ok=True,
            regime="UPTREND",
            long_only=True,
            prob_up=0.72,
            volume_ratio=1.10,
            atr_pct=0.002,
        )
        self.assertEqual(decision, "BUY")

    def test_long_entry_blocked_in_dowtrend(self):
        decision = final_decision(
            trend=-1,
            scalp=1,
            rl_action=0,
            weights={"trend": 0.55, "scalp": 0.15, "rl": 0.30},
            risk_ok=True,
            regime="DOWNTREND",
            long_only=True,
            prob_up=0.56,
            volume_ratio=0.70,
            atr_pct=0.002,
        )
        self.assertEqual(decision, "HOLD")

    def test_countertrend_reversion_can_allow_buy(self):
        decision = final_decision(
            trend=-1,
            scalp=1,
            rl_action=0,
            weights={"trend": 0.55, "scalp": 0.15, "rl": 0.30},
            risk_ok=True,
            regime="DOWNTREND",
            long_only=True,
            prob_up=0.60,
            volume_ratio=0.90,
            atr_pct=0.003,
        )
        self.assertEqual(decision, "BUY")

    def test_buy_blocked_when_spread_is_too_wide(self):
        decision = final_decision(
            trend=1,
            scalp=1,
            rl_action=1,
            weights={"trend": 0.7, "scalp": 0.2, "rl": 0.1},
            risk_ok=True,
            regime="UPTREND",
            long_only=True,
            prob_up=0.72,
            volume_ratio=1.10,
            atr_pct=0.002,
            spread_bps=25.0,
            depth_notional=10000.0,
        )
        self.assertEqual(decision, "HOLD")


if __name__ == "__main__":
    unittest.main()
