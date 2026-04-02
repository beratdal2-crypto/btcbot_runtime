import os
import tempfile
import unittest

from alerts import load_recent_alerts, log_alert
from config import SETTINGS


class AlertTests(unittest.TestCase):
    def test_log_alert_creates_csv(self):
        original_path = SETTINGS.alerts_log_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                log_alert("warn", "api", "deneme", details="x")
                df = load_recent_alerts()
                self.assertIsNotNone(df)
                self.assertEqual(df.iloc[-1]["category"], "api")
        finally:
            SETTINGS.alerts_log_path = original_path


if __name__ == "__main__":
    unittest.main()
