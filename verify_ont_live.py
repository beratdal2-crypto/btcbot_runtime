from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from config import SETTINGS


LIVE_READINESS_PATH = "logs/live_readiness.json"
BEST_ALT_PATH = "logs/best_altcoin_strategy.json"
OUTPUT_PATH = "logs/ont_live_checklist.json"


def _load_json(path: str) -> dict:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _status(ok: bool, detail: str) -> dict[str, object]:
    return {"ok": bool(ok), "detail": detail}


REASON_ACTIONS = {
    "quick_alt_edge_yok": "Profil backtest metriklerini guclendir: bt_total_return_pct artir, bt_max_drawdown_pct dusur.",
    "quick_alt_edge_zayif": "Quick edge sinirda; ONT parametrelerini optimize edip tekrar profile report uret.",
    "wf_zayif": "Walk-forward sonucu zayif; wf_trade_count ve wf_avg_return_pct degerlerini arttiracak sekilde yeniden egit/optimize et.",
    "wf_henuz_zayif": "Walk-forward henuz sinirda; daha fazla veri ile yeniden calistir.",
    "bt_zayif": "Backtest zayif; bt_trade_count, bt_total_return_pct ve bt_profit_factor metriklerini esik ustune cikar.",
    "bt_sinirda": "Backtest sinirda; risk ayarlari ve profil secimini iyilestir.",
    "coin_score_yok": "Coin score verisi yok; coin_scores uretimi icin arastirma/egitim akisini calistir.",
    "skor_dusuk": "Coin score esik alti; profil/parametre iyilestir.",
    "hard_block": "Hard block var; coin_scores raporunda block nedenini kaldir.",
    "bakiye_yetersiz": "USDT bakiyesini MIN_QUOTE_BALANCE esiginin ustune cikar.",
}


def _reason_tokens(reason: str) -> list[str]:
    return [token.strip() for token in str(reason).split(",") if token.strip()]


def _remediation_steps(reason: str) -> list[str]:
    steps: list[str] = []
    for token in _reason_tokens(reason):
        action = REASON_ACTIONS.get(token)
        if action and action not in steps:
            steps.append(action)
    return steps


def _collect_condition_reasons(conditions: dict) -> list[str]:
    reasons: list[str] = []
    for payload in conditions.values():
        reason = str((payload or {}).get("reason", "")).strip()
        if reason:
            reasons.extend(_reason_tokens(reason))
    deduped: list[str] = []
    for token in reasons:
        if token not in deduped:
            deduped.append(token)
    return deduped


def _thresholds_snapshot() -> dict[str, float | int]:
    return {
        "min_quote_balance": float(SETTINGS.min_quote_balance),
        "live_gate_min_wf_trades": int(SETTINGS.live_gate_min_wf_trades),
        "live_gate_min_wf_avg_return_pct": float(SETTINGS.live_gate_min_wf_avg_return_pct),
        "live_gate_min_bt_trades": int(SETTINGS.live_gate_min_bt_trades),
        "live_gate_min_bt_return_pct": float(SETTINGS.live_gate_min_bt_return_pct),
        "live_gate_min_bt_profit_factor": float(SETTINGS.live_gate_min_bt_profit_factor),
        "live_gate_max_quick_drawdown_pct": float(SETTINGS.live_gate_max_quick_drawdown_pct),
    }


def build_ont_checklist() -> dict[str, object]:
    readiness = _load_json(LIVE_READINESS_PATH)
    best_alt = _load_json(BEST_ALT_PATH)

    ont_is_best = str(best_alt.get("symbol", "")).upper() == "ONTUSDT"
    ont_profile = str(best_alt.get("profile", "")) if ont_is_best else ""
    gate = (
        ((readiness.get("candidate_live_gate") or {}).get("ONTUSDT") or {})
        or ((readiness.get("live_deployment_gate") or {}).get("ONTUSDT") or {})
    )
    conditions = gate.get("conditions") or {}

    backtest_row = gate.get("profile_row") or {}
    bt_return = float(backtest_row.get("bt_total_return_pct", 0.0) or 0.0)
    bt_pf = float(backtest_row.get("bt_profit_factor", 0.0) or 0.0)
    bt_trades = int(backtest_row.get("bt_trade_count", 0) or 0)
    wf_return = float(backtest_row.get("wf_avg_return_pct", 0.0) or 0.0)
    wf_trades = int(backtest_row.get("wf_trade_count", 0) or 0)

    live_reason = str(gate.get("reason", ""))
    reason_tokens = _reason_tokens(live_reason)
    if not reason_tokens:
        reason_tokens = _collect_condition_reasons(conditions)
    merged_reason = ",".join(reason_tokens)
    checklist = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": "ONTUSDT",
        "profile": ont_profile,
        "is_current_best_altcoin": _status(ont_is_best, "ONT su anki en iyi alt aday." if ont_is_best else "ONT su an en iyi alt aday degil."),
        "quick_validation": _status(
            bool((conditions.get("quick_validation") or {}).get("ok")),
            str((conditions.get("quick_validation") or {}).get("reason", "")),
        ),
        "walkforward": _status(
            bool((conditions.get("walkforward") or {}).get("ok")),
            f"wf_trade_count={wf_trades}, wf_avg_return_pct={wf_return:.4f}",
        ),
        "backtest": _status(
            bool((conditions.get("backtest") or {}).get("ok")),
            f"bt_trade_count={bt_trades}, bt_total_return_pct={bt_return:.4f}, bt_profit_factor={bt_pf:.4f}",
        ),
        "guards": _status(
            bool((conditions.get("guards") or {}).get("ok")),
            str((conditions.get("guards") or {}).get("reason", "")),
        ),
        "balance": _status(
            bool((conditions.get("balance") or {}).get("ok")),
            str((conditions.get("balance") or {}).get("reason", "")),
        ),
        "test_order_stage": _status(
            bool(readiness.get("live_trading")) and bool(readiness.get("live_test_orders")),
            "Canli test-order acik." if bool(readiness.get("live_trading")) and bool(readiness.get("live_test_orders")) else "Test-order asamasi aktif degil.",
        ),
        "real_live_ready": _status(bool(gate.get("ok")), merged_reason),
        "thresholds": _thresholds_snapshot(),
        "remediation_steps": _remediation_steps(merged_reason),
        "next_step": "LIVE_TEST_ORDERS=false yapma; once tum gate maddeleri yesile donmeli." if not bool(gate.get("ok")) else "Test-order dogrulamasindan sonra gercek canliya gecilebilir.",
    }
    return checklist


def main() -> dict[str, object]:
    payload = build_ont_checklist()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
