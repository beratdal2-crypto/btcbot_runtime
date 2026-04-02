import unittest
from decimal import Decimal
import os
import tempfile

from config import SETTINGS
from execution import _reconstruct_open_lots, load_runtime_state, save_runtime_state, Position


class ReconciliationTests(unittest.TestCase):
    def test_runtime_state_roundtrip(self):
        original_path = SETTINGS.runtime_state_path
        with tempfile.TemporaryDirectory() as tmpdir:
            SETTINGS.runtime_state_path = os.path.join(tmpdir, "runtime_state.json")
            position = Position(symbol="ETHUSDT", side="LONG", entry_price=123.45, qty=0.02, is_open=True)
            save_runtime_state(position, daily_pnl_pct=0.01, last_event="entry:BUY:LIVE")

            state = load_runtime_state()

            self.assertTrue(state.loaded_from_disk)
            self.assertTrue(state.position.is_open)
            self.assertEqual(state.position.symbol, "ETHUSDT")
            self.assertEqual(state.position.side, "LONG")
            self.assertAlmostEqual(state.position.entry_price, 123.45)
            self.assertAlmostEqual(state.position.qty, 0.02)
            self.assertAlmostEqual(state.daily_pnl_pct, 0.01)
            self.assertEqual(state.last_event, "entry:BUY:LIVE")
        SETTINGS.runtime_state_path = original_path

    def test_reconstruct_open_lots_keeps_remaining_buys(self):
        trades = [
            {"id": 1, "time": 1, "price": "100", "qty": "0.01", "isBuyer": True},
            {"id": 2, "time": 2, "price": "110", "qty": "0.02", "isBuyer": True},
            {"id": 3, "time": 3, "price": "120", "qty": "0.015", "isBuyer": False},
        ]

        lots = _reconstruct_open_lots(trades)

        self.assertEqual(lots, [(Decimal("0.015"), Decimal("110"))])

    def test_reconstruct_open_lots_clears_when_sells_exceed_known_buys(self):
        trades = [
            {"id": 1, "time": 1, "price": "100", "qty": "0.01", "isBuyer": True},
            {"id": 2, "time": 2, "price": "120", "qty": "0.02", "isBuyer": False},
        ]

        lots = _reconstruct_open_lots(trades)

        self.assertEqual(lots, [])


if __name__ == "__main__":
    unittest.main()
