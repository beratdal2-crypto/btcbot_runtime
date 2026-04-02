#!/usr/bin/env bash
set -u

commands=(
  "python network_diagnostics.py"
  "python generate_network_access_request.py"
  "python prepare_ont_live.py"
  "timeout 240 python -u ont_do_all.py --execute"
  "python verify_ont_live.py"
  "python ont_live_status.py"
  "python verify_live.py"
  "python health_report.py"
)

overall=0
echo "Tam yeniden calistirma basladi"
for cmd in "${commands[@]}"; do
  echo
  echo "[RUN] $cmd"
  if eval "$cmd"; then
    echo "[OK]  $cmd"
  else
    rc=$?
    echo "[FAIL:$rc] $cmd"
    overall=1
  fi
done

echo
if [[ "$overall" -eq 0 ]]; then
  echo "SONUC: tum adimlar tamamlandi."
else
  echo "SONUC: bazi adimlar basarisiz (muhtemel altyapi veya piyasa/veri kosullari)."
fi
exit "$overall"
