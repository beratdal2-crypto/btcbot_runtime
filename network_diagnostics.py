from __future__ import annotations

import socket
import ssl
import urllib.request
import os


TARGETS = [
    ("api1.binance.com", 443, "https://api1.binance.com/api/v3/ping"),
    ("api2.binance.com", 443, "https://api2.binance.com/api/v3/ping"),
    ("api.binance.com", 443, "https://api.binance.com/api/v3/ping"),
]
PROXY_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
]


def _check_dns(host: str) -> tuple[bool, str]:
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except Exception as exc:
        return False, str(exc)


def _check_tcp(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=4):
            return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _check_https(url: str) -> tuple[bool, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
            body = resp.read(200).decode("utf-8", errors="ignore")
        return True, body.strip()
    except Exception as exc:
        return False, str(exc)


def _snapshot_proxy_env() -> dict[str, str]:
    return {k: os.getenv(k, "") for k in PROXY_KEYS if os.getenv(k, "")}


def _check_https_without_proxy(url: str) -> tuple[bool, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=6) as resp:
            body = resp.read(200).decode("utf-8", errors="ignore")
        return True, body.strip()
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    print("Dis ag erisim tani testi (Binance):\n")
    proxy_env = _snapshot_proxy_env()
    if proxy_env:
        print("Aktif proxy env bulundu:")
        for key, value in proxy_env.items():
            print(f"  {key}={value}")
        print()
    else:
        print("Aktif proxy env yok.\n")

    any_https_ok = False
    any_https_no_proxy_ok = False
    for host, port, url in TARGETS:
        dns_ok, dns_info = _check_dns(host)
        tcp_ok, tcp_info = _check_tcp(host, port)
        https_ok, https_info = _check_https(url)
        https_no_proxy_ok, https_no_proxy_info = _check_https_without_proxy(url)
        any_https_ok = any_https_ok or https_ok
        any_https_no_proxy_ok = any_https_no_proxy_ok or https_no_proxy_ok
        print(f"{host}:{port}")
        print(f"  DNS   : {'OK' if dns_ok else 'FAIL'} -> {dns_info}")
        print(f"  TCP   : {'OK' if tcp_ok else 'FAIL'} -> {tcp_info}")
        print(f"  HTTPS : {'OK' if https_ok else 'FAIL'} -> {https_info}")
        print(f"  HTTPS(no-proxy): {'OK' if https_no_proxy_ok else 'FAIL'} -> {https_no_proxy_info}")
        print()

    if any_https_ok:
        print("SONUC: Dis ag erisimi aktif gorunuyor.")
        return 0
    if (not any_https_ok) and any_https_no_proxy_ok:
        print("SONUC: Proxy kaynakli engel tespit edildi. Proxy bypass ile baglanti kurulabiliyor.")
        print("Aksiyon: BINANCE_DISABLE_ENV_PROXY=true ve kurumsal proxy bypass tanimlari.")
        return 1

    print("SONUC: Dis ag erisimi kapalI / engelli gorunuyor.")
    print("Acilmasi icin altyapi tarafinda outbound 443 + DNS erisimi gerekli.")
    print("Kurum firewall/proxy kurallari: *.binance.com ve *.binance.vision icin izin verilmeli.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
