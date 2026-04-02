from __future__ import annotations

import json
import os
import re
from pathlib import Path

from config import SETTINGS


SUSPICIOUS_PATTERNS = {
    "binance_api_key": re.compile(r"BINANCE_API_KEY\s*=\s*[A-Za-z0-9]{20,}"),
    "binance_api_secret": re.compile(r"BINANCE_API_SECRET\s*=\s*[A-Za-z0-9]{20,}"),
    "telegram_token": re.compile(r"TELEGRAM_BOT_TOKEN\s*=\s*\d+:[A-Za-z0-9_-]{20,}"),
}


def run_security_audit(root: str | None = None) -> dict:
    root_path = Path(root or ".").resolve()
    findings: list[dict] = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "venv", "venv312", "__pycache__", "tests"} for part in path.parts):
            continue
        if path.name in {".env.example"}:
            continue
        if path.suffix in {".pkl", ".zip"}:
            continue
        try:
            content = path.read_text(errors="ignore")
        except OSError:
            continue
        for name, pattern in SUSPICIOUS_PATTERNS.items():
            if pattern.search(content):
                findings.append({"pattern": name, "path": str(path)})
    report = {
        "root": str(root_path),
        "finding_count": len(findings),
        "findings": findings,
    }
    os.makedirs(os.path.dirname(SETTINGS.security_audit_path), exist_ok=True)
    with open(SETTINGS.security_audit_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    return report


if __name__ == "__main__":
    print(run_security_audit())
