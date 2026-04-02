from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from binance import ThreadedWebsocketManager

from alerts import log_alert
from config import SETTINGS


def _load_cache() -> dict[str, dict]:
    if not os.path.exists(SETTINGS.websocket_cache_path):
        return {}
    try:
        with open(SETTINGS.websocket_cache_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_cache(cache: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(SETTINGS.websocket_cache_path), exist_ok=True)
    with open(SETTINGS.websocket_cache_path, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _symbol_callback(message: dict) -> None:
    if not isinstance(message, dict):
        return
    symbol = str(message.get("s", "")).upper()
    if not symbol:
        return
    cache = _load_cache()
    cache[symbol] = {
        "event_time": datetime.now(timezone.utc).isoformat(),
        "price": float(message.get("c", 0.0) or 0.0),
        "bid": float(message.get("b", 0.0) or 0.0),
        "ask": float(message.get("a", 0.0) or 0.0),
        "source": "websocket",
    }
    _save_cache(cache)


def run_websocket_collector() -> None:
    twm = ThreadedWebsocketManager(api_key=SETTINGS.api_key or None, api_secret=SETTINGS.api_secret or None)
    twm.start()
    symbols = [symbol.lower() for symbol in SETTINGS.trading_symbols()]
    for symbol in symbols:
        twm.start_symbol_ticker_socket(callback=_symbol_callback, symbol=symbol)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log_alert("ERROR", "websocket", "Websocket collector durdu", details=str(exc))
        raise
    finally:
        twm.stop()


if __name__ == "__main__":
    run_websocket_collector()
