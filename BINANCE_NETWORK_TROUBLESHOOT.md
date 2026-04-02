# Binance Ag Erisimi Sorun Giderme

Bu rehber, `Network is unreachable` veya `Tunnel connection failed: 403 Forbidden` hatalarini gidermek icindir.

## 1) Taniyi netlestir

```bash
python network_diagnostics.py
```

Beklenen:
- DNS = OK
- TCP 443 = OK
- HTTPS ping = OK
- HTTPS(no-proxy) = OK (proxy kaynakli engeli ayiklamak icin)

## 2) Proxy ayarlarini kontrol et

Bot tarafinda proxy kapatma acik olsun:

```bash
BINANCE_DISABLE_ENV_PROXY=true
```

Host seviyesinde aktif proxy degiskenlerini gor:

```bash
env | rg -i "http_proxy|https_proxy|all_proxy|no_proxy"
```

Eger zorunlu kurum proxy kullaniyorsan:
- `*.binance.com`, `*.binance.vision` icin allow/bypass tanimla
- SSL inspection varsa Binance domainleri icin bypass iste

## 3) Firewall / outbound kurali

Ag ekibinden su izinleri iste:
- outbound TCP 443
- DNS (53/udp veya kurumsal resolver)
- hedef domainler: `api.binance.com`, `api1.binance.com`, `api2.binance.com`, `testnet.binance.vision`

Hizli host testi:

```bash
python - <<'PY'
import socket
for host in ["api.binance.com","api1.binance.com","api2.binance.com"]:
    try:
        ip = socket.gethostbyname(host)
        print(host, "DNS_OK", ip)
    except Exception as e:
        print(host, "DNS_FAIL", e)
PY
```

## 3.1) Kendi basina yapabilecegin islemler (root varsa)

Proxy degiskenlerini kapat:

```bash
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="localhost,127.0.0.1,binance.com,.binance.com,binance.vision,.binance.vision"
export no_proxy="$NO_PROXY"
```

Host firewall kontrolu:

```bash
sudo ufw status
sudo iptables -S
```

Eger outbound policy kapaliysa (ortama gore degisebilir), 443 cikisini ac:

```bash
sudo ufw allow out 443/tcp
sudo ufw allow out 53
```

Route / gateway kontrolu:

```bash
ip route
ping -c 3 8.8.8.8
```

Degisiklik sonrasi tekrar dogrula:

```bash
python network_diagnostics.py
```

## 3.2) "Nereden yapacagim?" (hangi panel/host)

Kural degisikligini **botun calistigi sunucunun cikis noktasinda** yapman gerekir.

- Eger bot kendi Linux sunucunda calisiyorsa:
  - Sunucuda terminalden (`ufw`, `iptables`, `ip route`) yaparsin.
- Eger AWS ise:
  - EC2 Security Group + NACL + VPC egress kurallarinda acarsin.
- Eger GCP ise:
  - VPC Firewall Egress kurallarinda acarsin.
- Eger Azure ise:
  - NSG ve Azure Firewall egress kurallarinda acarsin.
- Eger Kubernetes ise:
  - Node egress + NetworkPolicy + varsa egress gateway/proxy tarafinda acarsin.
- Eger kurumsal proxy zorunluysa:
  - Proxy yonetim panelinde `*.binance.com` ve `*.binance.vision` icin allow/bypass tanimlarsin.

Not: Gelistirme makinesinde acman yetmez; bot hangi hostta kosuyorsa o hostun egress yolunda acilmasi gerekir.

## 4) Runtime tarafinda yeniden dogrula

```bash
python verify_live.py
python live_readiness.py
python verify_ont_live.py
```

## 5) Hala duzelmediyse

`network_diagnostics.py` ciktilarini (DNS/TCP/HTTPS) ag ekibine ilet.
Talep metnini otomatik uretmek icin:

```bash
python generate_network_access_request.py
```

Uretilen dosya: `logs/network_access_request.md`

Ozellikle su iki imza kritik:
- `TCP FAIL: [Errno 101] Network is unreachable` -> route/firewall engeli
- `HTTPS FAIL: Tunnel connection failed: 403 Forbidden` -> proxy policy engeli
