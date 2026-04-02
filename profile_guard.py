from __future__ import annotations

import os

import pandas as pd


PROFILE_REPORT_PATH = "logs/btc_strategy_profiles.csv"
BEST_PROFILE_PATH = "logs/best_strategy_profile.json"


def load_profile_report(path: str = PROFILE_REPORT_PATH) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def best_profile_row(report: pd.DataFrame | None = None) -> dict | None:
    report = load_profile_report() if report is None else report
    if report is None or report.empty or "research_score" not in report.columns:
        return None
    sortable = report.copy()
    for column in ("wf_avg_return_pct", "bt_total_return_pct"):
        if column not in sortable.columns:
            sortable[column] = 0.0
    ordered = sortable.sort_values(["research_score", "wf_avg_return_pct", "bt_total_return_pct"], ascending=False)
    row = ordered.iloc[0].to_dict()
    return row


def live_profile_guard(profile_name: str, report: pd.DataFrame | None = None) -> tuple[bool, str]:
    row = best_profile_row(report)
    if row is None:
        return False, "profil_raporu_yok"
    best_name = str(row.get("profile", "")).strip()
    best_score = float(row.get("research_score", 0.0))
    if best_score <= 0:
        return False, "profil_skoru_pozitif_degil"
    if profile_name != best_name:
        return False, f"en_iyi_profil:{best_name}"
    return True, ""
