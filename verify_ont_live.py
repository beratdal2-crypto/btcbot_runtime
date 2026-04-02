from __future__ import annotations

import json
import os
from datetime import datetime, timezone


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


def build_ont_checklist() -> dict[str, object]:
    readiness = _load_json(LIVE_READINESS_PATH)
    best_alt = _load_json(BEST_ALT_PATH)

    ont_is_best = str(best_alt.get("symbol", "")).upper() == "ONTUSDT"
    ont_profile = str(best_alt.get("profile", "")) if ont_is_best else ""
    gate = ((readiness.get("candidate_live_gate") or {}).get("ONTUSDT") or {})
    conditions = gate.get("conditions") or {}

    backtest_row = gate.get("profile_row") or {}
    bt_return = float(backtest_row.get("bt_total_return_pct", 0.0) or 0.0)
    bt_pf = float(backtest_row.get("bt_profit_factor", 0.0) or 0.0)
    bt_trades = int(backtest_row.get("bt_trade_count", 0) or 0)
    wf_return = float(backtest_row.get("wf_avg_return_pct", 0.0) or 0.0)
    wf_trades = int(backtest_row.get("wf_trade_count", 0) or 0)

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
        "real_live_ready": _status(bool(gate.get("ok")), str(gate.get("reason", ""))),
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
