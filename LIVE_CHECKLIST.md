# Canli Kullanim Checklist

## Zorunlu

- [ ] Binance API key/secret yeni ve gecerli
- [ ] IP whitelist aktif
- [ ] `verify_live.py` temiz geciyor
- [ ] Dashboard aciliyor
- [ ] `health_report.py` icinde `dashboard_ok=true`
- [ ] `kill_switch` pasif
- [ ] `shadow_mode` acik

## Kademeli Gecis

1. `LIVE_TEST_ORDERS=true`
2. kucuk bakiye ile gozlem
3. shadow ve canli loglari kiyasla
4. sorun yoksa `LIVE_TEST_ORDERS=false`

## Gozlem

- ilk canli gunlerde buyuk boyut kullanma
- `Order audit`, `alerts`, `shadow trades` ve `coin contribution` dosyalarini izle
- `slippage` ve `second_validation` skip oranlari normal mi bak
