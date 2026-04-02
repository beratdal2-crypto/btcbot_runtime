from __future__ import annotations

import pandas as pd


def build_system_advice(
    backtest_summary: pd.DataFrame | None,
    walkforward: pd.DataFrame | None,
    coin_scores: pd.DataFrame | None,
    security_audit: dict | None,
    live_readiness: dict | None,
) -> dict:
    status = "HEALTHY"
    headline = "Sistem dengeli gorunuyor."
    actions: list[str] = []

    if security_audit and int(security_audit.get("finding_count", 0)) > 0:
        status = "STOP"
        headline = "Guvenlik bulgusu var; once bunu temizle."
        actions.append("API key/secret veya benzeri hassas verileri temizle.")

    if live_readiness and not bool(live_readiness.get("api_keys_present", False)):
        actions.append("Canliya donmeden once yeni Binance key/secret tanimla.")

    if backtest_summary is not None and not backtest_summary.empty:
        row = backtest_summary.iloc[-1]
        bt_return = float(row.get("total_return_pct", 0.0))
        max_dd = float(row.get("max_drawdown_pct", 0.0))
        if bt_return < 0 or max_dd >= 10:
            status = "CAUTION" if status != "STOP" else status
            headline = "Arastirma hattinda edge zayif; canli riski buyutme."
            actions.append("Optimizer ve coin elemesini yeniden kos.")
        if max_dd >= 14:
            status = "STOP"
            headline = "Drawdown yuksek; canli buyuk notional uygun degil."
            actions.append("Pozisyon boyutunu dusur veya paper modda kal.")

    if walkforward is not None and not walkforward.empty:
        wf_return = float(pd.to_numeric(walkforward.get("total_return_pct"), errors="coerce").fillna(0.0).mean())
        wf_negative_ratio = float((pd.to_numeric(walkforward.get("total_return_pct"), errors="coerce").fillna(0.0) < 0).mean())
        if wf_return < 0 or wf_negative_ratio > 0.5:
            status = "CAUTION" if status != "STOP" else status
            actions.append("Negatif fold oranini dusurmeden coin listesini genisletme.")

    if coin_scores is not None and not coin_scores.empty:
        blocked = coin_scores[coin_scores.get("hard_block") == True]
        eligible = coin_scores[coin_scores.get("eligible") == True]
        if len(blocked) >= max(2, len(coin_scores) // 3):
            status = "CAUTION" if status != "STOP" else status
            actions.append("Hard-block alan coinleri aktif taramadan cikar.")
        if eligible.empty:
            status = "STOP"
            headline = "Uygun coin kalmamis; sistem islem acmamalı."
            actions.append("Coin skorlarini yenilemeden canli moda gecme.")

    if not actions:
        actions.append("Kucuk notional ile test-order veya paper modda izlemeye devam et.")

    return {
        "status": status,
        "headline": headline,
        "actions": actions[:4],
    }
