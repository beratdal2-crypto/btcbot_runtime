# ONT Canli Gecis: Ne Yapmamiz Gerekiyor?

Bu dosya, ONTUSDT'yi canliya almak icin kalan isleri oncelik sirasi ile verir.

## 1) Altyapi engelini kaldir (zorunlu)

```bash
python network_diagnostics.py
```

Hedef:
- DNS = OK
- TCP(443) = OK
- HTTPS ping = OK

Eger FAIL ise:
- outbound 443 ac
- `*.binance.com` ve `*.binance.vision` izin listesine al
- zorunlu kurum proxy kurali varsa bot hostu icin bypass tanimla
- detayli rehber: `BINANCE_NETWORK_TROUBLESHOOT.md`

## 2) ONT ortamini hazirla

```bash
python prepare_ont_live.py
```

Bu komut:
- `logs/ont_live_prepared.env` uretir
- mevcut env ile farklari gosterir
- preflight checkleri calistirir

## 3) Teknik gate'leri kapat

```bash
python ont_do_all.py --execute
python verify_ont_live.py
python ont_live_status.py
```

Beklenen:
- `real_live_ready=true`
- `gate_reason` bos
- `blocker_list` bos veya kritik degil

## 4) Operasyonel son kontroller

```bash
python verify_live.py
python health_report.py
```

Beklenen:
- dashboard_ok=true
- kill switch kapali
- test-order asamasi yesil

## 5) Kademeli canli gecis

1. `LIVE_TEST_ORDERS=true` ile kucuk boyutta gozlem
2. en az 1 gun shadow/canli karsilastirma
3. sorun yoksa:
   - `PAPER_TRADE=false`
   - `LIVE_TEST_ORDERS=false`

## Hemen simdi tek satir ozet komutlar

```bash
python network_diagnostics.py
python ont_live_status.py
```
