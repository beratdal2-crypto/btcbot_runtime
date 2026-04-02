import unittest

import pandas as pd

from features import build_features


class OntFeatureScalingTests(unittest.TestCase):
    def test_ont_features_scale_volume_and_depth_proxies(self):
        rows = []
        price = 1.0
        for idx in range(80):
            price += 0.01
            rows.append(
                {
                    "open_time": f"2026-03-29T00:{idx:02d}:00Z",
                    "o": price - 0.01,
                    "h": price + 0.02,
                    "l": price - 0.02,
                    "c": price,
                    "v": 1000 + idx * 10,
                    "close_time": f"2026-03-29T00:{idx:02d}:59Z",
                    "quote_asset_volume": (1000 + idx * 10) * price,
                    "number_of_trades": 10 + idx,
                    "taker_buy_base": 400 + idx,
                    "taker_buy_quote": (400 + idx) * price,
                    "ignore": 0.0,
                }
            )
        df = pd.DataFrame(rows)
        micro = {"spread_bps": 8.0, "total_depth_notional": 5000.0, "imbalance": 0.12}

        btc = build_features(df, imbalance=0.12, microstructure=micro, symbol="BTCUSDT")
        ont = build_features(df, imbalance=0.12, microstructure=micro, symbol="ONTUSDT")

        self.assertGreater(
            float(ont["signed_volume_proxy"].iloc[-1]),
            float(btc["signed_volume_proxy"].iloc[-1]),
        )
        self.assertLess(
            float(ont["liquidity_stress"].iloc[-1]),
            float(btc["liquidity_stress"].iloc[-1]),
        )
        self.assertGreater(
            float(ont["micro_depth_log"].iloc[-1]),
            float(btc["micro_depth_log"].iloc[-1]),
        )


if __name__ == "__main__":
    unittest.main()
