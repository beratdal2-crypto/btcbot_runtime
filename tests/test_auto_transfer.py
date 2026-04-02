import tempfile
import unittest
from pathlib import Path
from decimal import Decimal

from auto_transfer import _calculate_transfer_amount, load_auto_transfer_state, save_auto_transfer_state, AutoTransferState
from config import SETTINGS


class AutoTransferTests(unittest.TestCase):
    def test_calculate_transfer_amount_respects_multiple(self):
        amount = _calculate_transfer_amount(
            free_balance=Decimal("100"),
            network_info={
                "withdrawIntegerMultiple": "0.1",
                "withdrawMin": "1",
                "withdrawMax": "1000000",
            },
        )
        self.assertEqual(amount, Decimal("50.0"))

    def test_calculate_transfer_amount_rejects_below_minimum(self):
        with self.assertRaises(ValueError):
            _calculate_transfer_amount(
                free_balance=Decimal("100"),
                network_info={
                    "withdrawIntegerMultiple": "0.1",
                    "withdrawMin": "60",
                    "withdrawMax": "1000000",
                },
            )

    def test_state_roundtrip(self):
        original_state_path = SETTINGS.auto_transfer_state_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.auto_transfer_state_path = str(Path(tmpdir) / "auto_transfer_state.json")
                state = AutoTransferState(armed=False, last_transfer_at=123.0, last_transfer_amount=50.0, last_transfer_balance=100.0)
                save_auto_transfer_state(state)
                loaded = load_auto_transfer_state()
                self.assertFalse(loaded.armed)
                self.assertEqual(loaded.last_transfer_amount, 50.0)
                self.assertEqual(loaded.last_transfer_balance, 100.0)
        finally:
            SETTINGS.auto_transfer_state_path = original_state_path


if __name__ == "__main__":
    unittest.main()
