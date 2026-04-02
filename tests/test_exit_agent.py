import unittest

from agents.exit_agent import should_signal_exit


class ExitAgentTests(unittest.TestCase):
    def test_exits_long_in_dowtrend(self):
        self.assertTrue(
            should_signal_exit(
                position_side="LONG",
                regime="DOWNTREND",
                trend=1,
                scalp=1,
                rl_action=1,
                prob_up=0.70,
            )
        )

    def test_exits_when_signals_flip_negative(self):
        self.assertTrue(
            should_signal_exit(
                position_side="LONG",
                regime="RANGE",
                trend=-1,
                scalp=-1,
                rl_action=0,
                prob_up=0.48,
            )
        )

    def test_holds_when_long_signal_remains_constructive(self):
        self.assertFalse(
            should_signal_exit(
                position_side="LONG",
                regime="UPTREND",
                trend=1,
                scalp=1,
                rl_action=0,
                prob_up=0.62,
            )
        )


if __name__ == "__main__":
    unittest.main()
