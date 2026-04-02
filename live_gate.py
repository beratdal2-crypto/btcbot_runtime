from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

from coin_scores import live_entry_guard, load_coin_scores
from config import SETTINGS
from profile_guard import PROFILE_REPORT_PATH, live_profile_guard, load_profile_report


ALT_PROFILE_REPORT_PATH = "logs/altcoin_strategy_profiles.csv"
BEST_ALTCOIN_PROFILE_PATH = "logs/best_altcoin_strategy.json"
BTC_QUICK_REPORT_PATH = "logs/ultra_quick_btc_check.json"
RESEARCH_ONLY_ALT_SYMBOLS = {"STGUSDT"}


def _load_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    return None if df.empty else df


def _allowed_alt_symbols() -> set[str]:
    symbols = {
        symbol.upper()
        for symbol in SETTINGS.alt_research_symbols()
        if symbol.upper() not in RESEARCH_ONLY_ALT_SYMBOLS
    }
    for symbol in SETTINGS.trading_symbols():
        upper = symbol.upper()
        if upper == "BTCUSDT" or upper in RESEARCH_ONLY_ALT_SYMBOLS:
            continue
        symbols.add(upper)
    return symbols


def _is_allowed_alt_symbol(symbol: str) -> bool:
    upper = symbol.upper()
    return bool(upper) and upper in _allowed_alt_symbols()


def _profile_report_for_symbol(symbol: str) -> pd.DataFrame | None:
    if symbol.upper() == "BTCUSDT":
        return load_profile_report(PROFILE_REPORT_PATH)
    return _load_csv(ALT_PROFILE_REPORT_PATH)


def _profile_row_for_symbol(symbol: str, strategy_name: str, report: pd.DataFrame | None) -> dict[str, Any] | None:
    if report is None or report.empty:
        return None
    scoped = report.copy()
    if "symbol" in scoped.columns:
        scoped = scoped[scoped["symbol"].astype(str).str.upper() == symbol.upper()]
    if "profile" in scoped.columns:
        scoped = scoped[scoped["profile"].astype(str) == strategy_name]
    if scoped.empty:
        return None
    sort_columns = [column for column in ("research_score", "wf_avg_return_pct", "bt_total_return_pct") if column in scoped.columns]
    if sort_columns:
        scoped = scoped.sort_values(sort_columns, ascending=False)
    return scoped.iloc[0].to_dict()


def _condition(status: str, reason: str = "", **extra: Any) -> dict[str, Any]:
    payload = {"ok": status == "pass", "status": status, "reason": reason}
    payload.update(extra)
    return payload


def _is_hard_guard_reason(reason: str) -> bool:
    lowered = reason.strip().lower()
    if not lowered:
        return False
    hard_tokens = (
        "hard_block",
        "coin_score_yok",
        "coin_score_satiri_yok",
        "canli_skor_dusuk",
        "profil_raporu_yok",
        "profil_skoru_pozitif_degil",
    )
    return any(token in lowered for token in hard_tokens)


def _candidate_points(status: str) -> int:
    if status == "pass":
        return 2
    if status == "warn":
        return 1
    return 0


def evaluate_live_conditions_from_inputs(
    *,
    symbol: str,
    strategy_name: str,
    live_guard_ok: bool,
    live_guard_reason: str,
    profile_guard_ok: bool,
    profile_guard_reason: str,
    profile_row: dict[str, Any] | None,
    quick_report: dict[str, Any] | None,
    quote_balance: float | None,
) -> dict[str, Any]:
    conditions: dict[str, dict[str, Any]] = {}

    if symbol.upper() == "BTCUSDT":
        backtest_quick = (quick_report or {}).get("backtest", {})
        quick_ok = (
            bool((quick_report or {}).get("edge_confirmed"))
            and float(backtest_quick.get("total_return_pct", -999.0)) > SETTINGS.live_gate_min_quick_return_pct
            and float(backtest_quick.get("max_drawdown_pct", 999.0)) < SETTINGS.live_gate_max_quick_drawdown_pct
        )
        quick_candidate = (
            float(backtest_quick.get("total_return_pct", -999.0)) >= SETTINGS.live_gate_candidate_min_bt_return_pct
            and float(backtest_quick.get("max_drawdown_pct", 999.0)) <= SETTINGS.live_gate_candidate_max_quick_drawdown_pct
        )
        if quick_ok:
            conditions["quick_validation"] = _condition("pass")
        elif quick_candidate:
            conditions["quick_validation"] = _condition("warn", "quick_edge_yetersiz")
        else:
            conditions["quick_validation"] = _condition("fail", "quick_edge_yok")
    else:
        quick_ok = (
            profile_row is not None
            and float(profile_row.get("bt_total_return_pct", -999.0)) > SETTINGS.live_gate_min_quick_return_pct
            and float(profile_row.get("bt_max_drawdown_pct", 999.0)) < SETTINGS.live_gate_max_quick_drawdown_pct
        )
        quick_candidate = (
            profile_row is not None
            and float(profile_row.get("bt_total_return_pct", -999.0)) >= SETTINGS.live_gate_candidate_min_bt_return_pct
            and float(profile_row.get("bt_max_drawdown_pct", 999.0)) <= SETTINGS.live_gate_candidate_max_quick_drawdown_pct
        )
        if quick_ok:
            conditions["quick_validation"] = _condition("pass")
        elif quick_candidate:
            conditions["quick_validation"] = _condition("warn", "quick_alt_edge_zayif")
        else:
            conditions["quick_validation"] = _condition("fail", "quick_alt_edge_yok")

    wf_ok = (
        profile_row is not None
        and int(profile_row.get("wf_trade_count", 0)) >= SETTINGS.live_gate_min_wf_trades
        and float(profile_row.get("wf_avg_return_pct", -999.0)) >= SETTINGS.live_gate_min_wf_avg_return_pct
    )
    wf_trade_count = int((profile_row or {}).get("wf_trade_count", 0))
    wf_avg_return = float((profile_row or {}).get("wf_avg_return_pct", -999.0))
    if wf_ok:
        conditions["walkforward"] = _condition("pass")
    elif profile_row is not None and (
        wf_trade_count == 0 or wf_avg_return >= SETTINGS.live_gate_candidate_min_wf_avg_return_pct
    ):
        conditions["walkforward"] = _condition("warn", "wf_henuz_zayif")
    else:
        conditions["walkforward"] = _condition("fail", "wf_zayif")

    bt_ok = (
        profile_row is not None
        and int(profile_row.get("bt_trade_count", 0)) >= SETTINGS.live_gate_min_bt_trades
        and float(profile_row.get("bt_total_return_pct", -999.0)) > SETTINGS.live_gate_min_bt_return_pct
        and float(profile_row.get("bt_profit_factor", 0.0)) > SETTINGS.live_gate_min_bt_profit_factor
    )
    bt_trade_count = int((profile_row or {}).get("bt_trade_count", 0))
    bt_return = float((profile_row or {}).get("bt_total_return_pct", -999.0))
    bt_profit_factor = float((profile_row or {}).get("bt_profit_factor", 0.0))
    bt_drawdown = float((profile_row or {}).get("bt_max_drawdown_pct", 999.0))
    if bt_ok:
        conditions["backtest"] = _condition("pass")
    elif (
        profile_row is not None
        and bt_trade_count >= SETTINGS.live_gate_candidate_min_bt_trades
        and bt_return >= SETTINGS.live_gate_candidate_min_bt_return_pct
        and bt_profit_factor >= SETTINGS.live_gate_candidate_min_bt_profit_factor
        and bt_drawdown <= SETTINGS.live_gate_candidate_max_bt_drawdown_pct
    ):
        conditions["backtest"] = _condition("warn", "bt_sinirda")
    else:
        conditions["backtest"] = _condition("fail", "bt_zayif")

    guard_ok = live_guard_ok and profile_guard_ok
    guard_reason = ",".join(part for part in [live_guard_reason, profile_guard_reason] if part)
    if guard_ok:
        conditions["guards"] = _condition("pass")
    elif _is_hard_guard_reason(guard_reason):
        conditions["guards"] = _condition("fail", guard_reason)
    else:
        conditions["guards"] = _condition("warn", guard_reason or "guard_sinirda")

    balance_ok = quote_balance is not None and float(quote_balance) >= SETTINGS.min_quote_balance
    if balance_ok:
        conditions["balance"] = _condition(
            "pass",
            quote_balance=None if quote_balance is None else float(quote_balance),
            min_quote_balance=float(SETTINGS.min_quote_balance),
        )
    else:
        conditions["balance"] = _condition(
            "fail",
            "bakiye_yetersiz",
            quote_balance=None if quote_balance is None else float(quote_balance),
            min_quote_balance=float(SETTINGS.min_quote_balance),
        )

    strict_ok = all(condition["status"] == "pass" for condition in conditions.values())
    candidate_score = sum(_candidate_points(condition["status"]) for condition in conditions.values())
    candidate_ok = (
        not strict_ok
        and all(condition["status"] != "fail" for condition in conditions.values())
        and candidate_score >= SETTINGS.live_gate_candidate_min_score
    )
    reasons = [condition["reason"] for condition in conditions.values() if condition.get("reason")]
    return {
        "symbol": symbol,
        "profile": strategy_name,
        "ok": bool(strict_ok),
        "strict_ok": bool(strict_ok),
        "candidate_ok": bool(candidate_ok),
        "candidate_score": int(candidate_score),
        "reason": ",".join(reasons),
        "conditions": conditions,
        "profile_row": profile_row or {},
    }


def live_deployment_guard(symbol: str, strategy_name: str, quote_balance: float | None = None) -> tuple[bool, str, dict[str, Any]]:
    scores = load_coin_scores()
    live_guard_ok, live_guard_reason = live_entry_guard(symbol, scores=scores)
    report = _profile_report_for_symbol(symbol)
    profile_guard_ok = True
    profile_guard_reason = ""
    if symbol.upper() == "BTCUSDT":
        profile_guard_ok, profile_guard_reason = live_profile_guard(strategy_name, report)
    profile_row = _profile_row_for_symbol(symbol, strategy_name, report)
    quick_report = _load_json(BTC_QUICK_REPORT_PATH) if symbol.upper() == "BTCUSDT" else None
    evaluation = evaluate_live_conditions_from_inputs(
        symbol=symbol,
        strategy_name=strategy_name,
        live_guard_ok=live_guard_ok,
        live_guard_reason=live_guard_reason,
        profile_guard_ok=profile_guard_ok,
        profile_guard_reason=profile_guard_reason,
        profile_row=profile_row,
        quick_report=quick_report,
        quote_balance=quote_balance,
    )
    return bool(evaluation["ok"]), str(evaluation["reason"]), evaluation


def load_best_altcoin_candidate() -> dict[str, Any] | None:
    payload = _load_json(BEST_ALTCOIN_PROFILE_PATH)
    if payload:
        symbol = str(payload.get("symbol", "")).upper()
        if _is_allowed_alt_symbol(symbol):
            return payload

    report = _load_csv(ALT_PROFILE_REPORT_PATH)
    if report is not None and not report.empty and "symbol" in report.columns:
        scoped = report.copy()
        scoped = scoped[scoped["symbol"].astype(str).str.upper().isin(_allowed_alt_symbols())]
        if not scoped.empty:
            sort_columns = [column for column in ("research_score", "bt_profit_factor", "bt_total_return_pct") if column in scoped.columns]
            if sort_columns:
                scoped = scoped.sort_values(sort_columns, ascending=False)
            return scoped.iloc[0].to_dict()

    fallback = _fallback_altcoin_candidates()
    return fallback[0] if fallback else None


def _fallback_altcoin_research_score(row: dict[str, Any]) -> float:
    return (
        float(row.get("bt_total_return_pct", 0.0)) * 0.40
        - float(row.get("bt_max_drawdown_pct", 0.0)) * 0.15
        + float(row.get("bt_profit_factor", 0.0)) * 0.35
        + min(int(row.get("bt_trade_count", 0)), 5) * 0.08
    )


def _fallback_altcoin_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    profiles = ("alt_5m_pullback", "alt_5m_breakout", "eth_5m_pullback", "eth_5m_continuation")
    for symbol in SETTINGS.alt_research_symbols():
        upper_symbol = symbol.upper()
        if upper_symbol in RESEARCH_ONLY_ALT_SYMBOLS:
            continue
        best_row: dict[str, Any] | None = None
        for profile in profiles:
            summary_path = os.path.join("logs", f"{upper_symbol.lower()}_{profile}_backtest_summary.csv")
            summary_df = _load_csv(summary_path)
            if summary_df is None or summary_df.empty:
                continue
            row = {
                "symbol": upper_symbol,
                "profile": profile,
                "bt_trade_count": int(summary_df.iloc[-1].get("trade_count", 0)),
                "bt_total_return_pct": float(summary_df.iloc[-1].get("total_return_pct", 0.0)),
                "bt_max_drawdown_pct": float(summary_df.iloc[-1].get("max_drawdown_pct", 0.0)),
                "bt_profit_factor": float(summary_df.iloc[-1].get("profit_factor", 0.0)),
                "wf_fold_count": 0,
                "wf_trade_count": 0,
                "wf_avg_return_pct": 0.0,
                "wf_avg_max_drawdown_pct": 0.0,
                "wf_avg_win_rate_pct": 0.0,
            }
            row["research_score"] = _fallback_altcoin_research_score(row)
            if best_row is None or float(row["research_score"]) > float(best_row["research_score"]):
                best_row = row
        if best_row is not None:
            candidates.append(best_row)
    candidates.sort(
        key=lambda item: (
            float(item.get("research_score", -999.0)),
            float(item.get("bt_profit_factor", 0.0)),
            float(item.get("bt_total_return_pct", -999.0)),
        ),
        reverse=True,
    )
    return candidates


def load_best_altcoin_candidate_for_symbol(symbol: str) -> dict[str, Any] | None:
    upper_symbol = symbol.upper()
    if not _is_allowed_alt_symbol(upper_symbol):
        return None
    report = _load_csv(ALT_PROFILE_REPORT_PATH)
    if report is not None and not report.empty and "symbol" in report.columns:
        scoped = report.copy()
        scoped = scoped[scoped["symbol"].astype(str).str.upper() == upper_symbol]
        if not scoped.empty:
            sort_columns = [column for column in ("research_score", "bt_profit_factor", "bt_total_return_pct") if column in scoped.columns]
            if sort_columns:
                scoped = scoped.sort_values(sort_columns, ascending=False)
            return scoped.iloc[0].to_dict()

    for row in _fallback_altcoin_candidates():
        if str(row.get("symbol", "")).upper() == upper_symbol:
            return row
    return None


def load_backup_altcoin_candidates(primary_symbol: str = "", limit: int = 2) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    allowed_symbols = _allowed_alt_symbols()
    report = _load_csv(ALT_PROFILE_REPORT_PATH)
    if report is not None and not report.empty:
        scoped = report.copy()
        scoped = scoped[scoped["symbol"].astype(str).str.upper().isin(allowed_symbols)]
        if primary_symbol:
            scoped = scoped[scoped["symbol"].astype(str).str.upper() != primary_symbol.upper()]
        if not scoped.empty:
            scoped = scoped.sort_values(
                ["research_score", "bt_profit_factor", "bt_total_return_pct"],
                ascending=False,
            )
            for _, row in scoped.iterrows():
                symbol = str(row.get("symbol", "")).upper()
                if not symbol or symbol in seen:
                    continue
                ordered.append(row.to_dict())
                seen.add(symbol)
                if len(ordered) >= limit:
                    return ordered

    for row in _fallback_altcoin_candidates():
        symbol = str(row.get("symbol", "")).upper()
        if not symbol or symbol in seen:
            continue
        if primary_symbol and symbol == primary_symbol.upper():
            continue
        ordered.append(row)
        seen.add(symbol)
        if len(ordered) >= limit:
            break
    return ordered
