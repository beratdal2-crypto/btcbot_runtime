from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from config import SETTINGS
from data import build_client, _call_with_retries


@dataclass
class AutoTransferState:
    armed: bool = True
    last_transfer_at: float = 0.0
    last_transfer_amount: float = 0.0
    last_transfer_balance: float = 0.0


@dataclass
class AutoTransferResult:
    triggered: bool = False
    executed: bool = False
    dry_run: bool = False
    amount: float = 0.0
    asset: str = ""
    details: str = ""
    transfer_id: str = ""


def _to_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def _floor_to_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if multiple <= 0:
        return value
    return (value / multiple).quantize(Decimal("1"), rounding=ROUND_DOWN) * multiple


def load_auto_transfer_state() -> AutoTransferState:
    if not os.path.exists(SETTINGS.auto_transfer_state_path):
        return AutoTransferState()
    try:
        with open(SETTINGS.auto_transfer_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return AutoTransferState()
    return AutoTransferState(
        armed=bool(payload.get("armed", True)),
        last_transfer_at=float(payload.get("last_transfer_at", 0.0)),
        last_transfer_amount=float(payload.get("last_transfer_amount", 0.0)),
        last_transfer_balance=float(payload.get("last_transfer_balance", 0.0)),
    )


def save_auto_transfer_state(state: AutoTransferState) -> None:
    os.makedirs(os.path.dirname(SETTINGS.auto_transfer_state_path), exist_ok=True)
    with open(SETTINGS.auto_transfer_state_path, "w") as f:
        json.dump(
            {
                "armed": state.armed,
                "last_transfer_at": state.last_transfer_at,
                "last_transfer_amount": state.last_transfer_amount,
                "last_transfer_balance": state.last_transfer_balance,
            },
            f,
            indent=2,
            sort_keys=True,
        )


def ensure_auto_transfer_log() -> None:
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(SETTINGS.auto_transfer_log_path) or os.path.getsize(SETTINGS.auto_transfer_log_path) == 0:
        with open(SETTINGS.auto_transfer_log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time", "asset", "amount", "network", "address", "dry_run", "transfer_id", "details"
            ])


def log_auto_transfer(result: AutoTransferResult) -> None:
    ensure_auto_transfer_log()
    with open(SETTINGS.auto_transfer_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            result.asset,
            result.amount,
            SETTINGS.auto_transfer_network,
            SETTINGS.auto_transfer_address,
            result.dry_run,
            result.transfer_id,
            result.details,
        ])


def _validate_auto_transfer_settings() -> None:
    if not SETTINGS.auto_transfer_enabled:
        return
    if not SETTINGS.api_key or not SETTINGS.api_secret:
        raise ValueError("Auto transfer icin BINANCE_API_KEY ve BINANCE_API_SECRET zorunlu.")
    if not SETTINGS.auto_transfer_address:
        raise ValueError("Auto transfer icin AUTO_TRANSFER_ADDRESS zorunlu.")
    if not SETTINGS.auto_transfer_network:
        raise ValueError("Auto transfer icin AUTO_TRANSFER_NETWORK zorunlu.")
    if SETTINGS.auto_transfer_fraction <= 0 or SETTINGS.auto_transfer_fraction >= 1:
        raise ValueError("AUTO_TRANSFER_FRACTION 0 ile 1 arasinda olmali.")


def _network_info_for_asset(asset: str, network: str) -> dict:
    client = build_client()
    coins = _call_with_retries(lambda: client.get_all_coins_info())
    for coin in coins:
        if coin.get("coin") != asset:
            continue
        for item in coin.get("networkList", []):
            if item.get("network") == network:
                return item
    raise ValueError(f"Coin/network bilgisi bulunamadi: {asset}/{network}")


def _free_balance(asset: str) -> Decimal:
    client = build_client()
    balance = _call_with_retries(lambda: client.get_asset_balance(asset=asset, recvWindow=SETTINGS.recv_window))
    if not balance:
        return Decimal("0")
    return _to_decimal(balance["free"])


def _calculate_transfer_amount(free_balance: Decimal, network_info: dict) -> Decimal:
    raw_amount = free_balance * _to_decimal(SETTINGS.auto_transfer_fraction)
    multiple = _to_decimal(network_info.get("withdrawIntegerMultiple", "0"))
    minimum = _to_decimal(network_info.get("withdrawMin", "0"))
    maximum = _to_decimal(network_info.get("withdrawMax", "999999999"))

    amount = _floor_to_multiple(raw_amount, multiple)
    amount = min(amount, maximum)
    if amount < minimum:
        raise ValueError(f"Hesaplanan transfer miktari minimumun altinda: {amount} < {minimum}")
    return amount


def maybe_auto_transfer(position_is_open: bool) -> AutoTransferResult:
    if not SETTINGS.auto_transfer_enabled:
        return AutoTransferResult(details="disabled")

    _validate_auto_transfer_settings()
    state = load_auto_transfer_state()
    free_balance = _free_balance(SETTINGS.auto_transfer_asset)

    if position_is_open:
        return AutoTransferResult(details="open_position")

    if free_balance < _to_decimal(SETTINGS.auto_transfer_reset_balance):
        if not state.armed:
            state.armed = True
            save_auto_transfer_state(state)

    if free_balance < _to_decimal(SETTINGS.auto_transfer_trigger_balance):
        return AutoTransferResult(details="below_threshold")

    now = time.time()
    if not state.armed:
        return AutoTransferResult(details="already_triggered_for_current_cycle")
    if state.last_transfer_at and now - state.last_transfer_at < SETTINGS.auto_transfer_min_interval_seconds:
        return AutoTransferResult(details="cooldown")

    network_info = _network_info_for_asset(SETTINGS.auto_transfer_asset, SETTINGS.auto_transfer_network)
    amount = _calculate_transfer_amount(free_balance, network_info)

    result = AutoTransferResult(
        triggered=True,
        amount=float(amount),
        asset=SETTINGS.auto_transfer_asset,
    )
    if SETTINGS.auto_transfer_dry_run:
        result.executed = True
        result.dry_run = True
        result.details = "dry_run"
    else:
        client = build_client()
        params = {
            "coin": SETTINGS.auto_transfer_asset,
            "network": SETTINGS.auto_transfer_network,
            "address": SETTINGS.auto_transfer_address,
            "amount": format(amount, "f"),
            "name": SETTINGS.auto_transfer_address_name,
            "walletType": SETTINGS.auto_transfer_wallet_type,
            "transactionFeeFlag": SETTINGS.auto_transfer_transaction_fee_flag,
            "recvWindow": SETTINGS.recv_window,
            "withdrawOrderId": f"autotrf-{int(now)}",
        }
        if SETTINGS.auto_transfer_address_tag:
            params["addressTag"] = SETTINGS.auto_transfer_address_tag
        response = _call_with_retries(lambda: client.withdraw(**params))
        result.executed = True
        result.transfer_id = str(response.get("id", ""))
        result.details = response.get("msg", "submitted")

    state.armed = False
    state.last_transfer_at = now
    state.last_transfer_amount = float(amount)
    state.last_transfer_balance = float(free_balance)
    save_auto_transfer_state(state)
    log_auto_transfer(result)
    return result
