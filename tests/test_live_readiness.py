import os
import tempfile
import unittest

from config import SETTINGS
from live_readiness import build_live_readiness_report


class LiveReadinessTests(unittest.TestCase):
    def test_build_live_readiness_report_writes_json(self):
        original_out = SETTINGS.live_readiness_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.live_readiness_path = os.path.join(tmpdir, "live_readiness.json")
                report = build_live_readiness_report()
                self.assertTrue(os.path.exists(SETTINGS.live_readiness_path))
                self.assertIn("api_keys_present", report)
        finally:
            SETTINGS.live_readiness_path = original_out
