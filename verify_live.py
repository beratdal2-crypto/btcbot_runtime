from __future__ import annotations
import sys

from config import SETTINGS
from data import build_client, get_last_price, _call_with_retries
from execution import preview_live_entry, validate_live_trading_setup


def _is_network_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "network is unreachable",
        "failed to establish a new connection",
        "max retries exceeded",
        "tunnel connection failed",
        "proxyerror",
        "connectionerror",
        "name resolution",
    ]
    return any(marker in text for marker in markers)


def _safe_call(fn, label: str):
    try:
        return _call_with_retries(fn)
    except Exception as exc:
        if _is_network_error(exc):
            print(f"[NETWORK_FAIL] {label}: {exc}")
            print("Ag/proxy/firewall kaynakli engel var. Detay icin: python network_diagnostics.py")
            raise SystemExit(2)
        raise


def main() -> None:
    print("Canli hazirlik kontrolu")
    print(f"symbol={SETTINGS.symbol}")
    print(f"paper_trade={SETTINGS.paper_trade}")
    print(f"live_trading={SETTINGS.live_trading}")
    print(f"live_test_orders={SETTINGS.live_test_orders}")
    print(f"binance_testnet={SETTINGS.testnet}")
    print(f"binance_tld={SETTINGS.binance_tld}")

    if SETTINGS.api_key in {"", "PUT_YOUR_KEY_HERE"} or SETTINGS.api_secret in {"", "PUT_YOUR_SECRET_HERE"}:
        raise ValueError(".env icine gecerli BINANCE_API_KEY ve BINANCE_API_SECRET yazilmali.")

    client = build_client()
    permissions = _safe_call(
        lambda: client.get_account_api_permissions(recvWindow=SETTINGS.recv_window)
    , "account_api_permissions")
    print("API permissions:")
    print(
        f"  enableReading={permissions.get('enableReading')} "
        f"enableSpotAndMarginTrading={permissions.get('enableSpotAndMarginTrading')} "
        f"ipRestrict={permissions.get('ipRestrict')}"
    )

    try:
        current_price = get_last_price()
    except Exception as exc:
        if _is_network_error(exc):
            print(f"[NETWORK_FAIL] get_last_price: {exc}")
            print("Ag/proxy/firewall kaynakli engel var. Detay icin: python network_diagnostics.py")
            raise SystemExit(2)
        raise
    print(f"current_price={current_price}")

    symbol_info = _safe_call(lambda: client.get_symbol_info(SETTINGS.symbol), "symbol_info")
    if not symbol_info:
        raise ValueError(f"Sembol bulunamadi: {SETTINGS.symbol}")

    base_asset = symbol_info["baseAsset"]
    quote_asset = symbol_info["quoteAsset"]
    base_balance = _safe_call(
        lambda: client.get_asset_balance(asset=base_asset, recvWindow=SETTINGS.recv_window)
    , "base_balance")
    quote_balance = _safe_call(
        lambda: client.get_asset_balance(asset=quote_asset, recvWindow=SETTINGS.recv_window)
    , "quote_balance")
    print(
        f"balances: {base_asset}={base_balance['free'] if base_balance else '0'} "
        f"{quote_asset}={quote_balance['free'] if quote_balance else '0'}"
    )

    filters = {item["filterType"]: item for item in symbol_info.get("filters", [])}
    lot_size = filters.get("LOT_SIZE") or {}
    market_lot_size = filters.get("MARKET_LOT_SIZE") or {}
    min_notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
    print("filters:")
    print(
        f"  lot_step={lot_size.get('stepSize')} market_step={market_lot_size.get('stepSize')} "
        f"min_notional={min_notional.get('minNotional')}"
    )

    if SETTINGS.live_trading and not SETTINGS.paper_trade:
        validate_live_trading_setup(SETTINGS.symbol)
        params, qty = preview_live_entry("BUY", current_price)
        print(f"preview_buy_qty={qty}")
        print(f"preview_order={params}")
        if SETTINGS.live_test_orders:
            _safe_call(lambda: client.create_test_order(**params), "create_test_order")
            print("Binance test order basarili. Gercek emir olusmadi.")
        else:
            print("UYARI: LIVE_TEST_ORDERS=false. Bu script test order gondermedi.")
    else:
        print("Canli emir modu kapali. Sadece hesap ve sembol kontrolu yapildi.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] verify_live basarisiz: {exc}")
        sys.exit(1)
