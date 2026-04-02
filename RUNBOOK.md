# Operasyon Runbook

## Baslangic

1. [`.env`](/Users/beratdal/Desktop/btc_bot_complete/.env) dosyasinda API ve mod ayarlarini kontrol et.
2. `venv312/bin/python live_readiness.py` calistir.
3. `venv312/bin/python verify_live.py` ile hesap/izin durumunu dogrula.
4. Dashboard'u [http://127.0.0.1:8501](http://127.0.0.1:8501) adresinden ac.

## Gunluk Kontrol

1. `Model` sekmesinde `Coin Bazli Model Durumu` ve `Coin Skorlari` kartlarini kontrol et.
2. `Ozet` sekmesinde `Koruma / Kill` ve `Uyari Merkezi` alanlarina bak.
3. `Islemler` sekmesinde `Shadow Islemler`, `Bildirim Gecmisi` ve `Son Operasyon Uyarilari` alanlarini kontrol et.

## Ne Zaman Paper Moduna Donulur

- `kill switch` aktifse
- art arda API / slippage alarmlari geliyorsa
- beklenmeyen drawdown goruluyorsa
- dashboard health veya heartbeat stale duruma dusuyorsa

## Ne Zaman Botu Durdururum

- `gunluk_equity_drawdown`
- `ardisik_zararlar`
- `self_protection`
- Binance tarafinda izin / whitelist / API problemi

## API Key Rotasyonu

Bu oturumda paylasilmis olabilecek eski key pair'i iptal et.

1. Binance API Management'te mevcut key'i sil.
2. Yeni key olustur.
3. `Enable Reading` ve gerekiyorsa `Spot & Margin Trading` ac.
4. IP restriction ac.
5. Yeni degerleri sadece [`.env`](/Users/beratdal/Desktop/btc_bot_complete/.env) icine yaz.

## Hizli Komutlar

```bash
source venv312/bin/activate
python live_readiness.py
python verify_live.py
python health_report.py
python backtest.py
python walkforward.py
```
