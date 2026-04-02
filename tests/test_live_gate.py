import unittest
import json
import os
import tempfile

import live_gate
from config import SETTINGS
from live_gate import (
    evaluate_live_conditions_from_inputs,
    load_backup_altcoin_candidates,
    load_best_altcoin_candidate,
    load_best_altcoin_candidate_for_symbol,
)


class LiveGateTests(unittest.TestCase):
    def test_all_conditions_pass(self):
        result = evaluate_live_conditions_from_inputs(
            symbol="BTCUSDT",
            strategy_name="balanced",
            live_guard_ok=True,
            live_guard_reason="",
            profile_guard_ok=True,
            profile_guard_reason="",
            profile_row={
                "bt_trade_count": 6,
                "bt_total_return_pct": 1.0,
                "bt_profit_factor": 1.2,
                "wf_trade_count": 3,
                "wf_avg_return_pct": 0.1,
            },
            quick_report={
                "edge_confirmed": True,
                "backtest": {"total_return_pct": 0.3, "max_drawdown_pct": 1.5},
            },
            quote_balance=25.0,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["strict_ok"])
        self.assertFalse(result["candidate_ok"])

    def test_negative_backtest_blocks_live(self):
        result = evaluate_live_conditions_from_inputs(
            symbol="ETHUSDT",
            strategy_name="alt_5m_pullback",
            live_guard_ok=True,
            live_guard_reason="",
            profile_guard_ok=True,
            profile_guard_reason="",
            profile_row={
                "bt_trade_count": 8,
                "bt_total_return_pct": -0.2,
                "bt_profit_factor": 1.5,
                "bt_max_drawdown_pct": 1.0,
                "wf_trade_count": 4,
                "wf_avg_return_pct": 0.1,
            },
            quick_report=None,
            quote_balance=25.0,
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["conditions"]["backtest"]["ok"])

    def test_zero_walkforward_trades_blocks_live(self):
        result = evaluate_live_conditions_from_inputs(
            symbol="ETHUSDT",
            strategy_name="alt_5m_pullback",
            live_guard_ok=True,
            live_guard_reason="",
            profile_guard_ok=True,
            profile_guard_reason="",
            profile_row={
                "bt_trade_count": 8,
                "bt_total_return_pct": 0.4,
                "bt_profit_factor": 1.5,
                "bt_max_drawdown_pct": 1.0,
                "wf_trade_count": 0,
                "wf_avg_return_pct": 0.0,
            },
            quick_report=None,
            quote_balance=25.0,
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["conditions"]["walkforward"]["ok"])

    def test_near_breakeven_altcoin_becomes_candidate_not_live(self):
        result = evaluate_live_conditions_from_inputs(
            symbol="ONTUSDT",
            strategy_name="ont_15m_breakout",
            live_guard_ok=False,
            live_guard_reason="islem_az,bt_getiri_zayif",
            profile_guard_ok=True,
            profile_guard_reason="",
            profile_row={
                "bt_trade_count": 2,
                "bt_total_return_pct": -0.39,
                "bt_profit_factor": 0.56,
                "bt_max_drawdown_pct": 1.28,
                "wf_trade_count": 0,
                "wf_avg_return_pct": 0.0,
            },
            quick_report=None,
            quote_balance=25.0,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["candidate_ok"])
        self.assertEqual(result["conditions"]["guards"]["status"], "warn")
        self.assertEqual(result["conditions"]["backtest"]["status"], "warn")

    def test_hard_guard_reason_blocks_candidate_too(self):
        result = evaluate_live_conditions_from_inputs(
            symbol="ONTUSDT",
            strategy_name="ont_15m_breakout",
            live_guard_ok=False,
            live_guard_reason="hard_block",
            profile_guard_ok=True,
            profile_guard_reason="",
            profile_row={
                "bt_trade_count": 2,
                "bt_total_return_pct": -0.39,
                "bt_profit_factor": 0.56,
                "bt_max_drawdown_pct": 1.28,
                "wf_trade_count": 0,
                "wf_avg_return_pct": 0.0,
            },
            quick_report=None,
            quote_balance=25.0,
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["candidate_ok"])
        self.assertEqual(result["conditions"]["guards"]["status"], "fail")

    def test_best_altcoin_candidate_loader_returns_dict_or_none(self):
        result = load_best_altcoin_candidate()
        self.assertTrue(result is None or isinstance(result, dict))

    def test_best_altcoin_candidate_loader_ignores_stale_disallowed_symbol(self):
        original_best_path = live_gate.BEST_ALTCOIN_PROFILE_PATH
        original_alt_report_path = live_gate.ALT_PROFILE_REPORT_PATH
        original_alt_csv = SETTINGS.alt_research_symbols_csv
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                best_path = os.path.join(tmpdir, "best_altcoin_strategy.json")
                report_path = os.path.join(tmpdir, "altcoin_strategy_profiles.csv")
                with open(best_path, "w") as f:
                    json.dump({"symbol": "STGUSDT", "profile": "alt_5m_pullback"}, f)
                with open(report_path, "w") as f:
                    f.write(
                        "symbol,profile,research_score,bt_profit_factor,bt_total_return_pct\n"
                        "XRPUSDT,alt_5m_pullback,0.1,0.8,-0.3\n"
                    )
                live_gate.BEST_ALTCOIN_PROFILE_PATH = best_path
                live_gate.ALT_PROFILE_REPORT_PATH = report_path
                SETTINGS.alt_research_symbols_csv = "XRPUSDT,ONTUSDT"

                result = load_best_altcoin_candidate()
                self.assertIsInstance(result, dict)
                self.assertEqual(str(result.get("symbol", "")).upper(), "XRPUSDT")
        finally:
            live_gate.BEST_ALTCOIN_PROFILE_PATH = original_best_path
            live_gate.ALT_PROFILE_REPORT_PATH = original_alt_report_path
            SETTINGS.alt_research_symbols_csv = original_alt_csv

    def test_backup_altcoin_candidates_loader_returns_list(self):
        result = load_backup_altcoin_candidates(primary_symbol="ONTUSDT", limit=2)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertNotEqual(str(item.get("symbol", "")).upper(), "STGUSDT")

    def test_best_altcoin_candidate_for_symbol_returns_symbol_specific_row(self):
        original_alt_report_path = live_gate.ALT_PROFILE_REPORT_PATH
        original_alt_csv = SETTINGS.alt_research_symbols_csv
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                report_path = os.path.join(tmpdir, "altcoin_strategy_profiles.csv")
                with open(report_path, "w") as f:
                    f.write(
                        "symbol,profile,research_score,bt_profit_factor,bt_total_return_pct\n"
                        "ONTUSDT,ont_15m_breakout,-0.33,0.56,-0.39\n"
                        "XRPUSDT,alt_5m_pullback,0.08,0.74,-0.38\n"
                    )
                live_gate.ALT_PROFILE_REPORT_PATH = report_path
                SETTINGS.alt_research_symbols_csv = "XRPUSDT,ONTUSDT"

                result = load_best_altcoin_candidate_for_symbol("ONTUSDT")
                self.assertIsInstance(result, dict)
                self.assertEqual(str(result.get("symbol", "")).upper(), "ONTUSDT")
                self.assertEqual(str(result.get("profile", "")), "ont_15m_breakout")
        finally:
            live_gate.ALT_PROFILE_REPORT_PATH = original_alt_report_path
            SETTINGS.alt_research_symbols_csv = original_alt_csv


if __name__ == "__main__":
    unittest.main()
