#!/usr/bin/env bash
set -u

echo "Ağ erişimi yeniden uygulama başlıyor"

echo
echo "[1/4] Proxy env temizleniyor"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
export NO_PROXY="localhost,127.0.0.1,binance.com,.binance.com,binance.vision,.binance.vision"
export no_proxy="$NO_PROXY"
echo "NO_PROXY=$NO_PROXY"

echo
echo "[2/4] Ağ tanısı çalıştırılıyor"
python network_diagnostics.py || true

echo
echo "[3/4] Ağ erişim talebi dosyası üretiliyor"
python generate_network_access_request.py

echo
echo "[4/4] Canlı doğrulama tekrar deneniyor"
python verify_live.py || true

echo
echo "Tamamlandı. Hâlâ FAIL varsa sorun host/egress firewall tarafındadır."
