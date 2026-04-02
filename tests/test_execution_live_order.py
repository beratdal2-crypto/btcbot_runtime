import unittest
from decimal import Decimal
from unittest.mock import patch

from config import SETTINGS
from execution import _build_live_order_request


class ExecutionLiveOrderTests(unittest.TestCase):
    def test_buy_request_lifts_quote_to_min_notional_when_balance_allows(self):
        symbol_info = {
            "baseAsset": "ONT",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "MARKET_LOT_SIZE", "minQty": "1.00000000", "maxQty": "1000000.00000000", "stepSize": "1.00000000"},
                {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
            ],
        }
        original_buffer = SETTINGS.live_min_notional_buffer_pct
        original_max_quote = SETTINGS.max_live_quote_per_order
        original_min_quote = SETTINGS.min_quote_balance
        original_risk = SETTINGS.risk_per_trade
        try:
            SETTINGS.live_min_notional_buffer_pct = 0.05
            SETTINGS.max_live_quote_per_order = 1.0
            SETTINGS.min_quote_balance = 15.0
            SETTINGS.risk_per_trade = 0.04
            with patch("execution._get_symbol_info", return_value=symbol_info), patch(
                "execution._get_free_balance", return_value=Decimal("22.67460262")
            ):
                params, qty = _build_live_order_request(
                    "BUY",
                    current_price=0.05136,
                    tracked_qty=0.0,
                    symbol="ONTUSDT",
                    atr_pct=0.01,
                    coin_score=50.0,
                )
            self.assertEqual(params["side"], "BUY")
            self.assertGreaterEqual(qty * 0.05136, 5.0)
        finally:
            SETTINGS.live_min_notional_buffer_pct = original_buffer
            SETTINGS.max_live_quote_per_order = original_max_quote
            SETTINGS.min_quote_balance = original_min_quote
            SETTINGS.risk_per_trade = original_risk


if __name__ == "__main__":
    unittest.main()
