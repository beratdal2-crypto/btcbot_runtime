import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from health_report import build_system_health_report


class HealthReportTests(unittest.TestCase):
    def test_build_system_health_report_writes_json(self):
        original_heartbeat = SETTINGS.heartbeat_log_path
        original_alerts = SETTINGS.alerts_log_path
        original_out = SETTINGS.system_health_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.heartbeat_log_path = os.path.join(tmpdir, "heartbeat.csv")
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                SETTINGS.system_health_path = os.path.join(tmpdir, "system_health.json")
                now = pd.Timestamp.utcnow()
                pd.DataFrame([{"time": now.isoformat(), "price": 1.0}]).to_csv(SETTINGS.heartbeat_log_path, index=False)
                pd.DataFrame([{"time": now.isoformat(), "level": "WARN", "category": "api"}]).to_csv(SETTINGS.alerts_log_path, index=False)

                report = build_system_health_report()

                self.assertTrue(os.path.exists(SETTINGS.system_health_path))
                self.assertIn("dashboard_ok", report)
        finally:
            SETTINGS.heartbeat_log_path = original_heartbeat
            SETTINGS.alerts_log_path = original_alerts
            SETTINGS.system_health_path = original_out
