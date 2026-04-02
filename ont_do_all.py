from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


CHECKLIST_PATH = Path("logs/ont_live_checklist.json")

REASON_COMMANDS: dict[str, list[list[str]]] = {
    "quick_alt_edge_yok": [[sys.executable, "optimize_ont_15m_breakout.py"]],
    "quick_alt_edge_zayif": [[sys.executable, "optimize_ont_15m_breakout.py"]],
    "wf_zayif": [[sys.executable, "run_ont_breakout_walkforward.py"]],
    "wf_henuz_zayif": [[sys.executable, "run_ont_breakout_walkforward.py"]],
    "bt_zayif": [[sys.executable, "backtest.py"]],
    "bt_sinirda": [[sys.executable, "backtest.py"]],
    "coin_score_yok": [[sys.executable, "coin_scores.py"]],
}

BASELINE_COMMANDS: list[list[str]] = [
    [sys.executable, "network_diagnostics.py"],
    [sys.executable, "archive_market_data.py"],
    [sys.executable, "trainer.py"],
]

FINAL_CHECKS: list[list[str]] = [
    [sys.executable, "live_readiness.py"],
    [sys.executable, "verify_ont_live.py"],
    [sys.executable, "ont_go_live.py"],
]


def _load_checklist() -> dict:
    if not CHECKLIST_PATH.exists() or CHECKLIST_PATH.stat().st_size == 0:
        return {}
    with CHECKLIST_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _tokens(reason: str) -> list[str]:
    return [item.strip() for item in str(reason).split(",") if item.strip()]


def _build_plan(checklist: dict) -> tuple[list[list[str]], list[str]]:
    commands: list[list[str]] = []
    for cmd in BASELINE_COMMANDS:
        if cmd not in commands:
            commands.append(cmd)

    reasons = _tokens((checklist.get("real_live_ready") or {}).get("detail", ""))
    for reason in reasons:
        for cmd in REASON_COMMANDS.get(reason, []):
            if cmd not in commands:
                commands.append(cmd)

    for cmd in FINAL_CHECKS:
        if cmd not in commands:
            commands.append(cmd)
    return commands, reasons


def _run_command(cmd: list[str]) -> bool:
    try:
        completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
        output = (completed.stdout or "").strip() or (completed.stderr or "").strip()
        print(f"[OK] {' '.join(cmd)}")
        if output:
            print(output)
        print()
        return True
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "").strip() or (exc.stderr or "").strip()
        print(f"[FAIL] {' '.join(cmd)}")
        if output:
            print(output)
        print()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ONT gate remediation plan runner")
    parser.add_argument("--execute", action="store_true", help="Komutlari gercekten calistir")
    args = parser.parse_args()

    if not CHECKLIST_PATH.exists():
        print("logs/ont_live_checklist.json bulunamadi; once python verify_ont_live.py calistiriliyor.\n")
        subprocess.run([sys.executable, "verify_ont_live.py"], check=False)

    checklist = _load_checklist()
    commands, reasons = _build_plan(checklist)

    print("ONT gate reason'lari:", reasons or ["(yok)"])
    print("Planlanan adimlar:")
    for i, cmd in enumerate(commands, start=1):
        print(f"  {i}. {' '.join(cmd)}")
    print()

    manual_items: list[str] = []
    manual_items.append("Eger network_diagnostics FAIL donerse dis ag/firewall/proxy izni altyapi seviyesinde acilmali.")
    if "bakiye_yetersiz" in reasons:
        manual_items.append("USDT bakiyesini en az MIN_QUOTE_BALANCE seviyesine cikart.")
    manual_items.append("Dashboard servisini acik tut (health_report dashboard_ok=true olmali).")

    if not args.execute:
        print("Dry-run modu. Tum adimlari calistirmak icin: python ont_do_all.py --execute")
        if manual_items:
            print("Manuel adimlar:")
            for item in manual_items:
                print(f"- {item}")
        return 0

    success = True
    for cmd in commands:
        success = _run_command(cmd) and success

    if manual_items:
        print("Manuel adimlar:")
        for item in manual_items:
            print(f"- {item}")
        print()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
