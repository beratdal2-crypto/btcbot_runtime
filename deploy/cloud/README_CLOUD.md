# Cloud Worker Deploy (No Local Disk Usage)

Bu botu yerelde calistirmak yerine bulutta long-running worker olarak calistir.

## 1) Gerekli ortam degiskenleri

Asagidakileri cloud paneline ENV olarak gir:

- BINANCE_API_KEY
- BINANCE_API_SECRET
- BINANCE_TLD=me
- BINANCE_TESTNET=false
- BINANCE_DISABLE_ENV_PROXY=true
- SYMBOL=ONTUSDT
- PRIMARY_SYMBOL=ONTUSDT
- SYMBOLS=ONTUSDT
- ALT_RESEARCH_SYMBOLS=XRPUSDT,ONTUSDT
- LIVE_TRADING=true
- LIVE_TEST_ORDERS=true
- PAPER_TRADE=false
- LONG_ONLY=true
- MAX_LIVE_QUOTE_PER_ORDER=25

## 2) Build/Run

Container build:

- Build command: default (Dockerfile)
- Start command: `python main.py`

## 3) Cloud provider notlari

- Render/Railway/Fly benzeri platformlarda "Worker" (web degil) sec.
- Persistent disk zorunlu degil; loglar platform loglarina akar.
- Health check icin periyodik `python health_report.py` job'i eklenebilir.

## 4) Guvenli gecis

- Ilk asamada `LIVE_TEST_ORDERS=true` kalmali.
- Gercek emre gecmeden once `verify_live.py` ve `verify_ont_live.py` cloud ortaminda temiz olmali.
- Sonra `LIVE_TEST_ORDERS=false` yap.
