import os
import tempfile
import time
import unittest

from coin_runtime import filter_symbols_by_cooldown, record_trade_outcome
from config import SETTINGS


class CoinRuntimeTests(unittest.TestCase):
    def test_symbol_enters_cooldown_after_consecutive_losses(self):
        original_path = SETTINGS.coin_cooldown_state_path
        original_enabled = SETTINGS.coin_cooldown_enabled
        original_losses = SETTINGS.coin_max_consecutive_losses
        original_minutes = SETTINGS.coin_cooldown_minutes
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.coin_cooldown_state_path = os.path.join(tmpdir, "cooldowns.json")
                SETTINGS.coin_cooldown_enabled = True
                SETTINGS.coin_max_consecutive_losses = 2
                SETTINGS.coin_cooldown_minutes = 60

                now = time.time()
                record_trade_outcome("BTCUSDT", -0.01, event_time=now)
                record_trade_outcome("BTCUSDT", -0.02, event_time=now + 1)

                eligible, state = filter_symbols_by_cooldown(("BTCUSDT", "ETHUSDT"), now=now + 2)
                self.assertEqual(eligible, ("ETHUSDT",))
                self.assertTrue(bool(state.loc[state["symbol"] == "BTCUSDT", "cooldown_active"].iloc[0]))
        finally:
            SETTINGS.coin_cooldown_state_path = original_path
            SETTINGS.coin_cooldown_enabled = original_enabled
            SETTINGS.coin_max_consecutive_losses = original_losses
            SETTINGS.coin_cooldown_minutes = original_minutes


if __name__ == "__main__":
    unittest.main()
