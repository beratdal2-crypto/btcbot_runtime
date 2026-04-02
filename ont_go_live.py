from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from config import SETTINGS


ONT_CHECK_PATH = Path("logs/ont_live_checklist.json")


def _run_step(cmd: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        output = completed.stdout.strip() or completed.stderr.strip()
        return True, output
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "").strip() or (exc.stderr or "").strip()
        return False, output


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    steps = [
        [sys.executable, "live_readiness.py"],
        [sys.executable, "verify_ont_live.py"],
        [sys.executable, "verify_live.py"],
        [sys.executable, "health_report.py"],
    ]

    print("ONTUSDT canliya gecis on-kontrolu baslatiliyor...\n")
    failed = False
    for cmd in steps:
        ok, output = _run_step(cmd)
        marker = "OK" if ok else "FAIL"
        print(f"[{marker}] {' '.join(cmd)}")
        if output:
            print(output)
        print()
        failed = failed or (not ok)

    ont = _load_json(ONT_CHECK_PATH)
    readiness = _load_json(Path(SETTINGS.live_readiness_path))
    system_health = _load_json(Path(SETTINGS.system_health_path))

    real_live_ready = bool((ont.get("real_live_ready") or {}).get("ok"))
    dashboard_ok = bool(system_health.get("dashboard_ok"))
    live_flags_ok = bool(readiness.get("live_trading")) and bool(readiness.get("live_test_orders"))

    print("=== Ozet ===")
    print(f"real_live_ready: {real_live_ready}")
    print(f"dashboard_ok: {dashboard_ok}")
    print(f"live_test_order_asamasi: {live_flags_ok}")
    remediation_steps = ont.get("remediation_steps") or []
    thresholds = ont.get("thresholds") or {}
    if thresholds:
        print(f"thresholds: {thresholds}")
    if remediation_steps:
        print("gate_yesile_cevirmek_icin:")
        for idx, step in enumerate(remediation_steps, start=1):
            print(f"  {idx}. {step}")

    if real_live_ready and dashboard_ok and not failed:
        print("\nSONUC: Test-order asamasi icin hazir.")
        print("Gercek emir gecisi icin sonra .env icinde PAPER_TRADE=false ve LIVE_TEST_ORDERS=false yap.")
        return 0

    print("\nSONUC: Henuz canli gecis icin hazir degil.")
    print("Once verify_ont_live.py ve verify_live.py icindeki red nedenlerini kapat.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
