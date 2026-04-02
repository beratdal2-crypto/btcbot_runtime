import os
import tempfile
import unittest

from config import SETTINGS
from shadow_mode import ShadowState, load_shadow_state, process_shadow_position
from execution import Position


class ShadowModeTests(unittest.TestCase):
    def test_shadow_buy_and_close_cycle(self):
        original_state = SETTINGS.shadow_state_path
        original_log = SETTINGS.shadow_trade_log_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.shadow_state_path = os.path.join(tmpdir, "shadow.json")
                SETTINGS.shadow_trade_log_path = os.path.join(tmpdir, "shadow.csv")
                state = load_shadow_state()
                state = process_shadow_position(state, "BTCUSDT", 100.0, "BUY", False)
                self.assertTrue(state.position.is_open)
                state.position = Position(symbol="BTCUSDT", side="LONG", entry_price=100.0, qty=1.0, peak_price=101.0, is_open=True)
                state = process_shadow_position(state, "BTCUSDT", 100.1, "HOLD", True)
                self.assertFalse(state.position.is_open)
                self.assertTrue(os.path.exists(SETTINGS.shadow_trade_log_path))
        finally:
            SETTINGS.shadow_state_path = original_state
            SETTINGS.shadow_trade_log_path = original_log


if __name__ == "__main__":
    unittest.main()
