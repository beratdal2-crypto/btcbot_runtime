import os
import tempfile
import unittest

import pandas as pd

from config import SETTINGS
from kill_switch import evaluate_kill_switch, save_kill_switch_state


class KillSwitchTests(unittest.TestCase):
    def test_activates_on_repeated_errors(self):
        original_alerts = SETTINGS.alerts_log_path
        original_self = SETTINGS.self_protection_state_path
        original_threshold = SETTINGS.kill_switch_error_threshold
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                SETTINGS.self_protection_state_path = os.path.join(tmpdir, "self.json")
                SETTINGS.kill_switch_error_threshold = 2
                now = pd.Timestamp.utcnow()
                pd.DataFrame(
                    [
                        {"time": now.isoformat(), "level": "ERROR", "category": "api"},
                        {"time": now.isoformat(), "level": "ERROR", "category": "main_loop"},
                    ]
                ).to_csv(SETTINGS.alerts_log_path, index=False)
                active, reason = evaluate_kill_switch()
                self.assertTrue(active)
                self.assertIn("threshold", reason)
        finally:
            SETTINGS.alerts_log_path = original_alerts
            SETTINGS.self_protection_state_path = original_self
            SETTINGS.kill_switch_error_threshold = original_threshold

    def test_save_kill_switch_state_writes_json(self):
        original_path = SETTINGS.kill_switch_state_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.kill_switch_state_path = os.path.join(tmpdir, "kill.json")
                save_kill_switch_state(True, "test")
                self.assertTrue(os.path.exists(SETTINGS.kill_switch_state_path))
        finally:
            SETTINGS.kill_switch_state_path = original_path

    def test_warn_level_api_noise_does_not_trigger_kill_switch(self):
        original_alerts = SETTINGS.alerts_log_path
        original_self = SETTINGS.self_protection_state_path
        original_threshold = SETTINGS.kill_switch_error_threshold
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.alerts_log_path = os.path.join(tmpdir, "alerts.csv")
                SETTINGS.self_protection_state_path = os.path.join(tmpdir, "self.json")
                SETTINGS.kill_switch_error_threshold = 2
                now = pd.Timestamp.utcnow()
                pd.DataFrame(
                    [
                        {"time": now.isoformat(), "level": "WARN", "category": "api"},
                        {"time": now.isoformat(), "level": "WARN", "category": "api"},
                        {"time": now.isoformat(), "level": "WARN", "category": "watchdog"},
                    ]
                ).to_csv(SETTINGS.alerts_log_path, index=False)
                active, reason = evaluate_kill_switch()
                self.assertFalse(active)
                self.assertEqual(reason, "ok")
        finally:
            SETTINGS.alerts_log_path = original_alerts
            SETTINGS.self_protection_state_path = original_self
            SETTINGS.kill_switch_error_threshold = original_threshold


if __name__ == "__main__":
    unittest.main()
