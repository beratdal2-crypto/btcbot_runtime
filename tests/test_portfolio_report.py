import json
import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from portfolio_report import build_portfolio_report


class PortfolioReportTests(unittest.TestCase):
    def test_build_portfolio_report_outputs_files(self):
        original_trade = SETTINGS.trade_log_path
        original_equity = SETTINGS.equity_log_path
        original_audit = SETTINGS.order_audit_log_path
        original_report = SETTINGS.portfolio_report_path
        original_periods = SETTINGS.portfolio_periods_path
        original_contrib = SETTINGS.coin_contribution_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.trade_log_path = os.path.join(tmpdir, "trades.csv")
                SETTINGS.equity_log_path = os.path.join(tmpdir, "equity.csv")
                SETTINGS.order_audit_log_path = os.path.join(tmpdir, "audit.csv")
                SETTINGS.portfolio_report_path = os.path.join(tmpdir, "report.json")
                SETTINGS.portfolio_periods_path = os.path.join(tmpdir, "periods.csv")
                SETTINGS.coin_contribution_path = os.path.join(tmpdir, "contrib.csv")

                now = pd.Timestamp.utcnow()
                pd.DataFrame(
                    [
                        {"time": now.isoformat(), "symbol": "BTCUSDT", "action": "CLOSE_LONG", "profit_pct": 0.01},
                        {"time": now.isoformat(), "symbol": "ETHUSDT", "action": "CLOSE_LONG", "profit_pct": -0.005},
                    ]
                ).to_csv(SETTINGS.trade_log_path, index=False)
                pd.DataFrame(
                    [
                        {"time": (now - pd.Timedelta(days=1)).isoformat(), "equity_usdt": 100.0},
                        {"time": now.isoformat(), "equity_usdt": 102.0},
                    ]
                ).to_csv(SETTINGS.equity_log_path, index=False)
                pd.DataFrame([{"slippage_bps": 5.0, "estimated_fee_quote": 0.12}]).to_csv(SETTINGS.order_audit_log_path, index=False)

                report = build_portfolio_report()

                self.assertTrue(os.path.exists(SETTINGS.portfolio_report_path))
                self.assertTrue(os.path.exists(SETTINGS.portfolio_periods_path))
                self.assertTrue(os.path.exists(SETTINGS.coin_contribution_path))
                self.assertGreater(report["current_equity_usdt"], 0.0)
                with open(SETTINGS.portfolio_report_path, "r") as f:
                    payload = json.load(f)
                self.assertIn("avg_slippage_bps", payload)
        finally:
            SETTINGS.trade_log_path = original_trade
            SETTINGS.equity_log_path = original_equity
            SETTINGS.order_audit_log_path = original_audit
            SETTINGS.portfolio_report_path = original_report
            SETTINGS.portfolio_periods_path = original_periods
            SETTINGS.coin_contribution_path = original_contrib


if __name__ == "__main__":
    unittest.main()
