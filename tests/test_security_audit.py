import os
import tempfile
import unittest

from config import SETTINGS
from security_audit import run_security_audit


class SecurityAuditTests(unittest.TestCase):
    def test_security_audit_finds_exposed_env_values(self):
        original_out = SETTINGS.security_audit_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.security_audit_path = os.path.join(tmpdir, "audit.json")
                env_path = os.path.join(tmpdir, ".env")
                with open(env_path, "w") as f:
                    f.write("BINANCE_API_KEY=ABCDEFGHIJKLMNOPQRSTUVWX123456\n")
                    f.write("BINANCE_API_SECRET=ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n")

                report = run_security_audit(root=tmpdir)

                self.assertGreaterEqual(report["finding_count"], 2)
                self.assertTrue(os.path.exists(SETTINGS.security_audit_path))
        finally:
            SETTINGS.security_audit_path = original_out
