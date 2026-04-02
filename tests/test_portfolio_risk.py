import unittest

import pandas as pd

from portfolio_risk import evaluate_portfolio_risk


class PortfolioRiskTests(unittest.TestCase):
    def test_blocks_after_consecutive_losses(self):
        trades = pd.DataFrame(
            [
                {"time": pd.Timestamp.utcnow().isoformat(), "action": "CLOSE_LONG", "profit_pct": -0.01},
                {"time": pd.Timestamp.utcnow().isoformat(), "action": "CLOSE_LONG", "profit_pct": -0.02},
                {"time": pd.Timestamp.utcnow().isoformat(), "action": "CLOSE_LONG", "profit_pct": -0.03},
            ]
        )
        result = evaluate_portfolio_risk(trades, equity=None)
        self.assertFalse(result.allow_entries)

    def test_temkinli_mode_after_drawdown(self):
        equity = pd.DataFrame(
            [
                {"time": pd.Timestamp.utcnow().isoformat(), "equity_usdt": 1000},
                {"time": pd.Timestamp.utcnow().isoformat(), "equity_usdt": 970},
            ]
        )
        result = evaluate_portfolio_risk(pd.DataFrame(), equity)
        self.assertTrue(result.allow_entries)
        self.assertLess(result.size_multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
