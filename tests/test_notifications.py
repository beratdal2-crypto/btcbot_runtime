import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from notifications import notify_event


class NotificationTests(unittest.TestCase):
    def test_notify_event_logs_even_when_channel_disabled(self):
        original_enabled = SETTINGS.notification_enabled
        original_path = SETTINGS.notification_log_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.notification_enabled = False
                SETTINGS.notification_log_path = os.path.join(tmpdir, "notifications.csv")
                notify_event("INFO", "trade", "Baslik", "Mesaj")
                df = pd.read_csv(SETTINGS.notification_log_path)
                self.assertEqual(df.iloc[-1]["category"], "trade")
        finally:
            SETTINGS.notification_enabled = original_enabled
            SETTINGS.notification_log_path = original_path


if __name__ == "__main__":
    unittest.main()
