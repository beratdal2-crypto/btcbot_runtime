import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
import btcbot_watchdog as watchdog


class WatchdogTests(unittest.TestCase):
    def test_should_restart_when_heartbeat_is_stale(self):
        original_heartbeat = SETTINGS.heartbeat_log_path
        original_timeout = SETTINGS.watchdog_heartbeat_timeout_seconds
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.heartbeat_log_path = os.path.join(tmpdir, "heartbeat.csv")
                SETTINGS.watchdog_heartbeat_timeout_seconds = 10
                stale_time = pd.Timestamp.utcnow() - pd.Timedelta(seconds=60)
                pd.DataFrame([{"time": stale_time.isoformat(), "price": 1}]).to_csv(SETTINGS.heartbeat_log_path, index=False)

                should_restart, reason = watchdog.should_restart_runner()
                self.assertTrue(should_restart)
                self.assertIn("heartbeat_gecikmesi", reason)
        finally:
            SETTINGS.heartbeat_log_path = original_heartbeat
            SETTINGS.watchdog_heartbeat_timeout_seconds = original_timeout


if __name__ == "__main__":
    unittest.main()
