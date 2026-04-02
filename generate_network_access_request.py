from __future__ import annotations

import datetime as dt
from pathlib import Path


OUTPUT_PATH = Path("logs/network_access_request.md")


def build_request() -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    return f"""# Network Access Request (Binance) - {now}

Merhaba Ag/Guvenlik Ekibi,

Bu hostta Binance API erisimi icin asagidaki outbound izinlere ihtiyacimiz var.

## Istek

1. Outbound TCP 443 acilsin.
2. DNS cozumleme (kurumsal resolver) erisimi acik olsun.
3. Domain allowlist:
   - api.binance.com
   - api1.binance.com
   - api2.binance.com
   - testnet.binance.vision
   - *.binance.com
   - *.binance.vision

## Gozlenen semptom

- TCP testinde: `[Errno 101] Network is unreachable`
- HTTPS proxy yolunda: `Tunnel connection failed: 403 Forbidden`
- HTTPS no-proxy yolunda da ulasilamiyor (route/firewall engeli supheli)

## Is etkisi

Canli dogrulama (`verify_live.py`) Binance API'ye ulasamadigi icin canli gecis onayi veremiyor.

Tesekkurler.
"""


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_request(), encoding="utf-8")
    print(f"Talep dosyasi olusturuldu: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
