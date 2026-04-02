from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from config import SETTINGS
from live_gate import (
    live_deployment_guard,
    load_backup_altcoin_candidates,
    load_best_altcoin_candidate,
    load_best_altcoin_candidate_for_symbol,
)
from profile_guard import best_profile_row, load_profile_report

try:
    from execution import get_free_quote_balance as _quote_balance_reader
except ImportError:
    from execution import _get_free_balance as _legacy_balance_reader

    def _quote_balance_reader(symbol: str) -> float:
        quote_asset = "USDT"
        upper = symbol.upper()
        for candidate in ("USDT", "FDUSD", "USDC", "BUSD", "TUSD", "BTC", "ETH", "BNB", "TRY"):
            if upper.endswith(candidate):
                quote_asset = candidate
                break
        return float(_legacy_balance_reader(quote_asset))


def build_live_readiness_report() -> dict:
    api_keys_present = bool(SETTINGS.api_key and SETTINGS.api_secret)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_keys_present": api_keys_present,
        "paper_trade": SETTINGS.paper_trade,
        "live_trading": SETTINGS.live_trading,
        "live_test_orders": SETTINGS.live_test_orders,
        "shadow_mode_enabled": SETTINGS.shadow_mode_enabled,
        "kill_switch_enabled": SETTINGS.kill_switch_enabled,
        "notifications_enabled": SETTINGS.notification_enabled,
        "auto_transfer_enabled": SETTINGS.auto_transfer_enabled,
        "min_quote_balance": SETTINGS.min_quote_balance,
        "risk_per_trade": SETTINGS.risk_per_trade,
        "max_live_quote_per_order": SETTINGS.max_live_quote_per_order,
        "symbols": list(SETTINGS.trading_symbols()),
        "candidate_symbols": [],
        "live_score_guard_enabled": SETTINGS.live_require_score_guard,
        "live_entry_guard": {},
        "live_deployment_gate": {},
        "best_strategy_profile": {},
        "best_altcoin_strategy": {},
        "backup_altcoin_candidates": [],
        "candidate_live_gate": {},
        "backup_candidate_live_gate": {},
        "next_manual_actions": [],
    }
    profile_report = load_profile_report()
    best_profile = best_profile_row(profile_report)
    best_altcoin = load_best_altcoin_candidate()
    if best_profile:
        report["best_strategy_profile"] = best_profile
    if best_altcoin:
        report["best_altcoin_strategy"] = best_altcoin
    primary_alt_symbol = str(best_altcoin.get("symbol", "")).strip().upper() if best_altcoin else ""
    backup_altcoins = load_backup_altcoin_candidates(primary_symbol=primary_alt_symbol, limit=2)
    if backup_altcoins:
        report["backup_altcoin_candidates"] = backup_altcoins
    for symbol in SETTINGS.trading_symbols():
        symbol_alt_profile = load_best_altcoin_candidate_for_symbol(symbol)
        if symbol_alt_profile:
            profile_name = str(symbol_alt_profile.get("profile", "balanced"))
        elif best_altcoin and str(best_altcoin.get("symbol", "")).strip().upper() == symbol.upper():
            profile_name = str(best_altcoin.get("profile", "balanced"))
        else:
            profile_name = str(best_profile.get("profile", "balanced")) if best_profile else "balanced"
        try:
            quote_balance = _quote_balance_reader(symbol) if api_keys_present and SETTINGS.live_trading else None
        except Exception:
            quote_balance = None
        allowed, reason, evaluation = live_deployment_guard(symbol, profile_name, quote_balance=quote_balance)
        report["live_entry_guard"][symbol] = {
            "allowed": allowed,
            "candidate": bool(evaluation.get("candidate_ok", False)),
            "candidate_score": int(evaluation.get("candidate_score", 0)),
            "reason": reason,
        }
        report["live_deployment_gate"][symbol] = evaluation
    candidate_symbols: list[str] = list(SETTINGS.trading_symbols())
    if best_altcoin:
        alt_symbol = str(best_altcoin.get("symbol", "")).strip().upper()
        alt_profile = str(best_altcoin.get("profile", "")).strip()
        if alt_symbol and alt_symbol not in candidate_symbols:
            candidate_symbols.append(alt_symbol)
            try:
                alt_quote_balance = _quote_balance_reader(alt_symbol) if api_keys_present and SETTINGS.live_trading else None
            except Exception:
                alt_quote_balance = None
            report["candidate_live_gate"][alt_symbol] = live_deployment_guard(
                alt_symbol,
                alt_profile,
                quote_balance=alt_quote_balance,
            )[2]
    for backup in backup_altcoins:
        alt_symbol = str(backup.get("symbol", "")).strip().upper()
        alt_profile = str(backup.get("profile", "")).strip()
        if not alt_symbol or not alt_profile:
            continue
        if alt_symbol not in candidate_symbols:
            candidate_symbols.append(alt_symbol)
        report["backup_candidate_live_gate"][alt_symbol] = live_deployment_guard(
            alt_symbol,
            alt_profile,
            quote_balance=None,
        )[2]
    report["candidate_symbols"] = candidate_symbols
    if not api_keys_present:
        report["next_manual_actions"].append("Yeni Binance API key/secret olustur ve .env icine yaz.")
    if SETTINGS.live_trading and SETTINGS.live_test_orders:
        report["next_manual_actions"].append("Gercek emre gecmeden once verify_live.py ile test-order dogrula.")
    blocked_symbols = [symbol for symbol, result in report["live_entry_guard"].items() if not result["allowed"]]
    if blocked_symbols:
        report["next_manual_actions"].append(
            "Canli gate aktif; gercek emre gecmeden once su semboller 5 kosulu birlikte gecmeli: "
            + ", ".join(blocked_symbols)
        )
    candidate_symbols = [symbol for symbol, result in report["live_entry_guard"].items() if result.get("candidate")]
    if candidate_symbols:
        report["next_manual_actions"].append(
            "Su semboller aday seviyesinde; tam canliya gecmeden once daha fazla veri ve wf trade gerekli: "
            + ", ".join(candidate_symbols)
        )
    blocked_candidates = [symbol for symbol, result in report["candidate_live_gate"].items() if not result.get("ok", False)]
    if blocked_candidates:
        report["next_manual_actions"].append(
            "Aday altcoin canli gate sonucu da henuz negatif: " + ", ".join(blocked_candidates)
        )
    blocked_backups = [symbol for symbol, result in report["backup_candidate_live_gate"].items() if not result.get("ok", False)]
    if blocked_backups:
        report["next_manual_actions"].append(
            "Yedek altcoin adaylari henuz strict live degil: " + ", ".join(blocked_backups)
        )
    if SETTINGS.notification_enabled and (not SETTINGS.telegram_bot_token or not SETTINGS.telegram_chat_id):
        report["next_manual_actions"].append("Telegram token/chat id eksik; bildirim kanali yerel logda kaliyor.")
    if SETTINGS.auto_transfer_enabled and SETTINGS.auto_transfer_dry_run:
        report["next_manual_actions"].append("Otomatik transfer dry-run modunda; canliya almadan once dashboard loglarini kontrol et.")

    os.makedirs(os.path.dirname(SETTINGS.live_readiness_path), exist_ok=True)
    with open(SETTINGS.live_readiness_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    return report


if __name__ == "__main__":
    print(build_live_readiness_report())
