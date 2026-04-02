import json
import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from sqlite_store import load_table, sync_sqlite_store


class SqliteStoreTests(unittest.TestCase):
    def test_sync_sqlite_store_ingests_logs(self):
        original_values = {
            "trade_log_path": SETTINGS.trade_log_path,
            "alerts_log_path": SETTINGS.alerts_log_path,
            "equity_log_path": SETTINGS.equity_log_path,
            "order_audit_log_path": SETTINGS.order_audit_log_path,
            "notification_log_path": SETTINGS.notification_log_path,
            "shadow_trade_log_path": SETTINGS.shadow_trade_log_path,
            "sqlite_db_path": SETTINGS.sqlite_db_path,
            "websocket_cache_path": SETTINGS.websocket_cache_path,
        }
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.trade_log_path = os.path.join(tmpdir, "trades.csv")
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                SETTINGS.equity_log_path = os.path.join(tmpdir, "equity.csv")
                SETTINGS.order_audit_log_path = os.path.join(tmpdir, "order_audit.csv")
                SETTINGS.notification_log_path = os.path.join(tmpdir, "notifications.csv")
                SETTINGS.shadow_trade_log_path = os.path.join(tmpdir, "shadow.csv")
                SETTINGS.sqlite_db_path = os.path.join(tmpdir, "btcbot.sqlite3")
                SETTINGS.websocket_cache_path = os.path.join(tmpdir, "websocket.json")

                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "symbol": "BTCUSDT", "action": "BUY", "price": 1, "qty": 1, "regime": "UPTREND", "prob_up": 0.7, "imbalance": 0.5, "profit_pct": 0.0}]).to_csv(SETTINGS.trade_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "level": "WARN", "category": "api", "symbol": "BTCUSDT", "message": "x", "details": "y"}]).to_csv(SETTINGS.alerts_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "equity_usdt": 100.0, "daily_pnl_pct": 0.1, "position_symbol": "BTCUSDT", "position_open": True}]).to_csv(SETTINGS.equity_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "symbol": "BTCUSDT", "action": "BUY", "order_id": "1", "status": "FILLED", "requested_qty": 1, "executed_qty": 1, "filled_ratio": 1, "fill_count": 1, "avg_price": 1, "slippage_bps": 0, "estimated_fee_quote": 0, "dry_run": False, "details": ""}]).to_csv(SETTINGS.order_audit_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "channel": "log", "level": "INFO", "category": "trade", "title": "t", "message": "m", "delivered": False, "details": ""}]).to_csv(SETTINGS.notification_log_path, index=False)
                pd.DataFrame([{"time": "2026-01-01T00:00:00Z", "symbol": "BTCUSDT", "action": "SHADOW_CLOSE", "price": 1, "qty": 1, "profit_pct": 0.1, "reason": "tp"}]).to_csv(SETTINGS.shadow_trade_log_path, index=False)
                with open(SETTINGS.websocket_cache_path, "w") as f:
                    json.dump({"BTCUSDT": {"event_time": "2026-01-01T00:00:00Z", "price": 1, "bid": 0.99, "ask": 1.01, "source": "websocket"}}, f)

                result = sync_sqlite_store()

                self.assertGreaterEqual(result["trades"], 1)
                self.assertEqual(len(load_table("trades")), 1)
                self.assertEqual(len(load_table("websocket_ticks")), 1)
        finally:
            for key, value in original_values.items():
                setattr(SETTINGS, key, value)
