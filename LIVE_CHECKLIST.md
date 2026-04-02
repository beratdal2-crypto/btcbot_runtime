# Canli Kullanim Checklist

Hizli aksiyon plani icin: `ONT_NEXT_STEPS.md`

## Zorunlu

- [ ] Binance API key/secret yeni ve gecerli
- [ ] IP whitelist aktif
- [ ] `verify_live.py` temiz geciyor
- [ ] `verify_ont_live.py` ciktisinda `real_live_ready=true`
- [ ] Dashboard aciliyor
- [ ] `health_report.py` icinde `dashboard_ok=true`
- [ ] `kill_switch` pasif
- [ ] `shadow_mode` acik

## ONTUSDT canliya gecis ayarlari

`.env` icin minimum:

```bash
SYMBOL=ONTUSDT
PRIMARY_SYMBOL=ONTUSDT
SYMBOLS=ONTUSDT
ALT_RESEARCH_SYMBOLS=XRPUSDT,ONTUSDT
LIVE_TRADING=true
LIVE_TEST_ORDERS=true
PAPER_TRADE=true
BINANCE_TESTNET=false
```

Not:
- `LIVE_TEST_ORDERS=true` iken bot canli endpointte test order mantiginda calisir.
- Gercek emirden once `PAPER_TRADE=false` yap.

## Komut sirasi (canliya almadan hemen once)

```bash
python live_readiness.py
python verify_ont_live.py
python verify_live.py
python health_report.py
```

Hepsi temizse ve `verify_ont_live.py` icinde `real_live_ready=true` ise bir sonraki adima gec.

Istersen bu adimlari tek komutla da kosabilirsin:

```bash
python ont_go_live.py
```

Bu komut `logs/ont_live_checklist.json` icindeki `remediation_steps` alanini da yazdirir; gate yesile cevirmek icin hangi maddeyi kapatman gerektigini dogrudan gorursun.

Tum teknik adimlari tek planda gormek (ve istersen otomatik calistirmak) icin:

```bash
python ont_do_all.py
python ont_do_all.py --execute
```

Dis ag acikligini dogrulamak icin:

```bash
python network_diagnostics.py
```

Anlik ONT canli durum ozeti icin:

```bash
python ont_live_status.py
```

Canli gecis icin tek seferde hazirlik + preflight calistirmak icin:

```bash
python prepare_ont_live.py
```

## Kademeli Gecis

1. `LIVE_TEST_ORDERS=true`
2. kucuk bakiye ile gozlem
3. shadow ve canli loglari kiyasla
4. sorun yoksa:
   - `PAPER_TRADE=false`
   - `LIVE_TEST_ORDERS=false`
5. ilk 24 saat `MAX_LIVE_QUOTE_PER_ORDER` dusuk tutulur (ornek: 10-25 USDT)

## Gozlem

- ilk canli gunlerde buyuk boyut kullanma
- `Order audit`, `alerts`, `shadow trades` ve `coin contribution` dosyalarini izle
- `slippage` ve `second_validation` skip oranlari normal mi bak
