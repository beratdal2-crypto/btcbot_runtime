#!/usr/bin/env bash
set -u

commands=(
  "python network_diagnostics.py"
  "python prepare_ont_live.py"
  "python ont_do_all.py --execute"
  "python verify_live.py"
  "python health_report.py"
)

overall=0
echo "ONT 5-komut calistirma basladi"
for cmd in "${commands[@]}"; do
  echo
  echo "[RUN] $cmd"
  if eval "$cmd"; then
    echo "[OK]  $cmd"
  else
    echo "[FAIL] $cmd"
    overall=1
  fi
done

echo
if [[ "$overall" -eq 0 ]]; then
  echo "SONUC: tum komutlar basariyla tamamlandi."
else
  echo "SONUC: en az bir komut basarisiz oldu (beklenen ortam kisitlari olabilir)."
fi
exit "$overall"
