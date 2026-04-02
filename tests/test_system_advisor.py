import unittest

import pandas as pd

from system_advisor import build_system_advice


class SystemAdvisorTests(unittest.TestCase):
    def test_security_finding_forces_stop(self):
        advice = build_system_advice(
            backtest_summary=pd.DataFrame([{"total_return_pct": 1.0, "max_drawdown_pct": 2.0}]),
            walkforward=pd.DataFrame([{"total_return_pct": 0.2}]),
            coin_scores=pd.DataFrame([{"symbol": "BTCUSDT", "eligible": True, "hard_block": False}]),
            security_audit={"finding_count": 1},
            live_readiness={"api_keys_present": True},
        )
        self.assertEqual(advice["status"], "STOP")

    def test_negative_research_results_trigger_caution(self):
        advice = build_system_advice(
            backtest_summary=pd.DataFrame([{"total_return_pct": -0.4, "max_drawdown_pct": 10.5}]),
            walkforward=pd.DataFrame([{"total_return_pct": -0.2}, {"total_return_pct": 0.1}]),
            coin_scores=pd.DataFrame([{"symbol": "BTCUSDT", "eligible": True, "hard_block": False}]),
            security_audit={"finding_count": 0},
            live_readiness={"api_keys_present": True},
        )
        self.assertIn(advice["status"], {"CAUTION", "STOP"})
