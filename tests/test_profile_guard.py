import unittest

import pandas as pd

from profile_guard import best_profile_row, live_profile_guard


class ProfileGuardTests(unittest.TestCase):
    def test_best_profile_picks_highest_research_score(self):
        report = pd.DataFrame(
            [
                {"profile": "balanced", "research_score": -0.2},
                {"profile": "trend", "research_score": 0.4},
                {"profile": "mean_reversion", "research_score": 0.1},
            ]
        )
        row = best_profile_row(report)
        self.assertEqual(row["profile"], "trend")

    def test_live_profile_guard_blocks_non_best_profile(self):
        report = pd.DataFrame(
            [
                {"profile": "trend", "research_score": 0.4},
                {"profile": "mean_reversion", "research_score": 0.1},
            ]
        )
        allowed, reason = live_profile_guard("mean_reversion", report)
        self.assertFalse(allowed)
        self.assertIn("en_iyi_profil:trend", reason)

    def test_live_profile_guard_blocks_nonpositive_best_score(self):
        report = pd.DataFrame(
            [
                {"profile": "trend", "research_score": 0.0},
            ]
        )
        allowed, reason = live_profile_guard("trend", report)
        self.assertFalse(allowed)
        self.assertEqual(reason, "profil_skoru_pozitif_degil")


if __name__ == "__main__":
    unittest.main()
