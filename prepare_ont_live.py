from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


OUTPUT_ENV_PATH = Path("logs/ont_live_prepared.env")


RECOMMENDED_ENV = {
    "SYMBOL": "ONTUSDT",
    "PRIMARY_SYMBOL": "ONTUSDT",
    "SYMBOLS": "ONTUSDT",
    "ALT_RESEARCH_SYMBOLS": "XRPUSDT,ONTUSDT",
    "LIVE_TRADING": "true",
    "LIVE_TEST_ORDERS": "true",
    "PAPER_TRADE": "false",
    "BINANCE_TESTNET": "false",
    "BINANCE_DISABLE_ENV_PROXY": "true",
}


def _write_prepared_env(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# ONT canliya gecis hazirlik dosyasi")
    lines.append("# Bu dosyayi inceleyip kendi .env dosyana tasiyabilirsin.\n")
    for key, value in RECOMMENDED_ENV.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> int:
    print(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    _write_prepared_env(OUTPUT_ENV_PATH)
    print(f"Hazir env olusturuldu: {OUTPUT_ENV_PATH}")

    print("\nMevcut ortam ile farklar:")
    for key, expected in RECOMMENDED_ENV.items():
        current = os.getenv(key, "(unset)")
        marker = "OK" if str(current).lower() == expected.lower() else "DIFF"
        print(f"- {key}: current={current} expected={expected} [{marker}]")

    print("\nPreflight komutlari calistiriliyor:")
    codes = [
        _run([sys.executable, "network_diagnostics.py"]),
        _run([sys.executable, "ont_do_all.py"]),
        _run([sys.executable, "ont_live_status.py"]),
    ]
    if any(code != 0 for code in codes):
        print("\nSONUC: Hazirlik adimlari tamamlandi, fakat canli gecis icin blockerlar devam ediyor.")
        return 1

    print("\nSONUC: ONT canli gecis icin test-order asamasinda hazir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
