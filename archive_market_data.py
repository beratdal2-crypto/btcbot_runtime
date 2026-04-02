from config import SETTINGS
from data import archive_latest_klines, get_market_data_archive_path


def run_archive() -> None:
    for symbol in SETTINGS.trading_symbols():
        try:
            df = archive_latest_klines(
                symbol=symbol,
                interval=SETTINGS.interval,
                backfill_bars=SETTINGS.archive_backfill_bars,
                force_refresh=False,
            )
        except Exception as exc:
            print(f"[{symbol}] Archive skipped: {exc}")
            continue

        print(f"[{symbol}] Archive rows: {len(df)}")
        print(f"[{symbol}] Archive path: {get_market_data_archive_path(symbol)}")
        if not df.empty:
            print(f"[{symbol}] First open_time: {df['open_time'].iloc[0]}")
            print(f"[{symbol}] Last open_time: {df['open_time'].iloc[-1]}")


if __name__ == "__main__":
    run_archive()
