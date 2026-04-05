from __future__ import annotations

import json
import os
from pathlib import Path
import time

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from alerts import load_recent_alerts
from coin_runtime import load_cooldown_state_frame
from coin_scores import select_tradeable_symbols
from comparison_report import build_live_paper_comparison
from config import SETTINGS
from data import get_free_asset_balance, load_websocket_snapshot
from system_advisor import build_system_advice


st.set_page_config(page_title="BTC Bot Panel", layout="wide")

COLORS = {
    "green": "#0f766e",
    "green_fill": "#ccfbf1",
    "blue": "#2563eb",
    "blue_fill": "#dbeafe",
    "amber": "#d97706",
    "amber_fill": "#fef3c7",
    "red": "#dc2626",
    "red_fill": "#fee2e2",
    "purple": "#7c3aed",
    "purple_fill": "#ede9fe",
    "slate": "#475569",
    "grid": "#cbd5e1",
}


def load_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return None if df.empty else df


def load_json(path: str) -> dict | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def format_metric(value, suffix: str = "", decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{decimals}f}{suffix}"


def latest_report_archives(limit: int = 5) -> list[Path]:
    archive_dir = Path(SETTINGS.report_archive_dir)
    if not archive_dir.exists():
        return []
    dirs = [path for path in archive_dir.iterdir() if path.is_dir()]
    return sorted(dirs, reverse=True)[:limit]


def describe_transfer_state(state: dict | None) -> tuple[str, str]:
    if not SETTINGS.auto_transfer_enabled:
        return "Kapalı", "Otomatik transfer kapalı."
    if state is None:
        return "Hazır", "Eşik bekleniyor."
    armed = bool(state.get("armed", True))
    last_transfer_at = float(state.get("last_transfer_at", 0.0))
    if armed:
        return "Hazır", "Transfer sistemi tetik için hazır."
    if not last_transfer_at:
        return "Bekliyor", "Son transfer zamanı bulunamadı."
    elapsed = max(0, int(time.time() - last_transfer_at))
    cooldown_left = max(0, SETTINGS.auto_transfer_min_interval_seconds - elapsed)
    if cooldown_left > 0:
        return "Bekleme", f"{cooldown_left // 60} dk bekleme var."
    return "Tetiklendi", "Reset bakiyesi bekleniyor olabilir."


def collect_data() -> dict:
    return {
        "trades": load_csv(SETTINGS.trade_log_path),
        "heartbeat": load_csv(SETTINGS.heartbeat_log_path),
        "equity": load_csv(SETTINGS.equity_log_path),
        "candidate_signals": load_csv(SETTINGS.candidate_signal_log_path),
        "near_candidate_signals": load_csv(SETTINGS.near_candidate_signal_log_path),
        "signal_readiness": load_csv(SETTINGS.signal_readiness_log_path),
        "backtest_summary": load_csv(SETTINGS.backtest_summary_path),
        "backtest_trades": load_csv(SETTINGS.backtest_trades_path),
        "walkforward": load_csv(SETTINGS.walkforward_results_path),
        "best_params": load_json(SETTINGS.best_params_path),
        "training_report": load_json(SETTINGS.training_report_path),
        "feature_importance": load_csv(SETTINGS.feature_importance_path),
        "coin_scores": load_csv(SETTINGS.coin_scores_path),
        "cooldowns": load_cooldown_state_frame(),
        "watchdog_state": load_json(SETTINGS.watchdog_state_path),
        "transfer_logs": load_csv(SETTINGS.auto_transfer_log_path),
        "transfer_state": load_json(SETTINGS.auto_transfer_state_path),
        "comparison": load_csv(SETTINGS.live_paper_comparison_path),
        "portfolio_report": load_json(SETTINGS.portfolio_report_path),
        "portfolio_periods": load_csv(SETTINGS.portfolio_periods_path),
        "coin_contribution": load_csv(SETTINGS.coin_contribution_path),
        "symbol_training_report": load_csv(SETTINGS.symbol_training_report_path),
        "alerts": load_recent_alerts(),
        "self_protection": load_json(SETTINGS.self_protection_state_path),
        "kill_switch": load_json(SETTINGS.kill_switch_state_path),
        "notifications": load_csv(SETTINGS.notification_log_path),
        "shadow_trades": load_csv(SETTINGS.shadow_trade_log_path),
        "system_health": load_json(SETTINGS.system_health_path),
        "live_readiness": load_json(SETTINGS.live_readiness_path),
        "symbol_optimization": load_csv(SETTINGS.symbol_optimization_results_path),
        "daily_summary": load_json(SETTINGS.daily_summary_path),
        "live_shadow_analysis": load_csv(SETTINGS.live_shadow_analysis_path),
        "security_audit": load_json(SETTINGS.security_audit_path),
    }


def config_summary_table() -> pd.DataFrame:
    rows = [
        {"ayar": "Live Trading", "değer": SETTINGS.live_trading},
        {"ayar": "Test Order", "değer": SETTINGS.live_test_orders},
        {"ayar": "Shadow Mode", "değer": SETTINGS.shadow_mode_enabled},
        {"ayar": "Websocket", "değer": SETTINGS.websocket_enabled},
        {"ayar": "Prefer Limit Entry", "değer": SETTINGS.prefer_limit_entry},
        {"ayar": "Risk / Trade", "değer": f"{SETTINGS.risk_per_trade:.2%}"},
        {"ayar": "Max Order Quote", "değer": SETTINGS.max_live_quote_per_order},
        {"ayar": "Sembol Sayısı", "değer": len(SETTINGS.trading_symbols())},
        {"ayar": "Auto Transfer", "değer": SETTINGS.auto_transfer_enabled},
        {"ayar": "Notifications", "değer": SETTINGS.notification_enabled},
    ]
    return pd.DataFrame(rows)


def quick_guide_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Bölüm": "Özet", "Gösterilen": "Canlı equity", "Anlamı": "Toplam portföy değerini gösterir."},
            {"Bölüm": "Özet", "Gösterilen": "Günlük PnL", "Anlamı": "Bugünkü kâr/zarar durumunu gösterir."},
            {"Bölüm": "Özet", "Gösterilen": "Son karar", "Anlamı": "Botun en son verdiği ana kararı gösterir."},
            {"Bölüm": "İşlemler", "Gösterilen": "Son işlemler", "Anlamı": "En son açılan ve kapanan işlemleri listeler."},
            {"Bölüm": "İşlemler", "Gösterilen": "Cooldown durumu", "Anlamı": "Geçici devre dışı kalan coinleri gösterir."},
            {"Bölüm": "İşlemler", "Gösterilen": "Kümülatif kâr", "Anlamı": "İşlem performansının toplam etkisini gösterir."},
            {"Bölüm": "Model", "Gösterilen": "Backtest özeti", "Anlamı": "Stratejinin geçmiş test performansını gösterir."},
            {"Bölüm": "Model", "Gösterilen": "Eğitim raporu", "Anlamı": "Model kalitesi ve doğruluk metriklerini özetler."},
            {"Bölüm": "Model", "Gösterilen": "Coin skorları", "Anlamı": "Hangi coinlerin daha güçlü olduğunu gösterir."},
            {"Bölüm": "Model", "Gösterilen": "Son 7 gün performansı", "Anlamı": "Yakın dönemde hangi coinlerin daha iyi gittiğini gösterir."},
            {"Bölüm": "Özet", "Gösterilen": "Uyarı Merkezi", "Anlamı": "Canlı hatalar, slippage ve risk uyarılarını listeler."},
        ]
    )


def recent_error_rows(limit: int = 12) -> pd.DataFrame | None:
    rows: list[dict] = []
    for source, path in [
        ("bot.err", "/Users/beratdal/btcbot_runtime/logs/bot.err"),
        ("dashboard.err", "/Users/beratdal/btcbot_runtime/logs/dashboard.err"),
    ]:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                for line in f.readlines()[-limit:]:
                    line = line.strip()
                    if line:
                        rows.append({"kaynak": source, "detay": line})
        except OSError:
            continue
    return None if not rows else pd.DataFrame(rows[-limit:])


def compute_health_status(backtest_summary: pd.DataFrame | None, walkforward: pd.DataFrame | None) -> tuple[str, str, list[str]]:
    if backtest_summary is None or backtest_summary.empty:
        return "VERİ YOK", COLORS["slate"], ["Backtest özeti yok."]

    row = backtest_summary.iloc[-1]
    bt_return = float(row.get("total_return_pct", 0.0))
    max_dd = float(row.get("max_drawdown_pct", 0.0))
    trade_count = int(row.get("trade_count", 0))

    messages = [f"Backtest işlem: {trade_count}", f"Backtest getiri: {bt_return:.2f}%", f"Max DD: {max_dd:.2f}%"]
    status = "SAĞLIKLI"
    color = COLORS["green"]

    if bt_return < 0 or max_dd >= 8 or trade_count == 0:
        status = "DİKKAT"
        color = COLORS["amber"]
    if bt_return < -1 or max_dd >= 15:
        status = "DUR"
        color = COLORS["red"]

    if walkforward is not None and not walkforward.empty:
        wf_return = float(walkforward["total_return_pct"].mean())
        messages.append(f"WF ort. getiri: {wf_return:.2f}%")
        if wf_return < 0 and status == "SAĞLIKLI":
            status = "DİKKAT"
            color = COLORS["amber"]
    return status, color, messages


def style_axes(ax) -> None:
    ax.grid(alpha=0.20, color=COLORS["grid"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def symbol_gate_summary(coin_scores: pd.DataFrame | None) -> tuple[str, str, str, str]:
    primary = SETTINGS.primary_symbol()
    secondary = ", ".join(SETTINGS.secondary_symbols()) or "-"
    selected, scoped = select_tradeable_symbols()
    selected_label = ", ".join(selected) if selected else "Yok"

    reasons: list[str] = []
    if scoped is not None and not scoped.empty:
        for symbol in [primary, *SETTINGS.secondary_symbols()]:
            row = scoped.loc[scoped["symbol"] == symbol]
            if row.empty:
                continue
            item = row.iloc[0]
            if symbol in selected:
                continue
            reason = str(item.get("reason", "pasif"))
            reasons.append(f"{symbol}: {reason}")
    reason_label = " | ".join(reasons[:4]) if reasons else "Aktif engel yok."
    return primary, secondary, selected_label, reason_label


def current_live_gate_snapshot(live_readiness: dict, symbol: str) -> dict:
    gate = ((live_readiness or {}).get("live_deployment_gate") or {}).get(symbol, {}) or {}
    profile = str(gate.get("profile", "-"))
    strict_ok = bool(gate.get("strict_ok", gate.get("ok", False)))
    candidate_ok = bool(gate.get("candidate_ok", False))
    candidate_score = int(gate.get("candidate_score", 0) or 0)
    conditions = gate.get("conditions", {}) or {}
    balance = conditions.get("balance", {}) or {}
    quote_balance = balance.get("quote_balance")
    return {
        "profile": profile,
        "strict_label": "AÇIK" if strict_ok else "KAPALI",
        "candidate_label": "ADAY" if candidate_ok else "DEĞİL",
        "candidate_score": candidate_score,
        "quote_balance": quote_balance,
        "reason": str(gate.get("reason", "-")) or "-",
        "conditions": conditions,
    }


def live_gate_condition_frame(snapshot: dict) -> pd.DataFrame | None:
    conditions = snapshot.get("conditions") or {}
    if not conditions:
        return None
    rows: list[dict] = []
    labels = {
        "quick_validation": "Quick",
        "walkforward": "Walk-forward",
        "backtest": "Backtest",
        "guards": "Guards",
        "balance": "Bakiye",
    }
    for key in ["quick_validation", "walkforward", "backtest", "guards", "balance"]:
        condition = conditions.get(key) or {}
        rows.append(
            {
                "Başlık": labels.get(key, key),
                "Durum": str(condition.get("status", "fail")).upper(),
                "Detay": str(condition.get("reason", "")) or "-",
            }
        )
    return pd.DataFrame(rows)


def backup_candidate_frame(live_readiness: dict) -> pd.DataFrame | None:
    backups = (live_readiness or {}).get("backup_altcoin_candidates") or []
    if not backups:
        return None
    rows: list[dict[str, object]] = []
    gates = (live_readiness or {}).get("backup_candidate_live_gate") or {}
    for item in backups:
        symbol = str(item.get("symbol", "-"))
        gate = gates.get(symbol, {}) or {}
        rows.append(
            {
                "Sembol": symbol,
                "Profil": str(item.get("profile", "-")),
                "Backtest": format_metric(item.get("bt_total_return_pct"), "%"),
                "PF": format_metric(item.get("bt_profit_factor"), decimals=3),
                "Trade": int(item.get("bt_trade_count", 0) or 0),
                "Durum": "STRICT" if gate.get("strict_ok") else "ADAY" if gate.get("candidate_ok") else "BLOK",
            }
        )
    return pd.DataFrame(rows)


def render_overview(data: dict) -> None:
    st.subheader("Özet")

    trades = data["trades"]
    heartbeat = data["heartbeat"]
    equity = data["equity"]
    candidate_signals = data["candidate_signals"]
    near_candidate_signals = data["near_candidate_signals"]
    signal_readiness = data["signal_readiness"]
    comparison = data["comparison"] if data["comparison"] is not None else build_live_paper_comparison()
    backtest_summary = data["backtest_summary"]
    walkforward = data["walkforward"]
    watchdog_state = data["watchdog_state"]
    portfolio_report = data["portfolio_report"] or {}
    portfolio_periods = data["portfolio_periods"]
    alerts = data["alerts"]
    self_protection = data["self_protection"] or {}
    kill_switch = data["kill_switch"] or {}
    system_health = data["system_health"] or {}
    live_readiness = data["live_readiness"] or {}
    daily_summary = data["daily_summary"] or {}
    security_audit = data["security_audit"] or {}
    websocket_state = load_websocket_snapshot()
    primary_symbol, secondary_symbols, selected_symbols, symbol_gate_reason = symbol_gate_summary(data["coin_scores"])
    system_advice = build_system_advice(
        backtest_summary=backtest_summary,
        walkforward=walkforward,
        coin_scores=data["coin_scores"],
        security_audit=security_audit,
        live_readiness=live_readiness,
    )
    free_usdt = get_free_asset_balance(SETTINGS.auto_transfer_asset) if SETTINGS.auto_transfer_enabled else None
    transfer_status, transfer_detail = describe_transfer_state(data["transfer_state"])
    live_gate_snapshot = current_live_gate_snapshot(live_readiness, primary_symbol)

    top = st.columns(6)
    top[0].metric("Canlı Equity", format_metric(equity.iloc[-1]["equity_usdt"]) if equity is not None and not equity.empty else "-")
    top[1].metric("Günlük PnL", format_metric(float(equity.iloc[-1]["daily_pnl_pct"]) * 100, "%") if equity is not None and not equity.empty else "-")
    top[2].metric("Son Karar", str(heartbeat.iloc[-1]["decision"]) if heartbeat is not None and not heartbeat.empty else "-")
    top[3].metric("Serbest USDT", format_metric(free_usdt) if free_usdt is not None else "-")
    top[4].metric("Transfer", transfer_status)
    top[5].metric("Watchdog", str(watchdog_state.get("last_reason", "-")) if watchdog_state else "-")
    st.caption(transfer_detail)

    portfolio_row = st.columns(4)
    portfolio_row[0].metric("7g Getiri", format_metric(portfolio_report.get("week_return_pct"), "%"))
    portfolio_row[1].metric("30g Getiri", format_metric(portfolio_report.get("month_return_pct"), "%"))
    portfolio_row[2].metric("Ort. Slippage", format_metric(portfolio_report.get("avg_slippage_bps"), " bps"))
    portfolio_row[3].metric("Koruma / Kill", f"{str(self_protection.get('mode', 'normal')).upper()} / {str(kill_switch.get('reason', 'ok')).upper()}")
    readiness = st.columns(3)
    readiness[0].metric("Dashboard Health", "OK" if system_health.get("dashboard_ok") else "WARN")
    readiness[1].metric("Heartbeat Age", format_metric(system_health.get("heartbeat_age_seconds"), " sn", decimals=0))
    readiness_label = "STRICT" if live_gate_snapshot["strict_label"] == "AÇIK" else "ADAY" if live_gate_snapshot["candidate_label"] == "ADAY" else "BLOK"
    readiness[2].metric("Canli Hazirlik", readiness_label if live_readiness.get("api_keys_present") else "EKSİK")
    summary_row = st.columns(4)
    summary_row[0].metric("Günlük Özet İşlem", int(daily_summary.get("closed_trade_count", 0)))
    summary_row[1].metric("Net K/Z", format_metric(daily_summary.get("net_profit_pct"), "%"))
    summary_row[2].metric("Live-Shadow Gap", format_metric(daily_summary.get("live_vs_shadow_gap_pct"), "%"))
    summary_row[3].metric("Websocket", "AKTİF" if websocket_state else "REST")

    st.markdown("#### Sembol Kapısı")
    gate_cols = st.columns(3)
    gate_cols[0].metric("Ana Sembol", primary_symbol)
    gate_cols[1].metric("İkinciller", secondary_symbols)
    gate_cols[2].metric("Aktif Seçilen", selected_symbols)
    st.caption(symbol_gate_reason)

    st.markdown("#### Live Gate Özeti")
    live_cols = st.columns(4)
    live_cols[0].metric("Strict Live", live_gate_snapshot["strict_label"])
    live_cols[1].metric("Candidate", live_gate_snapshot["candidate_label"])
    live_cols[2].metric("Aday Skoru", live_gate_snapshot["candidate_score"])
    live_cols[3].metric("Aktif Profil", live_gate_snapshot["profile"])
    if live_gate_snapshot["quote_balance"] is not None:
        st.caption(
            f"Bakiye: {format_metric(live_gate_snapshot['quote_balance'])} | Neden: {live_gate_snapshot['reason']}"
        )
    else:
        st.caption(f"Neden: {live_gate_snapshot['reason']}")
    condition_frame = live_gate_condition_frame(live_gate_snapshot)
    if condition_frame is not None:
        st.dataframe(condition_frame, use_container_width=True, hide_index=True)

    backup_frame = backup_candidate_frame(live_readiness)
    if backup_frame is not None:
        st.markdown("#### Yedek Altcoin Adayları")
        st.dataframe(backup_frame, use_container_width=True, hide_index=True)

    advice_color = {
        "HEALTHY": COLORS["green"],
        "CAUTION": COLORS["amber"],
        "STOP": COLORS["red"],
    }.get(system_advice["status"], COLORS["slate"])
    st.markdown(
        f"""
        <div style="padding:14px 16px;border-radius:14px;background:{advice_color}14;border:1px solid {advice_color};margin:8px 0 16px 0;">
          <div style="font-size:12px;color:{advice_color};font-weight:700;letter-spacing:0.08em;">OTOMATIK ONERI</div>
          <div style="font-size:22px;color:{advice_color};font-weight:800;margin-top:4px;">{system_advice['status']}</div>
          <div style="font-size:14px;color:{advice_color};margin-top:8px;">{system_advice['headline']}</div>
          <div style="font-size:13px;color:{advice_color};margin-top:8px;">{' | '.join(system_advice['actions'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status, status_color, messages = compute_health_status(backtest_summary, walkforward)
    st.markdown(
        f"""
        <div style="padding:14px 16px;border-radius:14px;background:{status_color}18;border:1px solid {status_color};margin:8px 0 16px 0;">
          <div style="font-size:12px;color:{status_color};font-weight:700;letter-spacing:0.08em;">GENEL DURUM</div>
          <div style="font-size:26px;color:{status_color};font-weight:800;margin-top:4px;">{status}</div>
          <div style="font-size:14px;color:{status_color};margin-top:8px;">{' | '.join(messages)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("#### Equity Eğrisi")
        if equity is not None and {"time", "equity_usdt"}.issubset(equity.columns):
            plot_df = equity.copy()
            plot_df["time"] = pd.to_datetime(plot_df["time"], errors="coerce", utc=True)
            fig, ax = plt.subplots(figsize=(8, 3.6))
            ax.plot(plot_df["time"], plot_df["equity_usdt"], color=COLORS["green"], linewidth=2.2)
            ax.fill_between(plot_df["time"], plot_df["equity_usdt"], color=COLORS["green_fill"], alpha=0.5)
            style_axes(ax)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Equity verisi yok.")
    with right:
        st.markdown("#### Uyarı Merkezi")
        if alerts is not None and not alerts.empty:
            st.dataframe(alerts.tail(12), use_container_width=True, hide_index=True)
        else:
            errors = recent_error_rows()
            if errors is not None:
                st.dataframe(errors, use_container_width=True, hide_index=True)
            else:
                st.info("Aktif hata görünmüyor.")

    st.markdown("#### Candidate Sinyaller")
    if candidate_signals is not None and not candidate_signals.empty:
        st.dataframe(candidate_signals.tail(12), use_container_width=True, hide_index=True)
    else:
        st.info("Aday sinyal henüz yok.")

    st.markdown("#### Near-Candidate Sinyaller")
    if near_candidate_signals is not None and not near_candidate_signals.empty:
        st.dataframe(near_candidate_signals.tail(12), use_container_width=True, hide_index=True)
    else:
        st.info("Near-candidate sinyal henüz yok.")

    st.markdown("#### Güçlü Sinyal Hazırlığı")
    if signal_readiness is not None and not signal_readiness.empty:
        st.dataframe(signal_readiness.tail(12), use_container_width=True, hide_index=True)
    else:
        st.info("Güçlü sinyal hazırlık verisi henüz yok.")

    st.markdown("#### Live / Paper Karşılaştırması")
    if comparison is not None and not comparison.empty:
        st.dataframe(comparison, use_container_width=True, hide_index=True)
    else:
        st.info("Karşılaştırma verisi yok.")

    st.markdown("#### Portföy Dönem Getirileri")
    if portfolio_periods is not None and not portfolio_periods.empty:
        fig, ax = plt.subplots(figsize=(8, 3.0))
        colors = [COLORS["green"] if value >= 0 else COLORS["red"] for value in portfolio_periods["return_pct"]]
        ax.bar(portfolio_periods["period"], portfolio_periods["return_pct"], color=colors)
        ax.axhline(0, color=COLORS["grid"], linewidth=1, linestyle="--")
        style_axes(ax)
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.info("Dönem getirisi verisi yok.")

    extra_overview_left, extra_overview_right = st.columns(2)
    with extra_overview_left:
        st.markdown("#### Güvenlik Özeti")
        if security_audit:
            st.metric("Bulgu Sayısı", int(security_audit.get("finding_count", 0)))
            findings = pd.DataFrame(security_audit.get("findings", [])).head(8)
            if not findings.empty:
                st.dataframe(findings, use_container_width=True, hide_index=True)
            else:
                st.info("Bulgu görünmüyor.")
        else:
            st.info("Güvenlik özeti yok.")
    with extra_overview_right:
        st.markdown("#### Ayar Özeti")
        st.dataframe(config_summary_table(), use_container_width=True, hide_index=True)


def render_trading(data: dict) -> None:
    st.subheader("İşlemler")

    trades = data["trades"]
    heartbeat = data["heartbeat"]
    cooldowns = data["cooldowns"]
    transfer_logs = data["transfer_logs"]
    alerts = data["alerts"]
    notifications = data["notifications"]
    shadow_trades = data["shadow_trades"]
    free_usdt = get_free_asset_balance(SETTINGS.auto_transfer_asset) if SETTINGS.auto_transfer_enabled else None
    transfer_status, _ = describe_transfer_state(data["transfer_state"])

    metrics = st.columns(5)
    if trades is not None and not trades.empty:
        trades = trades.copy()
        trades["cum_profit_pct"] = trades["profit_pct"].cumsum()
        metrics[0].metric("İşlem Sayısı", len(trades))
        metrics[1].metric("Kümülatif K/Z", format_metric(trades["cum_profit_pct"].iloc[-1] * 100, "%"))
        metrics[2].metric("Son Aksiyon", str(trades.iloc[-1]["action"]))
    else:
        metrics[0].metric("İşlem Sayısı", "-")
        metrics[1].metric("Kümülatif K/Z", "-")
        metrics[2].metric("Son Aksiyon", "-")
    metrics[3].metric("Transfer", transfer_status)
    metrics[4].metric("Serbest USDT", format_metric(free_usdt) if free_usdt is not None else "-")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Son İşlemler")
        if trades is not None and not trades.empty:
            keep = [col for col in ["time", "symbol", "action", "price", "qty", "profit_pct"] if col in trades.columns]
            st.dataframe(trades[keep].tail(12), use_container_width=True, hide_index=True)
        else:
            st.info("İşlem verisi yok.")
    with right:
        st.markdown("#### Cooldown Durumu")
        if cooldowns is not None and not cooldowns.empty:
            cooldown_view = cooldowns.copy()
            cooldown_view["last_updated_at"] = pd.to_datetime(cooldown_view["last_updated_at"], unit="s", errors="coerce")
            st.dataframe(cooldown_view, use_container_width=True, hide_index=True)
        else:
            st.info("Aktif cooldown yok.")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("#### Kümülatif Kâr")
        if trades is not None and not trades.empty:
            fig, ax = plt.subplots(figsize=(8, 3.5))
            profit_series = trades["cum_profit_pct"] * 100
            line_color = COLORS["green"] if profit_series.iloc[-1] >= 0 else COLORS["red"]
            fill_color = COLORS["green_fill"] if profit_series.iloc[-1] >= 0 else COLORS["red_fill"]
            ax.plot(trades.index, profit_series, color=line_color, linewidth=2.2)
            ax.fill_between(trades.index, profit_series, color=fill_color, alpha=0.55)
            ax.axhline(0, color=COLORS["grid"], linewidth=1, linestyle="--")
            style_axes(ax)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Grafik için işlem yok.")
    with chart_right:
        st.markdown("#### Son Fiyat")
        if heartbeat is not None and {"time", "price"}.issubset(heartbeat.columns):
            hb_plot = heartbeat.copy()
            hb_plot["time"] = pd.to_datetime(hb_plot["time"], errors="coerce", utc=True)
            fig, ax = plt.subplots(figsize=(8, 3.5))
            ax.plot(hb_plot["time"], hb_plot["price"], color=COLORS["blue"], linewidth=2.0)
            ax.fill_between(hb_plot["time"], hb_plot["price"], color=COLORS["blue_fill"], alpha=0.45)
            style_axes(ax)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Heartbeat verisi yok.")

    st.markdown("#### Transfer Geçmişi")
    if transfer_logs is not None and not transfer_logs.empty:
        st.dataframe(transfer_logs.tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("Transfer geçmişi yok.")

    st.markdown("#### Son Operasyon Uyarıları")
    if alerts is not None and not alerts.empty:
        ops_alerts = alerts[alerts["category"].isin(["order_fill", "slippage", "api", "risk_mode", "watchdog", "symbol_eval"])]
        st.dataframe(ops_alerts.tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("Operasyonel uyarı yok.")

    extra_left, extra_right = st.columns(2)
    with extra_left:
        st.markdown("#### Shadow İşlemler")
        if shadow_trades is not None and not shadow_trades.empty:
            st.dataframe(shadow_trades.tail(10), use_container_width=True, hide_index=True)
        else:
            st.info("Shadow işlem yok.")
    with extra_right:
        st.markdown("#### Bildirim Geçmişi")
        if notifications is not None and not notifications.empty:
            st.dataframe(notifications.tail(10), use_container_width=True, hide_index=True)
        else:
            st.info("Bildirim geçmişi yok.")


def render_model(data: dict) -> None:
    st.subheader("Model")

    backtest_summary = data["backtest_summary"]
    backtest_trades = data["backtest_trades"]
    walkforward = data["walkforward"]
    best_params = data["best_params"]
    training_report = data["training_report"]
    feature_importance = data["feature_importance"]
    coin_scores = data["coin_scores"]
    trades = data["trades"]
    coin_contribution = data["coin_contribution"]
    symbol_training_report = data["symbol_training_report"]
    symbol_optimization = data["symbol_optimization"]
    live_shadow_analysis = data["live_shadow_analysis"]
    archives = latest_report_archives()

    top = st.columns(4)
    if backtest_summary is not None and not backtest_summary.empty:
        row = backtest_summary.iloc[-1]
        top[0].metric("Backtest Getiri", format_metric(row.get("total_return_pct"), "%"))
        top[1].metric("Backtest İşlem", int(row.get("trade_count", 0)))
        top[2].metric("Max DD", format_metric(row.get("max_drawdown_pct"), "%"))
        top[3].metric("Kâr Faktörü", format_metric(row.get("profit_factor"), decimals=3))
    else:
        for idx, label in enumerate(["Backtest Getiri", "Backtest İşlem", "Max DD", "Kâr Faktörü"]):
            top[idx].metric(label, "-")

    left, right = st.columns((1.05, 0.95))
    with left:
        st.markdown("#### Eğitim Raporu")
        if training_report is not None:
            metrics = st.columns(4)
            metrics[0].metric("Doğruluk", format_metric(training_report.get("accuracy"), decimals=3))
            metrics[1].metric("ROC AUC", format_metric(training_report.get("roc_auc"), decimals=3))
            metrics[2].metric("Brier", format_metric(training_report.get("brier_score"), decimals=4))
            metrics[3].metric("ECE", format_metric(training_report.get("expected_calibration_error"), decimals=4))
            if feature_importance is not None and not feature_importance.empty:
                st.dataframe(feature_importance.head(8), use_container_width=True, hide_index=True)
        else:
            st.info("Eğitim raporu yok.")
    with right:
        st.markdown("#### Optimizer")
        if best_params is not None:
            params = best_params.get("parameters", {})
            summary = best_params.get("summary", {})
            rows = [
                {"alan": "Skor", "değer": format_metric(best_params.get("score"), decimals=3)},
                {"alan": "Alış Eşiği", "değer": params.get("buy_threshold", "-")},
                {"alan": "Çıkış Eşiği", "değer": params.get("signal_exit_prob_threshold", "-")},
                {"alan": "TP %", "değer": format_metric(float(params.get("take_profit_pct", 0.0)) * 100, "%", decimals=2)},
                {"alan": "SL %", "değer": format_metric(float(params.get("stop_loss_pct", 0.0)) * 100, "%", decimals=2)},
                {"alan": "İşlem", "değer": int(summary.get("trade_count", 0))},
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Optimizer sonucu yok.")

    coin_left, coin_right = st.columns(2)
    with coin_left:
        st.markdown("#### Coin Skorları")
        if coin_scores is not None and not coin_scores.empty:
            score_view = coin_scores.rename(columns={"symbol": "sembol", "score": "skor", "eligible": "aktif", "reason": "durum"})
            keep = [col for col in ["sembol", "skor", "aktif", "durum", "bt_trade_count", "wf_trade_count"] if col in score_view.columns]
            st.dataframe(score_view[keep], use_container_width=True, hide_index=True)
        else:
            st.info("Coin skorları yok.")
    with coin_right:
        st.markdown("#### Son 7 Gün Performansı")
        if trades is not None and not trades.empty and {"time", "symbol", "profit_pct", "action"}.issubset(trades.columns):
            trade_view = trades.copy()
            trade_view["time"] = pd.to_datetime(trade_view["time"], errors="coerce", utc=True)
            cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=7)
            trade_view = trade_view[trade_view["time"] >= cutoff]
            if not trade_view.empty:
                performance = (
                    trade_view.groupby("symbol")
                    .agg(
                        islem=("action", "count"),
                        getiri_pct=("profit_pct", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).sum() * 100)),
                    )
                    .reset_index()
                    .sort_values("getiri_pct", ascending=False)
                )
                st.dataframe(performance, use_container_width=True, hide_index=True)
            else:
                st.info("Son 7 günde işlem yok.")
        else:
            st.info("Performans verisi yok.")

    report_left, report_right = st.columns(2)
    with report_left:
        st.markdown("#### Coin Katkısı")
        if coin_contribution is not None and not coin_contribution.empty:
            st.dataframe(coin_contribution, use_container_width=True, hide_index=True)
        else:
            st.info("Coin katkı verisi yok.")
    with report_right:
        st.markdown("#### Coin Bazlı Model Durumu")
        if symbol_training_report is not None and not symbol_training_report.empty:
            st.dataframe(symbol_training_report, use_container_width=True, hide_index=True)
        else:
            st.info("Coin bazlı model raporu yok.")

    st.markdown("#### Coin Bazlı Optimizer")
    if symbol_optimization is not None and not symbol_optimization.empty:
        st.dataframe(symbol_optimization, use_container_width=True, hide_index=True)
    else:
        st.info("Coin bazlı optimizer özeti yok.")

    st.markdown("#### Live vs Shadow Analizi")
    if live_shadow_analysis is not None and not live_shadow_analysis.empty:
        st.dataframe(live_shadow_analysis, use_container_width=True, hide_index=True)
    else:
        st.info("Live vs shadow analizi yok.")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("#### Backtest Getiri Eğrisi")
        if backtest_trades is not None and "return_pct" in backtest_trades.columns:
            trade_plot = backtest_trades.copy()
            trade_plot["cum_return_pct"] = trade_plot["return_pct"].cumsum() * 100
            fig, ax = plt.subplots(figsize=(8, 3.5))
            ax.plot(trade_plot.index, trade_plot["cum_return_pct"], color=COLORS["amber"], linewidth=2.1)
            ax.fill_between(trade_plot.index, trade_plot["cum_return_pct"], color=COLORS["amber_fill"], alpha=0.50)
            ax.axhline(0, color=COLORS["grid"], linewidth=1, linestyle="--")
            style_axes(ax)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Backtest verisi yok.")
    with chart_right:
        st.markdown("#### Walk-forward Foldları")
        if walkforward is not None and not walkforward.empty:
            fig, ax = plt.subplots(figsize=(8, 3.5))
            bar_colors = [COLORS["purple"] if value >= 0 else COLORS["red"] for value in walkforward["total_return_pct"]]
            ax.bar(walkforward["fold"].astype(str), walkforward["total_return_pct"], color=bar_colors)
            ax.axhline(0, color=COLORS["grid"], linewidth=1, linestyle="--")
            style_axes(ax)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Walk-forward verisi yok.")

    st.markdown("#### Son Raporlar")
    if archives:
        st.dataframe(pd.DataFrame([{"arşiv": path.name} for path in archives]), use_container_width=True, hide_index=True)
    else:
        st.info("Rapor arşivi yok.")


st.title("BTC Bot Kontrol Paneli")
st.caption("Sade görünüm: önce özet, sonra işlemler, sonra model.")

data = collect_data()

with st.expander("Hızlı Rehber", expanded=False):
    st.dataframe(quick_guide_table(), use_container_width=True, hide_index=True)

tab_overview, tab_trading, tab_model = st.tabs(["Özet", "İşlemler", "Model"])

with tab_overview:
    render_overview(data)

with tab_trading:
    render_trading(data)

with tab_model:
    render_model(data)
