from __future__ import annotations

import json
from pathlib import Path


LIVE_READINESS = Path("logs/live_readiness.json")
ONT_CHECKLIST = Path("logs/ont_live_checklist.json")
SYSTEM_HEALTH = Path("logs/system_health.json")


def _load(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    readiness = _load(LIVE_READINESS)
    ont = _load(ONT_CHECKLIST)
    health = _load(SYSTEM_HEALTH)

    real_ready = bool((ont.get("real_live_ready") or {}).get("ok"))
    live_test_stage = bool((ont.get("test_order_stage") or {}).get("ok"))
    dashboard_ok = bool(health.get("dashboard_ok"))
    blockers = list(ont.get("remediation_steps") or [])
    gate_reason = str((ont.get("real_live_ready") or {}).get("detail", "")).strip()

    print("ONT canliya gecis - son durum")
    print(f"real_live_ready: {real_ready}")
    print(f"test_order_stage: {live_test_stage}")
    print(f"dashboard_ok: {dashboard_ok}")
    print(f"gate_reason: {gate_reason or '(yok)'}")

    if blockers:
        print("blocker_list:")
        for idx, item in enumerate(blockers, start=1):
            print(f"  {idx}. {item}")

    if real_ready and live_test_stage and dashboard_ok:
        print("SONUC: ONT canli gecise HAZIR.")
        return 0

    print("SONUC: ONT canli gecise HENUZ HAZIR DEGIL.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
