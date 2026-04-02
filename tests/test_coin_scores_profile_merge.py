import tempfile
import unittest
from pathlib import Path

import pandas as pd

from coin_scores import merge_profile_report_into_coin_scores
from config import SETTINGS


class CoinScoreProfileMergeTests(unittest.TestCase):
    def test_profile_report_creates_altcoin_score_row(self):
        original_coin_scores = SETTINGS.coin_scores_path
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                SETTINGS.coin_scores_path = str(Path(tmpdir) / "coin_scores.csv")
                report_path = Path(tmpdir) / "altcoin_profiles.csv"
                pd.DataFrame(
                    [
                        {
                            "symbol": "ETHUSDT",
                            "profile": "alt_5m_pullback",
                            "bt_trade_count": 1,
                            "bt_total_return_pct": -0.23,
                            "bt_max_drawdown_pct": 1.0,
                            "bt_profit_factor": 5.0,
                            "wf_fold_count": 2,
                            "wf_trade_count": 0,
                            "wf_avg_return_pct": 0.0,
                            "wf_avg_max_drawdown_pct": 0.0,
                            "wf_avg_win_rate_pct": 0.0,
                            "research_score": 0.58,
                        }
                    ]
                ).to_csv(report_path, index=False)

                merged = merge_profile_report_into_coin_scores(str(report_path))

                self.assertEqual(len(merged), 1)
                self.assertEqual(str(merged.iloc[0]["symbol"]), "ETHUSDT")
                self.assertIn("islem_az", str(merged.iloc[0]["reason"]))
        finally:
            SETTINGS.coin_scores_path = original_coin_scores


if __name__ == "__main__":
    unittest.main()
