from __future__ import annotations

import json
import os

from config import SETTINGS
from data import archive_latest_klines


def main() -> None:
    os.makedirs("logs", exist_ok=True)
    target_rows = max(SETTINGS.archive_backfill_bars, SETTINGS.long_validation_lookback_limit)
    last_rows = 0
    attempts = 0
    df = archive_latest_klines(symbol="BTCUSDT", interval="1m", backfill_bars=target_rows)
    while len(df) > last_rows and len(df) < target_rows and attempts < 5:
        last_rows = len(df)
        attempts += 1
        df = archive_latest_klines(symbol="BTCUSDT", interval="1m", backfill_bars=target_rows)

    payload = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "target_rows": target_rows,
        "archive_rows": int(len(df)),
        "attempts": attempts,
        "complete": bool(len(df) >= target_rows),
    }
    with open("logs/archive_depth_report.json", "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(payload)


if __name__ == "__main__":
    main()
