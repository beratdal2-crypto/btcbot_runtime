#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_ROOT"

python3 -m venv venv
source "$PROJECT_ROOT/venv/bin/activate"
pip install -r requirements.txt

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo ".env dosyasi olusturuldu. Binance anahtarlarini girmeyi unutma."
fi

python3 tests/smoke_test.py

echo "Kurulum tamam. Sonraki adimlar:"
echo "1) Paper trading icin .env dosyasini varsayilan haliyle kullanabilirsin"
echo "   Gercek Binance hesap ozellikleri ekleyeceksen BINANCE_API_KEY ve BINANCE_API_SECRET degerlerini yaz"
echo "2) python trainer.py"
echo "3) python rl_train.py"
echo "4) python main.py"
