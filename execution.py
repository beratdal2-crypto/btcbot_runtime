from __future__ import annotations
import csv
import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_DOWN

from alerts import log_alert
from data import _call_client_method, get_klines_df, get_last_price, get_market_microstructure, get_symbol_info_cached
from config import SETTINGS
from no_trade_zone import detect_no_trade_zone
from position_sizing import compute_position_fraction


@dataclass
class Position:
    symbol: str = ""
    side: str | None = None
    entry_price: float = 0.0
    qty: float = 0.0
    peak_price: float = 0.0
    is_open: bool = False


@dataclass
class OrderResult:
    success: bool
    action: str
    qty: float = 0.0
    price: float = 0.0
    order_id: int | None = None
    dry_run: bool = False
    details: str = ""
    requested_qty: float = 0.0
    executed_qty: float = 0.0
    filled_ratio: float = 0.0
    fill_count: int = 0
    status: str = ""
    slippage_bps: float = 0.0
    estimated_fee_quote: float = 0.0


@dataclass
class ReconciliationResult:
    position: Position
    changed: bool = False
    details: str = ""
    external_change: bool = False


@dataclass
class RuntimeState:
    position: Position
    daily_pnl_pct: float = 0.0
    current_equity_usdt: float = 0.0
    last_event: str = ""
    updated_at: str = ""
    loaded_from_disk: bool = False


def _is_live_mode() -> bool:
    return SETTINGS.live_trading and not SETTINGS.paper_trade


def _to_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step


def _filter_map(symbol_info: dict) -> dict[str, dict]:
    return {item["filterType"]: item for item in symbol_info.get("filters", [])}


def _get_symbol_info(symbol: str) -> dict:
    info = get_symbol_info_cached(symbol)
    if not info:
        raise ValueError(f"Sembol bilgisi bulunamadi: {symbol}")
    return info


def _get_assets(symbol_info: dict) -> tuple[str, str]:
    return symbol_info["baseAsset"], symbol_info["quoteAsset"]


def _min_notional(filters: dict[str, dict]) -> Decimal:
    if "NOTIONAL" in filters:
        return _to_decimal(filters["NOTIONAL"]["minNotional"])
    if "MIN_NOTIONAL" in filters:
        return _to_decimal(filters["MIN_NOTIONAL"]["minNotional"])
    return Decimal("0")


def _market_step_and_min_qty(filters: dict[str, dict]) -> tuple[Decimal, Decimal, Decimal]:
    market_lot = filters.get("MARKET_LOT_SIZE")
    lot_size = filters.get("LOT_SIZE")
    if not market_lot and not lot_size:
        raise ValueError("MARKET_LOT_SIZE / LOT_SIZE filtresi bulunamadi")
    market_lot = market_lot or lot_size
    lot_size = lot_size or market_lot
    min_qty = _to_decimal(market_lot["minQty"])
    max_qty = _to_decimal(market_lot["maxQty"])
    step = _to_decimal(market_lot["stepSize"])
    if step <= 0:
        step = _to_decimal(lot_size["stepSize"])
    return min_qty, max_qty, step


def _min_notional_quote_target(min_notional: Decimal) -> Decimal:
    buffer_multiplier = Decimal("1") + _to_decimal(SETTINGS.live_min_notional_buffer_pct)
    return min_notional * buffer_multiplier


def _get_balance_snapshot(asset: str) -> tuple[Decimal, Decimal]:
    balance = _call_client_method("get_asset_balance", asset=asset, recvWindow=SETTINGS.recv_window)
    if not balance:
        return Decimal("0"), Decimal("0")
    return _to_decimal(balance["free"]), _to_decimal(balance.get("locked", "0"))


def _get_free_balance(asset: str) -> Decimal:
    free, _ = _get_balance_snapshot(asset)
    return free


def _infer_quote_asset_from_symbol(symbol: str) -> str | None:
    upper = symbol.upper()
    for quote_asset in ("USDT", "FDUSD", "USDC", "BUSD", "TUSD", "BTC", "ETH", "BNB", "TRY"):
        if upper.endswith(quote_asset):
            return quote_asset
    return None


def _load_quote_balance_cache() -> dict[str, float]:
    if not os.path.exists(SETTINGS.quote_balance_cache_path):
        return {}
    try:
        with open(SETTINGS.quote_balance_cache_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, float] = {}
    for asset, value in payload.items():
        try:
            out[str(asset).upper()] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _save_quote_balance_cache(cache: dict[str, float]) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS.quote_balance_cache_path), exist_ok=True)
        with open(SETTINGS.quote_balance_cache_path, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except OSError:
        return


def _cache_quote_balance(asset: str, amount: float) -> None:
    cache = _load_quote_balance_cache()
    cache[asset.upper()] = float(amount)
    _save_quote_balance_cache(cache)


def get_free_quote_balance(symbol: str) -> float:
    quote_asset = None
    try:
        symbol_info = _get_symbol_info(symbol)
        if symbol_info:
            _, quote_asset = _get_assets(symbol_info)
    except Exception:
        quote_asset = None
    quote_asset = quote_asset or _infer_quote_asset_from_symbol(symbol)
    if not quote_asset:
        return 0.0
    try:
        free_balance = float(_get_free_balance(quote_asset))
        _cache_quote_balance(quote_asset, free_balance)
        return free_balance
    except Exception:
        try:
            account = _call_client_method("get_account", recvWindow=SETTINGS.recv_window)
            for item in account.get("balances", []):
                if str(item.get("asset", "")).upper() != quote_asset.upper():
                    continue
                free_balance = float(item.get("free", 0.0))
                _cache_quote_balance(quote_asset, free_balance)
                return free_balance
        except Exception:
            pass
        return float(_load_quote_balance_cache().get(quote_asset.upper(), 0.0))


def _position_qty_delta(position: Position, qty: Decimal) -> Decimal:
    if not position.is_open:
        return qty
    return abs(_to_decimal(position.qty) - qty)


def _position_to_dict(position: Position) -> dict:
    return {
        "symbol": position.symbol,
        "side": position.side,
        "entry_price": position.entry_price,
        "qty": position.qty,
        "peak_price": position.peak_price,
        "is_open": position.is_open,
    }


def _position_from_dict(payload: dict | None) -> Position:
    payload = payload or {}
    return Position(
        symbol=str(payload.get("symbol", "")),
        side=payload.get("side"),
        entry_price=float(payload.get("entry_price", 0.0)),
        qty=float(payload.get("qty", 0.0)),
        peak_price=float(payload.get("peak_price", payload.get("entry_price", 0.0))),
        is_open=bool(payload.get("is_open", False)),
    )


def _summarize_position(position: Position) -> str:
    if not position.is_open:
        return "flat"
    symbol = position.symbol or SETTINGS.symbol
    return f"{symbol} {position.side or 'UNKNOWN'} qty={position.qty:.8f} entry={position.entry_price:.2f}"


def load_runtime_state() -> RuntimeState:
    if not os.path.exists(SETTINGS.runtime_state_path):
        return RuntimeState(position=Position())

    try:
        with open(SETTINGS.runtime_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return RuntimeState(position=Position())

    return RuntimeState(
        position=_position_from_dict(payload.get("position")),
        daily_pnl_pct=float(payload.get("daily_pnl_pct", 0.0)),
        current_equity_usdt=float(payload.get("current_equity_usdt", SETTINGS.starting_equity)),
        last_event=str(payload.get("last_event", "")),
        updated_at=str(payload.get("updated_at", "")),
        loaded_from_disk=True,
    )


def save_runtime_state(position: Position, daily_pnl_pct: float, current_equity_usdt: float | None = None, last_event: str = "") -> None:
    os.makedirs(os.path.dirname(SETTINGS.runtime_state_path), exist_ok=True)
    payload = {
        "position": _position_to_dict(position),
        "daily_pnl_pct": daily_pnl_pct,
        "current_equity_usdt": SETTINGS.starting_equity if current_equity_usdt is None else current_equity_usdt,
        "last_event": last_event,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(SETTINGS.runtime_state_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def _reconstruct_open_lots(trades: list[dict]) -> list[tuple[Decimal, Decimal]]:
    lots: list[list[Decimal]] = []
    ordered = sorted(trades, key=lambda item: (item.get("time", 0), item.get("id", 0)))
    for trade in ordered:
        qty = _to_decimal(trade["qty"])
        price = _to_decimal(trade["price"])
        if qty <= 0:
            continue
        if trade.get("isBuyer", False):
            lots.append([qty, price])
            continue

        remaining = qty
        while remaining > 0 and lots:
            lot_qty, lot_price = lots[0]
            consumed = min(lot_qty, remaining)
            lot_qty -= consumed
            remaining -= consumed
            if lot_qty <= 0:
                lots.pop(0)
            else:
                lots[0] = [lot_qty, lot_price]

        if remaining > 0:
            lots.clear()

    return [(qty, price) for qty, price in lots if qty > 0]


def _infer_entry_price_from_trades(client, symbol: str, current_qty: Decimal, current_price: float) -> tuple[float, str]:
    trades = _call_client_method(
        "get_my_trades",
        symbol=symbol,
        limit=SETTINGS.reconcile_trade_limit,
        recvWindow=SETTINGS.recv_window,
    )
    if not trades:
        return current_price, "current_price"

    lots = _reconstruct_open_lots(trades)
    if not lots:
        return current_price, "current_price"

    open_qty = sum(qty for qty, _ in lots)
    if open_qty <= 0:
        return current_price, "current_price"

    if open_qty < current_qty:
        return current_price, "current_price"

    weighted_cost = sum(qty * price for qty, price in lots)
    return float(weighted_cost / open_qty), "trade_history"


def reconcile_live_position(
    position: Position,
    current_price: float,
    symbol: str | None = None,
    state_known: bool = True,
) -> ReconciliationResult:
    if not _is_live_mode() or SETTINGS.live_test_orders:
        return ReconciliationResult(position=position)

    symbol = symbol or position.symbol or SETTINGS.symbol
    symbol_info = _get_symbol_info(symbol)
    filters = _filter_map(symbol_info)
    base_asset, _ = _get_assets(symbol_info)
    min_qty, _, step = _market_step_and_min_qty(filters)
    min_notional = _min_notional(filters)
    free_qty, locked_qty = _get_balance_snapshot(base_asset)
    total_qty = free_qty + locked_qty

    has_live_position = total_qty >= min_qty and (total_qty * _to_decimal(current_price)) >= min_notional
    if not has_live_position:
        if position.is_open:
            return ReconciliationResult(
                position=Position(),
                changed=True,
                details=(
                    "Binance bakiyesinde acik pozisyon yok; yerel pozisyon sifirlandi. "
                    f"eski={_summarize_position(position)} yeni=flat"
                ),
                external_change=state_known,
            )
        return ReconciliationResult(position=position)

    qty_delta = _position_qty_delta(position, total_qty)
    if position.is_open and position.side == "LONG" and qty_delta <= step and position.entry_price > 0:
        return ReconciliationResult(position=position)

    entry_price, source = _infer_entry_price_from_trades(None, symbol, total_qty, current_price)
    reconciled = Position(
        symbol=symbol,
        side="LONG",
        entry_price=entry_price,
        qty=float(total_qty),
        peak_price=max(current_price, entry_price),
        is_open=True,
    )
    if not position.is_open:
        return ReconciliationResult(
            position=reconciled,
            changed=True,
            details=(
                "Binance bakiyesinden acik LONG pozisyon bulundu. "
                f"eski=flat yeni={_summarize_position(reconciled)} kaynak={source}"
            ),
            external_change=state_known,
        )
    return ReconciliationResult(
        position=reconciled,
        changed=True,
        details=(
            "Yerel pozisyon Binance bakiyesiyle esitlendi. "
            f"eski={_summarize_position(position)} yeni={_summarize_position(reconciled)} kaynak={source}"
        ),
        external_change=state_known,
    )


def _average_fill_price(order: dict, fallback_price: float) -> float:
    fills = order.get("fills") or []
    if fills:
        total_qty = sum(_to_decimal(fill.get("qty", "0")) for fill in fills)
        total_quote = sum(_to_decimal(fill.get("qty", "0")) * _to_decimal(fill.get("price", "0")) for fill in fills)
        if total_qty > 0:
            return float(total_quote / total_qty)
    executed_qty = _to_decimal(order.get("executedQty", "0"))
    quote_qty = _to_decimal(order.get("cummulativeQuoteQty", "0"))
    if executed_qty > 0 and quote_qty > 0:
        return float(quote_qty / executed_qty)
    return fallback_price


def _calculate_slippage_bps(expected_price: float, actual_price: float, side: str) -> float:
    if expected_price <= 0 or actual_price <= 0:
        return 0.0
    if side.upper() == "BUY":
        return ((actual_price - expected_price) / expected_price) * 10_000
    return ((expected_price - actual_price) / expected_price) * 10_000


def _estimate_fee_quote(order: dict, avg_price: float) -> float:
    fills = order.get("fills") or []
    commission_quote = Decimal("0")
    for fill in fills:
        commission = _to_decimal(fill.get("commission", "0"))
        asset = str(fill.get("commissionAsset", "")).upper()
        if commission <= 0:
            continue
        if asset == "USDT":
            commission_quote += commission
        elif avg_price > 0:
            commission_quote += commission * _to_decimal(avg_price)
    return float(commission_quote)


def _fetch_final_order(symbol: str, order_id: int | None, fallback: dict) -> dict:
    if not order_id:
        return fallback
    latest = fallback
    for _ in range(max(1, SETTINGS.order_status_poll_attempts)):
        status = str(latest.get("status", "")).upper()
        executed_qty = _to_decimal(latest.get("executedQty", "0"))
        orig_qty = _to_decimal(latest.get("origQty", latest.get("origQty", "0")))
        if status == "FILLED" or (orig_qty > 0 and executed_qty >= orig_qty):
            return latest
        time.sleep(SETTINGS.order_status_poll_delay_seconds)
        try:
            latest = _call_client_method(
                "get_order",
                symbol=symbol,
                orderId=order_id,
                recvWindow=SETTINGS.recv_window,
            )
        except Exception as exc:
            log_alert("WARN", "order_status", "Order status sorgusu basarisiz", details=str(exc), symbol=symbol)
            return fallback
    return latest


def ensure_order_audit_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.order_audit_log_path) or os.path.getsize(SETTINGS.order_audit_log_path) == 0:
        with open(SETTINGS.order_audit_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "symbol",
                    "action",
                    "order_id",
                    "status",
                    "requested_qty",
                    "executed_qty",
                    "filled_ratio",
                    "fill_count",
                    "avg_price",
                    "slippage_bps",
                    "estimated_fee_quote",
                    "dry_run",
                    "details",
                ]
            )


def log_order_audit(symbol: str, result: OrderResult) -> None:
    ensure_order_audit_log()
    with open(SETTINGS.order_audit_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                symbol,
                result.action,
                result.order_id or "",
                result.status,
                result.requested_qty,
                result.executed_qty,
                result.filled_ratio,
                result.fill_count,
                result.price,
                result.slippage_bps,
                result.estimated_fee_quote,
                result.dry_run,
                result.details,
            ]
        )


def validate_live_trading_setup(symbol: str) -> None:
    if not _is_live_mode():
        return

    if SETTINGS.long_only is False:
        raise ValueError("Canli spot modunda LONG_ONLY=true olmali.")
    if not SETTINGS.api_key or not SETTINGS.api_secret:
        raise ValueError("Canli mod icin BINANCE_API_KEY ve BINANCE_API_SECRET zorunlu.")

    info = get_symbol_info_cached(symbol)
    if not info:
        raise ValueError(f"Sembol bilgisi bulunamadi: {symbol}")
    permissions = _call_client_method(
        "get_account_api_permissions",
        recvWindow=SETTINGS.recv_window,
    )
    if not permissions.get("enableReading", False):
        raise ValueError("API key okuma iznine sahip degil.")
    if not permissions.get("enableSpotAndMarginTrading", False):
        raise ValueError("API key spot trading iznine sahip degil.")
    if permissions.get("ipRestrict") is False and not SETTINGS.allow_unrestricted_api_key:
        raise ValueError(
            "API key icin IP restriction kapali. Devam etmek istersen ALLOW_UNRESTRICTED_API_KEY=true kullan."
        )


def _build_live_order_request(
    action: str,
    current_price: float,
    tracked_qty: float,
    symbol: str,
    atr_pct: float | None = None,
    coin_score: float | None = None,
) -> tuple[dict, float]:
    symbol_info = _get_symbol_info(symbol)
    filters = _filter_map(symbol_info)
    base_asset, quote_asset = _get_assets(symbol_info)
    min_qty, max_qty, step = _market_step_and_min_qty(filters)
    min_notional = _min_notional(filters)
    market_price = _to_decimal(current_price)

    if action == "BUY":
        quote_balance = _get_free_balance(quote_asset)
        if quote_balance < _to_decimal(SETTINGS.min_quote_balance):
            raise ValueError(
                f"Yetersiz {quote_asset} bakiyesi. Min gereken bakiye: {SETTINGS.min_quote_balance}"
            )

        position_fraction = compute_position_fraction(
            base_fraction=SETTINGS.risk_per_trade,
            atr_pct=atr_pct,
            coin_score=coin_score,
            confidence=abs((coin_score or 50.0) / 100.0 - 0.5),
        )
        desired_quote = min(
            float(quote_balance) * position_fraction,
            SETTINGS.max_live_quote_per_order,
        )
        min_quote_target = _min_notional_quote_target(min_notional)
        if quote_balance >= min_quote_target:
            desired_quote = max(desired_quote, float(min_quote_target))
        desired_quote = min(desired_quote, float(quote_balance))
        if desired_quote <= 0:
            raise ValueError(f"Kullanilabilir {quote_asset} bakiyesi yok.")

        quantity = _floor_to_step(_to_decimal(desired_quote) / market_price, step)
        if quantity < min_qty:
            raise ValueError(f"Hesaplanan miktar min qty altinda: {quantity} < {min_qty}")
        if quantity > max_qty:
            quantity = _floor_to_step(max_qty, step)
        if quantity * market_price < min_notional:
            raise ValueError(
                f"Hesaplanan emir notional degeri cok dusuk: {quantity * market_price} < {min_notional}"
            )

        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": format(quantity, "f"),
            "newOrderRespType": "FULL",
            "recvWindow": SETTINGS.recv_window,
        }
        if SETTINGS.prefer_limit_entry:
            micro = get_market_microstructure(symbol=symbol)
            best_ask = float(micro.get("best_ask", 0.0))
            spread_bps = float(micro.get("spread_bps", 0.0))
            if best_ask > 0 and spread_bps <= SETTINGS.max_entry_spread_bps:
                params.update(
                    {
                        "type": "LIMIT",
                        "timeInForce": "IOC",
                        "price": format(_to_decimal(best_ask), "f"),
                    }
                )
        return params, float(quantity)

    if tracked_qty <= 0:
        raise ValueError("Canli satis icin acik pozisyon bulunamadi.")

    base_balance = _get_free_balance(base_asset)
    quantity = _floor_to_step(min(base_balance, _to_decimal(tracked_qty)), step)
    if quantity < min_qty:
        raise ValueError(f"Satilabilir miktar min qty altinda: {quantity} < {min_qty}")
    if quantity > max_qty:
        quantity = _floor_to_step(max_qty, step)
    if quantity * market_price < min_notional:
        raise ValueError(
            f"Satis emri notional degeri cok dusuk: {quantity * market_price} < {min_notional}"
        )

    params = {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "quantity": format(quantity, "f"),
        "newOrderRespType": "FULL",
        "recvWindow": SETTINGS.recv_window,
    }
    if SETTINGS.prefer_limit_entry:
        micro = get_market_microstructure(symbol=symbol)
        best_bid = float(micro.get("best_bid", 0.0))
        spread_bps = float(micro.get("spread_bps", 0.0))
        if best_bid > 0 and spread_bps <= SETTINGS.max_entry_spread_bps:
            params.update(
                {
                    "type": "LIMIT",
                    "timeInForce": "IOC",
                    "price": format(_to_decimal(best_bid), "f"),
                }
            )
    return params, float(quantity)


def preview_live_entry(action: str, current_price: float, symbol: str | None = None) -> tuple[dict, float]:
    if action not in {"BUY", "SELL"}:
        raise ValueError("Sadece BUY veya SELL desteklenir")
    return _build_live_order_request(action, current_price, tracked_qty=0.0, symbol=symbol or SETTINGS.symbol)


def second_entry_validation(
    symbol: str,
    reference_price: float,
    prob_up: float,
    atr_pct: float,
    volume_ratio: float,
    max_entry_spread_bps: float,
    min_entry_depth_notional: float,
) -> tuple[bool, str, float]:
    if not SETTINGS.second_validation_enabled:
        return True, "", reference_price

    latest_price = get_last_price(symbol=symbol)
    drift_bps = abs((latest_price - reference_price) / reference_price) * 10000 if reference_price > 0 else 0.0
    if drift_bps > SETTINGS.max_price_drift_bps:
        return False, "price_drift", latest_price

    micro = get_market_microstructure(symbol=symbol)
    raw = get_klines_df(symbol=symbol, limit=3)
    last_bar_return_pct = 0.0
    if len(raw) >= 2:
        prev_close = float(raw["c"].iloc[-2])
        if prev_close > 0:
            last_bar_return_pct = ((float(raw["c"].iloc[-1]) - prev_close) / prev_close) * 100
    no_trade, reason = detect_no_trade_zone(
        symbol=symbol,
        regime="UPTREND",
        prob_up=prob_up,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
        spread_bps=float(micro["spread_bps"]),
        depth_notional=float(micro["total_depth_notional"]),
        last_bar_return_pct=last_bar_return_pct,
        max_entry_spread_bps=max_entry_spread_bps,
        min_entry_depth_notional=min_entry_depth_notional,
        min_probability_edge=SETTINGS.no_trade_min_probability_edge,
    )
    if no_trade:
        return False, reason, latest_price
    return True, "", latest_price


def execute_entry(
    position: Position,
    action: str,
    price: float,
    equity_usdt: float,
    symbol: str | None = None,
    atr_pct: float | None = None,
    coin_score: float | None = None,
) -> tuple[Position, OrderResult]:
    symbol = symbol or SETTINGS.symbol
    if not _is_live_mode():
        new_position = open_position(
            position,
            action,
            price,
            equity_usdt,
            symbol=symbol,
            atr_pct=atr_pct,
            coin_score=coin_score,
        )
        if not new_position.is_open:
            return new_position, OrderResult(False, action, details="Pozisyon acilamadi")
        return new_position, OrderResult(True, action, qty=new_position.qty, price=price)

    params, qty = _build_live_order_request(
        action,
        price,
        tracked_qty=0.0,
        symbol=symbol,
        atr_pct=atr_pct,
        coin_score=coin_score,
    )
    if SETTINGS.live_test_orders:
        _call_client_method("create_test_order", **params)
        new_position = Position(
            symbol=symbol,
            side="LONG" if action == "BUY" else "SHORT",
            entry_price=price,
            qty=qty,
            peak_price=price,
            is_open=True,
        )
        return new_position, OrderResult(
            True,
            action,
            qty=qty,
            price=price,
            dry_run=True,
            details=f"Binance test order dogrulandi ({params['type']})",
            requested_qty=qty,
            executed_qty=qty,
            filled_ratio=1.0,
            fill_count=1,
            status="TEST",
        )

    order = _call_client_method("create_order", **params)
    order = _fetch_final_order(symbol, order.get("orderId"), order)
    executed_qty = float(order.get("executedQty", qty))
    avg_price = _average_fill_price(order, price)
    slippage_bps = _calculate_slippage_bps(price, avg_price, action)
    estimated_fee_quote = _estimate_fee_quote(order, avg_price)
    new_position = Position(
        symbol=symbol,
        side="LONG" if action == "BUY" else "SHORT",
        entry_price=avg_price,
        qty=executed_qty,
        peak_price=avg_price,
        is_open=executed_qty > 0,
    )
    result = OrderResult(
        True,
        action,
        qty=executed_qty,
        price=avg_price,
        order_id=order.get("orderId"),
        details=order.get("status", ""),
        requested_qty=qty,
        executed_qty=executed_qty,
        filled_ratio=(executed_qty / qty) if qty > 0 else 0.0,
        fill_count=len(order.get("fills") or []),
        status=str(order.get("status", "")),
        slippage_bps=slippage_bps,
        estimated_fee_quote=estimated_fee_quote,
    )
    if result.filled_ratio < 0.999:
        log_alert("WARN", "order_fill", "Kismi dolum algilandi", details=f"{result.filled_ratio:.2%}", symbol=symbol)
    if abs(result.slippage_bps) >= SETTINGS.high_slippage_alert_bps:
        log_alert("WARN", "slippage", "Yuksek slippage algilandi", details=f"{result.slippage_bps:.2f}bps", symbol=symbol)
    log_order_audit(symbol, result)
    return new_position, result


def execute_exit(position: Position, current_price: float, force_close: bool = False) -> tuple[Position, float, OrderResult]:
    updated_position, should_close, pnl_pct, exit_reason = maybe_close_position(position, current_price)
    should_close = should_close or force_close
    if not should_close:
        return updated_position, pnl_pct, OrderResult(False, "HOLD", details="Cikis kosulu saglanmadi")

    action = "SELL" if position.side == "LONG" else "BUY"
    if not _is_live_mode():
        return Position(), pnl_pct, OrderResult(True, action, qty=position.qty, price=current_price, details=exit_reason)

    params, qty = _build_live_order_request(
        action,
        current_price,
        tracked_qty=position.qty,
        symbol=position.symbol or SETTINGS.symbol,
    )
    if SETTINGS.live_test_orders:
        _call_client_method("create_test_order", **params)
        return Position(), pnl_pct, OrderResult(
            True,
            action,
            qty=qty,
            price=current_price,
            dry_run=True,
            details=exit_reason or f"Binance test order dogrulandi ({params['type']})",
            requested_qty=qty,
            executed_qty=qty,
            filled_ratio=1.0,
            fill_count=1,
            status="TEST",
        )

    order = _call_client_method("create_order", **params)
    order = _fetch_final_order(position.symbol or SETTINGS.symbol, order.get("orderId"), order)
    executed_qty = float(order.get("executedQty", qty))
    avg_price = _average_fill_price(order, current_price)
    slippage_bps = _calculate_slippage_bps(current_price, avg_price, action)
    estimated_fee_quote = _estimate_fee_quote(order, avg_price)
    result = OrderResult(
        True,
        action,
        qty=executed_qty,
        price=avg_price,
        order_id=order.get("orderId"),
        details=exit_reason or order.get("status", ""),
        requested_qty=qty,
        executed_qty=executed_qty,
        filled_ratio=(executed_qty / qty) if qty > 0 else 0.0,
        fill_count=len(order.get("fills") or []),
        status=str(order.get("status", "")),
        slippage_bps=slippage_bps,
        estimated_fee_quote=estimated_fee_quote,
    )
    if result.filled_ratio < 0.999:
        log_alert("WARN", "order_fill", "Kismi cikis dolumu algilandi", details=f"{result.filled_ratio:.2%}", symbol=position.symbol or SETTINGS.symbol)
    if abs(result.slippage_bps) >= SETTINGS.high_slippage_alert_bps:
        log_alert("WARN", "slippage", "Cikis slippage yuksek", details=f"{result.slippage_bps:.2f}bps", symbol=position.symbol or SETTINGS.symbol)
    log_order_audit(position.symbol or SETTINGS.symbol, result)
    return Position(), pnl_pct, result


def ensure_trade_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.trade_log_path) or os.path.getsize(SETTINGS.trade_log_path) == 0:
        with open(SETTINGS.trade_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time", "symbol", "action", "price", "qty",
                "regime", "prob_up", "imbalance", "profit_pct"
            ])


def ensure_heartbeat_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.heartbeat_log_path) or os.path.getsize(SETTINGS.heartbeat_log_path) == 0:
        with open(SETTINGS.heartbeat_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time", "symbol", "regime", "decision", "price", "prob_up", "imbalance", "daily_pnl_pct"
            ])


def ensure_candidate_signal_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.candidate_signal_log_path) or os.path.getsize(SETTINGS.candidate_signal_log_path) == 0:
        with open(SETTINGS.candidate_signal_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "symbol",
                    "profile",
                    "decision",
                    "price",
                    "prob_up",
                    "coin_score",
                    "candidate_score",
                    "gate_reason",
                    "regime",
                    "volume_ratio",
                    "atr_pct",
                ]
            )


def ensure_near_candidate_signal_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.near_candidate_signal_log_path) or os.path.getsize(SETTINGS.near_candidate_signal_log_path) == 0:
        with open(SETTINGS.near_candidate_signal_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "symbol",
                    "profile",
                    "decision",
                    "price",
                    "prob_up",
                    "coin_score",
                    "candidate_score",
                    "gate_reason",
                    "regime",
                    "volume_ratio",
                    "atr_pct",
                ]
            )


def ensure_signal_diagnostics_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.signal_diagnostics_log_path) or os.path.getsize(SETTINGS.signal_diagnostics_log_path) == 0:
        with open(SETTINGS.signal_diagnostics_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "symbol",
                    "profile",
                    "decision",
                    "regime",
                    "no_trade_reason",
                    "coin_score",
                    "prob_up",
                    "volume_ratio",
                    "atr_pct",
                    "spread_bps",
                    "depth_notional",
                    "buy_threshold",
                    "entry_score_threshold",
                ]
            )


def ensure_signal_readiness_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.signal_readiness_log_path) or os.path.getsize(SETTINGS.signal_readiness_log_path) == 0:
        with open(SETTINGS.signal_readiness_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "symbol",
                    "profile",
                    "decision",
                    "regime",
                    "regime_ready",
                    "probability_ready",
                    "liquidity_ready",
                    "strong_ready",
                    "missing_parts",
                    "prob_up",
                    "buy_threshold",
                    "volume_ratio",
                    "spread_bps",
                    "depth_notional",
                ]
            )


def log_trade(symbol: str, action: str, price: float, qty: float, regime: str, prob_up: float, imbalance: float, profit_pct: float) -> None:
    ensure_trade_log()
    with open(SETTINGS.trade_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            symbol,
            action,
            price,
            qty,
            regime,
            prob_up,
            imbalance,
            profit_pct,
        ])


def log_heartbeat(symbol: str, regime: str, decision: str, price: float, prob_up: float, imbalance: float, daily_pnl_pct: float) -> None:
    ensure_heartbeat_log()
    with open(SETTINGS.heartbeat_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            symbol,
            regime,
            decision,
            price,
            prob_up,
            imbalance,
            daily_pnl_pct,
        ])


def log_candidate_signal(
    *,
    symbol: str,
    profile: str,
    decision: str,
    price: float,
    prob_up: float,
    coin_score: float,
    candidate_score: int,
    gate_reason: str,
    regime: str,
    volume_ratio: float,
    atr_pct: float,
) -> None:
    ensure_candidate_signal_log()
    with open(SETTINGS.candidate_signal_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                symbol,
                profile,
                decision,
                price,
                prob_up,
                coin_score,
                candidate_score,
                gate_reason,
                regime,
                volume_ratio,
                atr_pct,
            ]
        )


def log_near_candidate_signal(
    *,
    symbol: str,
    profile: str,
    decision: str,
    price: float,
    prob_up: float,
    coin_score: float,
    candidate_score: int,
    gate_reason: str,
    regime: str,
    volume_ratio: float,
    atr_pct: float,
) -> None:
    ensure_near_candidate_signal_log()
    with open(SETTINGS.near_candidate_signal_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                symbol,
                profile,
                decision,
                price,
                prob_up,
                coin_score,
                candidate_score,
                gate_reason,
                regime,
                volume_ratio,
                atr_pct,
            ]
        )


def log_signal_diagnostic(
    *,
    symbol: str,
    profile: str,
    decision: str,
    regime: str,
    no_trade_reason: str,
    coin_score: float,
    prob_up: float,
    volume_ratio: float,
    atr_pct: float,
    spread_bps: float,
    depth_notional: float,
    buy_threshold: float,
    entry_score_threshold: float,
) -> None:
    ensure_signal_diagnostics_log()
    with open(SETTINGS.signal_diagnostics_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                symbol,
                profile,
                decision,
                regime,
                no_trade_reason,
                coin_score,
                prob_up,
                volume_ratio,
                atr_pct,
                spread_bps,
                depth_notional,
                buy_threshold,
                entry_score_threshold,
            ]
        )


def log_signal_readiness(
    *,
    symbol: str,
    profile: str,
    decision: str,
    regime: str,
    regime_ready: bool,
    probability_ready: bool,
    liquidity_ready: bool,
    strong_ready: bool,
    missing_parts: str,
    prob_up: float,
    buy_threshold: float,
    volume_ratio: float,
    spread_bps: float,
    depth_notional: float,
) -> None:
    ensure_signal_readiness_log()
    with open(SETTINGS.signal_readiness_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                symbol,
                profile,
                decision,
                regime,
                regime_ready,
                probability_ready,
                liquidity_ready,
                strong_ready,
                missing_parts,
                prob_up,
                buy_threshold,
                volume_ratio,
                spread_bps,
                depth_notional,
            ]
        )


def open_position(
    position: Position,
    action: str,
    price: float,
    equity_usdt: float,
    symbol: str | None = None,
    atr_pct: float | None = None,
    coin_score: float | None = None,
) -> Position:
    position_fraction = compute_position_fraction(
        base_fraction=SETTINGS.risk_per_trade,
        atr_pct=atr_pct,
        coin_score=coin_score,
        confidence=abs((coin_score or 50.0) / 100.0 - 0.5),
    )
    allocated_quote = min(equity_usdt * position_fraction, SETTINGS.max_live_quote_per_order)
    qty = round(allocated_quote / price, 6) if price > 0 else 0.0

    if qty <= 0:
        return position

    position.symbol = symbol or SETTINGS.symbol
    position.side = "LONG" if action == "BUY" else "SHORT"
    position.entry_price = price
    position.qty = qty
    position.peak_price = price
    position.is_open = True
    return position


def maybe_close_position(position: Position, current_price: float) -> tuple[Position, bool, float, str]:
    if not position.is_open or position.side is None:
        return position, False, 0.0, "flat"

    if position.side == "LONG":
        pnl_pct = (current_price - position.entry_price) / position.entry_price
    else:
        pnl_pct = (position.entry_price - current_price) / position.entry_price

    updated_position = replace(position)
    updated_position.peak_price = max(updated_position.peak_price or updated_position.entry_price, current_price)

    if pnl_pct <= -SETTINGS.stop_loss_pct:
        return updated_position, True, pnl_pct, "sl"

    if updated_position.side == "LONG":
        break_even_price = 0.0
        trailing_stop_price = 0.0
        trailing_active = False

        if updated_position.peak_price >= updated_position.entry_price * (1 + SETTINGS.break_even_trigger_pct):
            break_even_price = updated_position.entry_price * (1 + SETTINGS.break_even_buffer_pct)
        if updated_position.peak_price >= updated_position.entry_price * (1 + SETTINGS.trailing_activation_pct):
            trailing_active = True
            trailing_stop_price = updated_position.peak_price * (1 - SETTINGS.trailing_stop_pct)

        dynamic_stop = max(break_even_price, trailing_stop_price)
        if dynamic_stop > 0 and current_price <= dynamic_stop:
            return updated_position, True, pnl_pct, "trailing"
        if not trailing_active and pnl_pct >= SETTINGS.take_profit_pct:
            return updated_position, True, pnl_pct, "tp"
    elif pnl_pct >= SETTINGS.take_profit_pct:
        return updated_position, True, pnl_pct, "tp"

    return updated_position, False, pnl_pct, "hold"


def get_live_total_equity_usdt(symbols: tuple[str, ...]) -> float:
    if not _is_live_mode():
        return SETTINGS.starting_equity

    account = _call_client_method("get_account", recvWindow=SETTINGS.recv_window)
    balances = account.get("balances", [])
    totals: dict[str, Decimal] = {}
    for item in balances:
        asset = str(item.get("asset", "")).upper()
        if not asset:
            continue
        total = _to_decimal(item.get("free", "0")) + _to_decimal(item.get("locked", "0"))
        if total > 0:
            totals[asset] = total

    equity = float(totals.get("USDT", Decimal("0")))
    for symbol in symbols:
        symbol_info = _get_symbol_info(symbol)
        base_asset, quote_asset = _get_assets(symbol_info)
        if quote_asset != "USDT":
            continue
        qty = totals.get(base_asset, Decimal("0"))
        if qty <= 0:
            continue
        equity += float(qty) * get_last_price(symbol=symbol)
    return equity


def ensure_equity_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.equity_log_path) or os.path.getsize(SETTINGS.equity_log_path) == 0:
        with open(SETTINGS.equity_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "equity_usdt", "daily_pnl_pct", "position_symbol", "position_open"])


def log_equity(equity_usdt: float, daily_pnl_pct: float, position: Position) -> None:
    ensure_equity_log()
    with open(SETTINGS.equity_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                equity_usdt,
                daily_pnl_pct,
                position.symbol,
                position.is_open,
            ]
        )
