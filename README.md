# BTC AI Platform (Paper Trading, Directly Runnable)

Bu proje Mac üzerinde doğrudan kurulup çalıştırılabilecek şekilde hazırlanmıştır.
Varsayılan mod güvenli tarafta kalmak için **paper trading** ve **long-only** olarak ayarlıdır.

## 1) Kurulum

```bash
chmod +x setup_local.sh deploy/daily_retrain.sh
./setup_local.sh
```

Alternatif olarak manuel kurulum:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`PAPER_TRADE=true` iken proje public market data kullandığı için anahtar girmeden de çalışabilir.
Gerçek Binance hesap özellikleri deneyeceksen `.env` içine API anahtarlarını yaz.
Arsivleyici, Binance'tan cekebildigi gercek klines verisini `logs/market_data_archive.csv` icinde biriktirir; ag sorunu varsa mevcut archive/cache ile devam eder.

## 2) Model eğitimleri

```bash
source venv/bin/activate
python archive_market_data.py
python trainer.py
python rl_train.py
```

Gunluk retrain scripti artik egitimden sonra otomatik olarak:

- `python archive_market_data.py`
- `python optimize_parameters.py`
- `python backtest.py`
- `python walkforward.py`
- `python live_readiness.py`
- `python health_report.py`
- `python live_shadow_analysis.py`
- `python daily_summary.py`
- `python security_audit.py`
- `python sqlite_store.py`
- ve ortaya cikan CSV raporlarini timestamp'li arsive

yazar.

## 3) Backtest

```bash
source venv/bin/activate
python backtest.py
```

Olusan dosyalar:

- `logs/market_data_archive.csv`
- `logs/backtest_trades.csv`
- `logs/backtest_summary.csv`
- `logs/walkforward_results.csv`
- `logs/optimization_results.csv`
- `logs/best_params.json`
- `logs/symbol_optimization_results.csv`
- `logs/symbol_best_params.json`
- `logs/symbol_training_report.csv`
- `logs/live_readiness.json`
- `logs/system_health.json`
- `logs/live_shadow_analysis.csv`
- `logs/daily_summary.json`
- `logs/security_audit.json`
- `logs/btcbot.sqlite3`
- `logs/report_archives/<timestamp>/...`

## 4) Dashboard

```bash
source venv/bin/activate
streamlit run dashboard.py
```

## 5) Botu çalıştır

```bash
source venv/bin/activate
python main.py
```

## 5.1) Binance hesabı ile bağlama

`paper` modda kalıp gerçek hesaptan bakiye/izin doğrulamak için:

```bash
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
PAPER_TRADE=true
LIVE_TRADING=false
```

Binance'a imzalı test order gonderip ama gercek emir olusturmamak icin:

```bash
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_TESTNET=false
BINANCE_BASE_ENDPOINT=1
PAPER_TRADE=false
LIVE_TRADING=true
LIVE_TEST_ORDERS=true
```

Gercek spot market order icin:

```bash
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_TESTNET=false
BINANCE_BASE_ENDPOINT=1
PAPER_TRADE=false
LIVE_TRADING=true
LIVE_TEST_ORDERS=false
ALLOW_UNRESTRICTED_API_KEY=false
```

Guvenlik notlari:

- Canli spot modunda `LONG_ONLY=true` zorunludur.
- Varsayilan olarak API key icin IP restriction beklenir. Zorlamayi kapatmak icin `ALLOW_UNRESTRICTED_API_KEY=true` gerekir.
- Emir boyutu `risk_per_trade`, `MAX_LIVE_QUOTE_PER_ORDER` ve sembol filtrelerine gore hesaplanir.
- Bu surum spot market order gonderir; restart sonrasi eldeki mevcut coin bakiyesini otomatik devralmaz.

Coklu coin tarama icin `.env` icine birden fazla sembol de yazabilirsin:

```bash
SYMBOL=BTCUSDT
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT
```

Bu modda bot tek seferde yine tek pozisyon acik tutar; her dongude listedeki coinleri tarar ve en guclu giris sinyalini secmeye calisir.
Egitim, optimizer, backtest ve walk-forward akislari da ayni `SYMBOLS` listesi uzerinden toplu calisabilir.

## 5.2) BinanceTR'ye otomatik USDT aktarim

`free USDT >= 100` oldugunda bakiyenin yarisini BinanceTR adresine gondermek icin:

```bash
AUTO_TRANSFER_ENABLED=true
AUTO_TRANSFER_DRY_RUN=true
AUTO_TRANSFER_ASSET=USDT
AUTO_TRANSFER_TRIGGER_BALANCE=100
AUTO_TRANSFER_FRACTION=0.5
AUTO_TRANSFER_RESET_BALANCE=90
AUTO_TRANSFER_NETWORK=TRX
AUTO_TRANSFER_ADDRESS=BINANCETR_USDT_ADRESI
AUTO_TRANSFER_ADDRESS_NAME=BinanceTR
```

Notlar:

- Varsayilan olarak `AUTO_TRANSFER_DRY_RUN=true` gelir; once boyle test etmek daha guvenlidir.
- Canli cekim icin Binance API key'inde `withdraw` yetkisi gerekir.
- Ag adini Binance withdraw tarafinda gecerli olan degerle yazmalisin. `USDT` icin bu cogu zaman `TRX`, `BSC` veya `ETH` olur.
- Bot acik pozisyondayken transfer denemez.

## 5.3) Telegram bildirimleri

Telegram uyarilarini acmak icin `.env` icine sunlari yaz:

```bash
NOTIFICATION_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
NOTIFICATION_TIMEOUT_SECONDS=8
```

Bildirim giden olaylar:

- pozisyon acilisi
- pozisyon kapanisi
- watchdog restart
- kill switch
- otomatik transfer

Not:

- `TELEGRAM_CHAT_ID` degeri botun mesaj gonderecegi sohbet veya kullanici kimligidir.
- Token ve chat id girilmeden bildirim sistemi sadece yerel log yazar.

## 6) Mac'te otomatik çalıştırma

Botu girişte otomatik başlatmak ve günlük yeniden eğitim yapmak için:

```bash
chmod +x deploy/run_bot.sh deploy/daily_retrain.sh
rsync -a --delete /Users/beratdal/Desktop/btc_bot_complete/ ~/btcbot_runtime/
cp deploy/com.berat.btcbot.runner.plist ~/Library/LaunchAgents/
cp deploy/com.berat.btcbot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.runner.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.plist
```

`launchd`, Desktop klasörüne erişimde takılabildiği için runtime kopyası `~/btcbot_runtime/` altında tutulur.
Log dosyaları `~/btcbot_runtime/logs/bot.out`, `~/btcbot_runtime/logs/bot.err`, `~/btcbot_runtime/logs/retrain.out`, `~/btcbot_runtime/logs/retrain.err` altında oluşur.
Retrain sonrasi performans raporlari da `~/btcbot_runtime/logs/report_archives/` altina tarihli klasorler halinde yazilir.

Dashboard'ı da servis olarak açmak için:

```bash
chmod +x deploy/run_dashboard.sh
rsync -a --delete /Users/beratdal/Desktop/btc_bot_complete/ ~/btcbot_runtime/
cp deploy/com.berat.btcbot.dashboard.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.dashboard.plist
```

Dashboard varsayılan olarak `http://127.0.0.1:8501` adresinde yayın yapar.
Log dosyaları `~/btcbot_runtime/logs/dashboard.out` ve `~/btcbot_runtime/logs/dashboard.err` altındadır.

Websocket ticker collector'u da servis olarak acmak istersen:

```bash
chmod +x deploy/run_websocket.sh
rsync -a --delete /Users/beratdal/Desktop/btc_bot_complete/ ~/btcbot_runtime/
cp deploy/com.berat.btcbot.websocket.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.websocket.plist
```

Bu servis `logs/websocket_cache.json` dosyasini taze tutar; bot `WEBSOCKET_ENABLED=true` iken fiyat ve spread tarafinda bunu tercih eder.

Dashboard'ı girişte otomatik tarayıcıda açmak için:

```bash
chmod +x deploy/open_dashboard.sh
cp deploy/com.berat.btcbot.dashboard.open.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.dashboard.open.plist
```

Market data archive gorevini saatlik calistirmak icin:

```bash
chmod +x deploy/run_archive.sh
rsync -a --delete /Users/beratdal/Desktop/btc_bot_complete/ ~/btcbot_runtime/
cp deploy/com.berat.btcbot.archive.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.berat.btcbot.archive.plist
```

Bu gorev `logs/market_data_archive.csv` dosyasini saatlik gunceller.

## Önemli notlar

- Varsayılan olarak gerçek emir göndermez.
- Paper trading modunda veri kaynağı olarak daha stabil olduğu için Binance mainnet public market data kullanılır.
- Spot kullanım mantığıyla tasarlandı.
- Kısa pozisyon simülasyonu kapalıdır (`LONG_ONLY=true`).
- `deploy/com.berat.btcbot.plist` bu klasörün mevcut konumuna göre ayarlanmıştır. Klasörü taşırsan yolları tekrar güncelle.
- Bu iskelet gerçek para öncesi uzun test gerektirir.

## Operasyon Dosyalari

- [RUNBOOK.md](/Users/beratdal/Desktop/btc_bot_complete/RUNBOOK.md)
- [LIVE_CHECKLIST.md](/Users/beratdal/Desktop/btc_bot_complete/LIVE_CHECKLIST.md)

Canliya gecmeden once:

```bash
source venv312/bin/activate
python live_readiness.py
python verify_live.py
python health_report.py
```
