from __future__ import annotations
import os
import time
import joblib
from dataclasses import dataclass

from alerts import log_alert
from kill_switch import evaluate_kill_switch, save_kill_switch_state
from notifications import notify_event
from config import SETTINGS
from adaptive_params import symbol_threshold_overrides
from coin_scores import live_entry_guard, load_coin_scores, select_tradeable_symbols
from coin_runtime import filter_symbols_by_cooldown, record_trade_outcome
from comparison_report import build_live_paper_comparison
from daily_summary import build_daily_summary
from no_trade_zone import detect_no_trade_zone
from data import get_klines_df, get_last_price, get_market_microstructure
from features import build_features
from regime.regime_features import add_regime_features
from regime.regime_detector import detect_regime
from regime.regime_router import regime_weights
from agents.trend_agent import trend_signal
from agents.scalp_agent import scalp_signal
from agents.compression_breakout_agent import compression_breakout_signal
from agents.mean_reversion_agent import mean_reversion_signal
from agents.risk_agent import risk_check
from agents.fusion import final_decision
from agents.exit_agent import should_signal_exit
from auto_transfer import maybe_auto_transfer
from execution import (
    Position,
    execute_entry,
    execute_exit,
    get_free_quote_balance,
    get_live_total_equity_usdt,
    load_runtime_state,
    log_trade,
    log_heartbeat,
    log_candidate_signal,
    log_near_candidate_signal,
    log_signal_diagnostic,
    log_equity,
    ensure_trade_log,
    ensure_heartbeat_log,
    ensure_candidate_signal_log,
    ensure_near_candidate_signal_log,
    ensure_signal_diagnostics_log,
    ensure_signal_readiness_log,
    reconcile_live_position,
    second_entry_validation,
    save_runtime_state,
    validate_live_trading_setup,
    log_signal_readiness,
)
from rl_infer import get_rl_action_from_df
from live_gate import live_deployment_guard
from position_sizing import compute_position_fraction
from portfolio_risk import evaluate_portfolio_risk
from portfolio_report import build_portfolio_report
from live_shadow_analysis import build_live_shadow_analysis
from profile_guard import live_profile_guard, load_profile_report
from security_audit import run_security_audit
from shadow_mode import load_shadow_state, process_shadow_position
from sqlite_store import sync_sqlite_store
from strategy_selector import select_symbol_strategy
from strategy_models import (
    apply_breakout_signal_bias,
    enforce_strategy_signal_quality,
    is_breakout_strategy,
    model_probability,
    select_strategy_model,
    should_force_ont_breakout_bias,
)
from signal_strength import evaluate_signal_readiness


def _is_transient_startup_validation_error(exc: Exception) -> bool:
    text = str(exc).lower()
    transient_markers = [
        "ssl",
        "httpsconnectionpool",
        "max retries exceeded",
        "connection reset",
        "timed out",
        "connection aborted",
    ]
    return any(marker in text for marker in transient_markers)


def _model_exists(path: str) -> bool:
    return os.path.exists(path) or os.path.exists(f"{path}.zip")


def _load_symbol_models(symbols: tuple[str, ...]) -> dict[str, object]:
    models: dict[str, object] = {}
    for symbol in symbols:
        path = os.path.join(SETTINGS.symbol_model_dir, f"{symbol}.pkl")
        if os.path.exists(path):
            models[symbol] = joblib.load(path)
    return models


def _load_strategy_models() -> dict[str, object]:
    models: dict[str, object] = {}
    if os.path.exists(SETTINGS.trend_model_path):
        models["trend"] = joblib.load(SETTINGS.trend_model_path)
    if os.path.exists(SETTINGS.mean_reversion_model_path):
        models["mean_reversion"] = joblib.load(SETTINGS.mean_reversion_model_path)
    return models


@dataclass
class SymbolSnapshot:
    symbol: str
    coin_score: float
    imbalance: float
    spread_bps: float
    depth_notional: float
    regime: str
    trend: int
    scalp: int
    rl_action: int
    prob_up: float
    risk_ok: bool
    decision: str
    current_price: float
    volume_ratio: float
    atr_pct: float
    position_fraction: float
    buy_threshold: float
    entry_score_threshold: float
    max_entry_spread_bps: float
    min_entry_depth_notional: float
    no_trade_zone_active: bool
    no_trade_zone_reason: str
    last_bar_return_pct: float
    profile_name: str
    mean_reversion_signal: int
    mean_reversion_confidence: float
    breakout_signal: int
    breakout_confidence: float
    regime_ready: bool
    probability_ready: bool
    liquidity_ready: bool
    strong_signal_ready: bool
    strong_signal_missing_parts: str

    @property
    def entry_rank(self) -> tuple[int, float, float, float]:
        direction_rank = 2 if self.decision == "BUY" else 1 if self.decision == "SELL" else 0
        confidence = abs(self.prob_up - 0.5)
        return (direction_rank, self.coin_score, confidence, self.volume_ratio)


def _build_score_lookup(symbols: tuple[str, ...]) -> dict[str, float]:
    scores = load_coin_scores()
    if scores is None or scores.empty or "symbol" not in scores.columns:
        return {symbol: 50.0 for symbol in symbols}
    scoped = scores[scores["symbol"].isin(symbols)]
    lookup = {str(row["symbol"]).upper(): float(row["score"]) for _, row in scoped.iterrows()}
    return {symbol: lookup.get(symbol, 50.0) for symbol in symbols}


def _evaluate_symbol(symbol: str, model, strategy_models: dict[str, object], daily_pnl_pct: float, coin_score: float) -> SymbolSnapshot:
    micro = get_market_microstructure(symbol=symbol)
    imbalance = float(micro["imbalance"])
    raw = get_klines_df(symbol=symbol)
    feat_df = build_features(raw, imbalance=imbalance, microstructure=micro, symbol=symbol)
    regime_df = add_regime_features(raw)

    regime = detect_regime(regime_df.iloc[-1])
    weights = regime_weights(regime)
    threshold_overrides = symbol_threshold_overrides(symbol, coin_score=coin_score)
    strategy = select_symbol_strategy(
        symbol=symbol,
        regime=regime,
        atr_pct=float(feat_df["atr_pct"].iloc[-1]),
        volume_ratio=float(feat_df["volume_ratio"].iloc[-1]),
        coin_score=coin_score,
    )
    if should_force_ont_breakout_bias(
        symbol=symbol,
        regime=regime,
        breakout_up_20=float(feat_df["breakout_up_20"].iloc[-1]),
        close_location=float(feat_df["close_location"].iloc[-1]),
        range_efficiency=float(feat_df["range_efficiency"].iloc[-1]),
        volume_ratio=float(feat_df["volume_ratio"].iloc[-1]),
    ):
        strategy = dict(strategy)
        strategy["name"] = "ont_15m_breakout"
        strategy["buy_threshold_offset"] = min(float(strategy.get("buy_threshold_offset", 0.0)), -0.02)
        strategy["entry_threshold_offset"] = min(float(strategy.get("entry_threshold_offset", 0.0)), -0.015)
        strategy["spread_multiplier"] = max(float(strategy.get("spread_multiplier", 1.0)), 1.05)
        strategy["depth_multiplier"] = min(float(strategy.get("depth_multiplier", 1.0)), 1.05)
        strategy["size_multiplier"] = min(float(strategy.get("size_multiplier", 1.0)), 0.72)
    threshold_overrides["buy_threshold"] = max(0.52, min(0.75, threshold_overrides["buy_threshold"] + float(strategy["buy_threshold_offset"])))
    threshold_overrides["entry_score_threshold"] = max(
        0.45,
        min(0.72, threshold_overrides["entry_score_threshold"] + float(strategy["entry_threshold_offset"])),
    )
    threshold_overrides["max_entry_spread_bps"] = max(
        4.0,
        float(threshold_overrides["max_entry_spread_bps"]) * float(strategy["spread_multiplier"]),
    )
    threshold_overrides["min_entry_depth_notional"] = max(
        500.0,
        float(threshold_overrides["min_entry_depth_notional"]) * float(strategy["depth_multiplier"]),
    )
    trend = trend_signal(feat_df)
    active_model = select_strategy_model(
        str(strategy["name"]),
        strategy_models=strategy_models,
        symbol_model=model,
        default_model=model,
    )
    scalp, prob_up = scalp_signal(
        model=active_model,
        df=feat_df,
        buy_threshold=threshold_overrides["buy_threshold"],
        sell_threshold=threshold_overrides["sell_threshold"],
    )
    model_prob_up = prob_up
    alternate_key = "trend" if str(strategy["name"]) == "mean_reversion" else "mean_reversion"
    alternate_model = strategy_models.get(alternate_key)
    alternate_prob = model_probability(alternate_model, feat_df) if alternate_model is not None else 0.5
    scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
    mr_signal, mr_confidence = mean_reversion_signal(feat_df, prob_up=prob_up)
    if strategy["name"] == "mean_reversion" and mr_signal > scalp:
        scalp = mr_signal
        prob_up = max(prob_up, mr_confidence)
        scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
    breakout_signal, breakout_confidence = compression_breakout_signal(feat_df, prob_up=prob_up)
    if is_breakout_strategy(str(strategy["name"])):
        scalp, prob_up = apply_breakout_signal_bias(
            symbol=symbol,
            strategy_name=str(strategy["name"]),
            regime=regime,
            trend=trend,
            scalp=scalp,
            active_probability=prob_up,
            breakout_signal=breakout_signal,
            breakout_confidence=breakout_confidence,
        )
        scalp = enforce_strategy_signal_quality(str(strategy["name"]), scalp, prob_up, alternate_prob, model_prob_up)
    rl_action = get_rl_action_from_df(feat_df)
    risk_ok = risk_check(
        volatility=float(regime_df["volatility_20"].iloc[-1]),
        daily_pnl_pct=daily_pnl_pct,
        max_daily_loss=SETTINGS.max_daily_loss,
    )
    atr_pct = float(feat_df["atr_pct"].iloc[-1])
    volume_ratio = float(feat_df["volume_ratio"].iloc[-1])
    last_bar_return_pct = 0.0
    if len(raw) >= 2:
        prev_close = float(raw["c"].iloc[-2])
        if prev_close > 0:
            last_bar_return_pct = ((float(raw["c"].iloc[-1]) - prev_close) / prev_close) * 100
    no_trade_zone_active, no_trade_zone_reason = detect_no_trade_zone(
        symbol=symbol,
        regime=regime,
        prob_up=prob_up,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
        spread_bps=float(micro["spread_bps"]),
        depth_notional=float(micro["total_depth_notional"]),
        last_bar_return_pct=last_bar_return_pct,
        max_entry_spread_bps=float(threshold_overrides["max_entry_spread_bps"]),
        min_entry_depth_notional=float(threshold_overrides["min_entry_depth_notional"]),
        min_probability_edge=SETTINGS.no_trade_min_probability_edge,
    )
    readiness = evaluate_signal_readiness(
        symbol=symbol,
        strategy_name=str(strategy["name"]),
        regime=regime,
        trend=trend,
        breakout_signal=breakout_signal,
        prob_up=prob_up,
        buy_threshold=float(threshold_overrides["buy_threshold"]),
        volume_ratio=volume_ratio,
        spread_bps=float(micro["spread_bps"]),
        depth_notional=float(micro["total_depth_notional"]),
        max_entry_spread_bps=float(threshold_overrides["max_entry_spread_bps"]),
        min_entry_depth_notional=float(threshold_overrides["min_entry_depth_notional"]),
    )
    if (
        symbol.upper() == "ONTUSDT"
        and is_breakout_strategy(str(strategy["name"]))
        and readiness.strong_ready
        and breakout_signal > 0
        and scalp < 1
    ):
        scalp = 1
        prob_up = max(prob_up, float(threshold_overrides["buy_threshold"]) + 0.01)
    decision = final_decision(
        trend=trend,
        scalp=scalp,
        rl_action=rl_action,
        weights=weights,
        risk_ok=risk_ok,
        regime=regime,
        long_only=SETTINGS.long_only,
        prob_up=prob_up,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
        spread_bps=float(micro["spread_bps"]),
        depth_notional=float(micro["total_depth_notional"]),
        entry_score_threshold=threshold_overrides["entry_score_threshold"],
        max_entry_spread_bps=threshold_overrides["max_entry_spread_bps"],
        min_entry_depth_notional=threshold_overrides["min_entry_depth_notional"],
        no_trade_zone_active=no_trade_zone_active,
    )
    current_price = get_last_price(symbol=symbol)
    confidence = abs(prob_up - 0.5)
    position_fraction = compute_position_fraction(
        base_fraction=SETTINGS.risk_per_trade,
        atr_pct=atr_pct,
        coin_score=coin_score,
        confidence=confidence,
        symbol=symbol,
    )
    position_fraction *= float(strategy["size_multiplier"])
    position_fraction = max(SETTINGS.position_size_min_fraction, min(SETTINGS.position_size_max_fraction, position_fraction))
    return SymbolSnapshot(
        symbol=symbol,
        coin_score=coin_score,
        imbalance=imbalance,
        spread_bps=float(micro["spread_bps"]),
        depth_notional=float(micro["total_depth_notional"]),
        regime=regime,
        trend=trend,
        scalp=scalp,
        rl_action=rl_action,
        prob_up=prob_up,
        risk_ok=risk_ok,
        decision=decision,
        current_price=current_price,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
        position_fraction=position_fraction,
        buy_threshold=threshold_overrides["buy_threshold"],
        entry_score_threshold=threshold_overrides["entry_score_threshold"],
        max_entry_spread_bps=float(threshold_overrides["max_entry_spread_bps"]),
        min_entry_depth_notional=float(threshold_overrides["min_entry_depth_notional"]),
        no_trade_zone_active=no_trade_zone_active,
        no_trade_zone_reason=no_trade_zone_reason,
        last_bar_return_pct=last_bar_return_pct,
        profile_name=f"{threshold_overrides.get('profile_name', 'default')}/{strategy['name']}",
        mean_reversion_signal=mr_signal,
        mean_reversion_confidence=mr_confidence,
        breakout_signal=breakout_signal,
        breakout_confidence=breakout_confidence,
        regime_ready=readiness.regime_ready,
        probability_ready=readiness.probability_ready,
        liquidity_ready=readiness.liquidity_ready,
        strong_signal_ready=readiness.strong_ready,
        strong_signal_missing_parts=readiness.missing_parts,
    )


def _reconcile_across_symbols(
    position: Position,
    symbols: tuple[str, ...],
    state_known: bool,
) -> tuple[Position, str]:
    if position.is_open:
        active_symbol = position.symbol or SETTINGS.symbol
        current_price = get_last_price(symbol=active_symbol)
        reconciliation = reconcile_live_position(position, current_price, symbol=active_symbol, state_known=state_known)
        if reconciliation.changed:
            sync_label = "[SYNC_EXTERNAL]" if reconciliation.external_change else "[SYNC]"
            return reconciliation.position, f"{sync_label} {reconciliation.details}"
        return reconciliation.position, ""

    for symbol in symbols:
        current_price = get_last_price(symbol=symbol)
        reconciliation = reconcile_live_position(Position(), current_price, symbol=symbol, state_known=state_known)
        if reconciliation.changed and reconciliation.position.is_open:
            sync_label = "[SYNC_EXTERNAL]" if reconciliation.external_change else "[SYNC]"
            return reconciliation.position, f"{sync_label} {reconciliation.details}"
    return position, ""


def run() -> None:
    ensure_trade_log()
    ensure_heartbeat_log()
    ensure_candidate_signal_log()
    ensure_near_candidate_signal_log()
    ensure_signal_diagnostics_log()
    ensure_signal_readiness_log()
    trading_symbols = SETTINGS.trading_symbols()
    for symbol in trading_symbols:
        try:
            validate_live_trading_setup(symbol)
        except Exception as exc:
            if _is_transient_startup_validation_error(exc):
                log_alert("WARN", "startup_validation", "Canli setup dogrulamasi gecici olarak atlandi", details=str(exc), symbol=symbol)
                print(f"[WARN] {symbol} startup validation atlandi: {exc}")
                continue
            raise

    if not os.path.exists(SETTINGS.model_path):
        raise FileNotFoundError(f"Önce model üret: {SETTINGS.model_path}")
    if not _model_exists(SETTINGS.rl_model_path):
        raise FileNotFoundError(f"Önce RL modeli üret: {SETTINGS.rl_model_path}")

    model = joblib.load(SETTINGS.model_path)
    symbol_models = _load_symbol_models(trading_symbols)
    strategy_models = _load_strategy_models()
    runtime_state = load_runtime_state()
    shadow_state = load_shadow_state()
    equity_usdt = runtime_state.current_equity_usdt or SETTINGS.starting_equity
    daily_pnl_pct = runtime_state.daily_pnl_pct
    position = runtime_state.position
    position, startup_sync_message = _reconcile_across_symbols(
        position,
        trading_symbols,
        state_known=runtime_state.loaded_from_disk,
    )
    if startup_sync_message:
        print(startup_sync_message)
    save_runtime_state(
        position,
        daily_pnl_pct,
        current_equity_usdt=equity_usdt,
        last_event=startup_sync_message or runtime_state.last_event,
    )
    last_sqlite_sync = 0.0
    last_summary_build = 0.0
    last_shadow_analysis = 0.0
    last_security_audit = 0.0

    while True:
        try:
            if SETTINGS.live_trading and not SETTINGS.paper_trade:
                equity_usdt = get_live_total_equity_usdt(trading_symbols)
            log_equity(equity_usdt, daily_pnl_pct, position)
            portfolio_report = build_portfolio_report()
            score_lookup = _build_score_lookup(trading_symbols)
            profile_report = load_profile_report()
            cooldown_symbols, cooldown_table = filter_symbols_by_cooldown(trading_symbols)
            score_candidates = cooldown_symbols if cooldown_symbols else trading_symbols
            scored_symbols, score_table = select_tradeable_symbols(score_candidates)
            trades_df = None
            equity_df = None
            if os.path.exists(SETTINGS.trade_log_path):
                import pandas as pd
                trades_df = pd.read_csv(SETTINGS.trade_log_path)
            if os.path.exists(SETTINGS.equity_log_path):
                import pandas as pd
                equity_df = pd.read_csv(SETTINGS.equity_log_path)
            portfolio_risk = evaluate_portfolio_risk(trades_df, equity_df)
            kill_active, kill_reason = evaluate_kill_switch() if SETTINGS.kill_switch_enabled else (False, "disabled")
            save_kill_switch_state(kill_active, kill_reason)
            if position.is_open and position.symbol:
                active_symbols = (position.symbol,)
            else:
                active_symbols = scored_symbols or trading_symbols or (SETTINGS.symbol,)
            snapshots: list[SymbolSnapshot] = []
            for symbol in active_symbols:
                try:
                    snapshots.append(
                        _evaluate_symbol(
                            symbol,
                            symbol_models.get(symbol, model),
                            strategy_models,
                            daily_pnl_pct,
                            coin_score=score_lookup.get(symbol, 50.0),
                        )
                    )
                except Exception as exc:
                    log_alert("WARN", "symbol_eval", "Sembol degerlendirme hatasi", details=str(exc), symbol=symbol)
                    print(f"[WARN] {symbol} degerlendirilemedi: {exc}")
            if not snapshots:
                if score_table is not None and not score_table.empty:
                    enabled_symbols = ", ".join(active_symbols)
                    print(f"[WARN] Aktif semboller okunamadi: {enabled_symbols}")
                else:
                    print("[WARN] Sembol verisi okunamadi; sonraki dongu bekleniyor.")
                for symbol in active_symbols:
                    try:
                        log_heartbeat(
                            symbol=symbol,
                            regime="NO_DATA",
                            decision="HOLD",
                            price=0.0,
                            prob_up=0.5,
                            imbalance=0.5,
                            daily_pnl_pct=daily_pnl_pct,
                        )
                    except Exception as exc:
                        print(f"[WARN] heartbeat yazilamadi: {symbol}: {exc}")
                save_runtime_state(
                    position,
                    daily_pnl_pct,
                    current_equity_usdt=equity_usdt,
                    last_event=f"no_snapshot:{','.join(active_symbols)}",
                )
                time.sleep(SETTINGS.loop_seconds)
                continue
            for snapshot in snapshots:
                log_heartbeat(
                    symbol=snapshot.symbol,
                    regime=snapshot.regime,
                    decision=snapshot.decision,
                    price=snapshot.current_price,
                    prob_up=snapshot.prob_up,
                    imbalance=snapshot.imbalance,
                    daily_pnl_pct=daily_pnl_pct,
                )

            reconciliation_message = ""
            if position.is_open:
                active_snapshot = snapshots[0]
                reconciliation = reconcile_live_position(
                    position,
                    active_snapshot.current_price,
                    symbol=active_snapshot.symbol,
                    state_known=True,
                )
                if reconciliation.changed:
                    position = reconciliation.position
                    sync_label = "[SYNC_EXTERNAL]" if reconciliation.external_change else "[SYNC]"
                    reconciliation_message = f"{sync_label} {reconciliation.details}"
                    print(reconciliation_message)
            else:
                position, reconciliation_message = _reconcile_across_symbols(position, trading_symbols, state_known=True)
                if reconciliation_message:
                    print(reconciliation_message)
                    continue

            selected_snapshot = snapshots[0] if position.is_open else max(snapshots, key=lambda item: item.entry_rank)
            log_signal_diagnostic(
                symbol=selected_snapshot.symbol,
                profile=selected_snapshot.profile_name,
                decision=selected_snapshot.decision,
                regime=selected_snapshot.regime,
                no_trade_reason=selected_snapshot.no_trade_zone_reason or "",
                coin_score=selected_snapshot.coin_score,
                prob_up=selected_snapshot.prob_up,
                volume_ratio=selected_snapshot.volume_ratio,
                atr_pct=selected_snapshot.atr_pct,
                spread_bps=selected_snapshot.spread_bps,
                depth_notional=selected_snapshot.depth_notional,
                buy_threshold=selected_snapshot.buy_threshold,
                entry_score_threshold=selected_snapshot.entry_score_threshold,
            )
            log_signal_readiness(
                symbol=selected_snapshot.symbol,
                profile=selected_snapshot.profile_name,
                decision=selected_snapshot.decision,
                regime=selected_snapshot.regime,
                regime_ready=selected_snapshot.regime_ready,
                probability_ready=selected_snapshot.probability_ready,
                liquidity_ready=selected_snapshot.liquidity_ready,
                strong_ready=selected_snapshot.strong_signal_ready,
                missing_parts=selected_snapshot.strong_signal_missing_parts,
                prob_up=selected_snapshot.prob_up,
                buy_threshold=selected_snapshot.buy_threshold,
                volume_ratio=selected_snapshot.volume_ratio,
                spread_bps=selected_snapshot.spread_bps,
                depth_notional=selected_snapshot.depth_notional,
            )

            if position.is_open:
                force_signal_exit = should_signal_exit(
                    position_side=position.side,
                    regime=selected_snapshot.regime,
                    trend=selected_snapshot.trend,
                    scalp=selected_snapshot.scalp,
                    rl_action=selected_snapshot.rl_action,
                    prob_up=selected_snapshot.prob_up,
                )
                new_position, pnl_pct, exit_result = execute_exit(
                    position,
                    selected_snapshot.current_price,
                    force_close=force_signal_exit,
                )
                if SETTINGS.shadow_mode_enabled:
                    shadow_state = process_shadow_position(
                        shadow_state,
                        symbol=selected_snapshot.symbol,
                        current_price=selected_snapshot.current_price,
                        decision="HOLD",
                        force_signal_exit=force_signal_exit,
                    )
                if exit_result.success:
                    daily_pnl_pct += pnl_pct
                    action = "CLOSE_LONG" if position.side == "LONG" else "CLOSE_SHORT"
                    record_trade_outcome(position.symbol or selected_snapshot.symbol, pnl_pct)
                    log_trade(
                        symbol=position.symbol or selected_snapshot.symbol,
                        action=action,
                        price=exit_result.price or selected_snapshot.current_price,
                        qty=exit_result.qty or position.qty,
                        regime=selected_snapshot.regime,
                        prob_up=selected_snapshot.prob_up,
                        imbalance=selected_snapshot.imbalance,
                        profit_pct=pnl_pct,
                    )
                    mode_label = "TEST_ORDER" if exit_result.dry_run else "LIVE" if SETTINGS.live_trading and not SETTINGS.paper_trade else "PAPER"
                    print(
                        f"[EXIT] {position.symbol or selected_snapshot.symbol} {action} mode={mode_label} "
                        f"price={exit_result.price or selected_snapshot.current_price:.2f} "
                        f"qty={exit_result.qty or position.qty} pnl={pnl_pct:.4%} reason={exit_result.details}"
                    )
                    notify_event("INFO", "trade_exit", "Pozisyon kapandi", f"{position.symbol or selected_snapshot.symbol} {action} pnl={pnl_pct:.4%}")
                    position = new_position
                    exit_cause = "signal_exit" if force_signal_exit else exit_result.details or "tp_sl"
                    save_runtime_state(
                        position,
                        daily_pnl_pct,
                        current_equity_usdt=equity_usdt,
                        last_event=f"exit:{selected_snapshot.symbol}:{action}:{mode_label}:{exit_cause}",
                    )

            if not position.is_open and selected_snapshot.decision in {"BUY", "SELL"} and portfolio_risk.allow_entries and not kill_active:
                if SETTINGS.live_trading and not SETTINGS.paper_trade and selected_snapshot.decision == "BUY":
                    strategy_name = selected_snapshot.profile_name.split("/")[-1] if selected_snapshot.profile_name else "balanced"
                    quote_balance = get_free_quote_balance(selected_snapshot.symbol)
                    live_guard_ok, live_guard_reason, live_gate_evaluation = live_deployment_guard(
                        selected_snapshot.symbol,
                        strategy_name,
                        quote_balance=quote_balance,
                    )
                    if not live_guard_ok:
                        if bool(live_gate_evaluation.get("candidate_ok")):
                            log_candidate_signal(
                                symbol=selected_snapshot.symbol,
                                profile=strategy_name,
                                decision=selected_snapshot.decision,
                                price=selected_snapshot.current_price,
                                prob_up=selected_snapshot.prob_up,
                                coin_score=selected_snapshot.coin_score,
                                candidate_score=int(live_gate_evaluation.get("candidate_score", 0)),
                                gate_reason=str(live_gate_evaluation.get("reason", "")),
                                regime=selected_snapshot.regime,
                                volume_ratio=selected_snapshot.volume_ratio,
                                atr_pct=selected_snapshot.atr_pct,
                            )
                        elif int(live_gate_evaluation.get("candidate_score", 0)) >= max(0, SETTINGS.live_gate_candidate_min_score - 3):
                            log_near_candidate_signal(
                                symbol=selected_snapshot.symbol,
                                profile=strategy_name,
                                decision=selected_snapshot.decision,
                                price=selected_snapshot.current_price,
                                prob_up=selected_snapshot.prob_up,
                                coin_score=selected_snapshot.coin_score,
                                candidate_score=int(live_gate_evaluation.get("candidate_score", 0)),
                                gate_reason=str(live_gate_evaluation.get("reason", "")),
                                regime=selected_snapshot.regime,
                                volume_ratio=selected_snapshot.volume_ratio,
                                atr_pct=selected_snapshot.atr_pct,
                            )
                        log_alert(
                            "WARN",
                            "live_entry_guard",
                            "Canli giris 5 kosullu canli gate tarafindan engellendi",
                            details=live_guard_reason,
                            symbol=selected_snapshot.symbol,
                        )
                        print(f"[SKIP] {selected_snapshot.symbol} live_gate={live_guard_reason}")
                        if SETTINGS.shadow_mode_enabled:
                            shadow_state = process_shadow_position(
                                shadow_state,
                                symbol=selected_snapshot.symbol,
                                current_price=selected_snapshot.current_price,
                                decision=selected_snapshot.decision,
                                force_signal_exit=False,
                            )
                        save_runtime_state(
                            position,
                            daily_pnl_pct,
                            current_equity_usdt=equity_usdt,
                            last_event=f"live_gate_skip:{selected_snapshot.symbol}:{live_gate_evaluation.get('reason','')}",
                        )
                        time.sleep(SETTINGS.loop_seconds)
                        continue
                second_ok, second_reason, refreshed_price = second_entry_validation(
                    symbol=selected_snapshot.symbol,
                    reference_price=selected_snapshot.current_price,
                    prob_up=selected_snapshot.prob_up,
                    atr_pct=selected_snapshot.atr_pct,
                    volume_ratio=selected_snapshot.volume_ratio,
                    max_entry_spread_bps=selected_snapshot.max_entry_spread_bps,
                    min_entry_depth_notional=selected_snapshot.min_entry_depth_notional,
                )
                if not second_ok:
                    log_alert("WARN", "second_validation", "Giris ikinci kontrolde engellendi", details=second_reason, symbol=selected_snapshot.symbol)
                    print(f"[SKIP] {selected_snapshot.symbol} second_validation={second_reason}")
                    if SETTINGS.shadow_mode_enabled:
                        shadow_state = process_shadow_position(
                            shadow_state,
                            symbol=selected_snapshot.symbol,
                            current_price=refreshed_price,
                            decision=selected_snapshot.decision,
                            force_signal_exit=False,
                        )
                    time.sleep(SETTINGS.loop_seconds)
                    continue
                position, entry_result = execute_entry(
                    position,
                    selected_snapshot.decision,
                    refreshed_price,
                    equity_usdt * portfolio_risk.size_multiplier,
                    symbol=selected_snapshot.symbol,
                    atr_pct=selected_snapshot.atr_pct,
                    coin_score=selected_snapshot.coin_score,
                )
                if SETTINGS.shadow_mode_enabled:
                    shadow_state = process_shadow_position(
                        shadow_state,
                        symbol=selected_snapshot.symbol,
                        current_price=refreshed_price,
                        decision=selected_snapshot.decision,
                        force_signal_exit=False,
                    )
                if entry_result.success:
                    log_trade(
                        symbol=selected_snapshot.symbol,
                        action=selected_snapshot.decision,
                        price=entry_result.price or refreshed_price,
                        qty=entry_result.qty,
                        regime=selected_snapshot.regime,
                        prob_up=selected_snapshot.prob_up,
                        imbalance=selected_snapshot.imbalance,
                        profit_pct=0.0,
                    )
                    mode_label = "TEST_ORDER" if entry_result.dry_run else "LIVE" if SETTINGS.live_trading and not SETTINGS.paper_trade else "PAPER"
                    print(
                        f"[ENTRY] {selected_snapshot.symbol} {selected_snapshot.decision} mode={mode_label} "
                        f"price={entry_result.price or refreshed_price:.2f} qty={entry_result.qty} "
                        f"regime={selected_snapshot.regime} prob_up={selected_snapshot.prob_up:.3f} "
                        f"imbalance={selected_snapshot.imbalance:.3f} score={selected_snapshot.coin_score:.1f} "
                        f"size={selected_snapshot.position_fraction:.2%} profile={selected_snapshot.profile_name} "
                        f"mr={selected_snapshot.mean_reversion_signal}"
                    )
                    notify_event("INFO", "trade_entry", "Pozisyon acildi", f"{selected_snapshot.symbol} {selected_snapshot.decision} qty={entry_result.qty}")
                    save_runtime_state(
                        position,
                        daily_pnl_pct,
                        current_equity_usdt=equity_usdt,
                        last_event=f"entry:{selected_snapshot.symbol}:{selected_snapshot.decision}:{mode_label}",
                    )
                else:
                    print(f"[SKIP] {selected_snapshot.symbol} {selected_snapshot.decision} reason={entry_result.details}")
            else:
                if kill_active:
                    log_alert("ERROR", "kill_switch", "Kill switch aktif", details=kill_reason)
                print(
                    f"[INFO] symbol={selected_snapshot.symbol} regime={selected_snapshot.regime} "
                    f"trend={selected_snapshot.trend} scalp={selected_snapshot.scalp} rl={selected_snapshot.rl_action} "
                    f"decision={selected_snapshot.decision} score={selected_snapshot.coin_score:.1f} "
                    f"size={selected_snapshot.position_fraction * portfolio_risk.size_multiplier:.2%} "
                    f"buy_th={selected_snapshot.buy_threshold:.2f} "
                    f"entry_th={selected_snapshot.entry_score_threshold:.2f} "
                    f"mr={selected_snapshot.mean_reversion_signal} "
                    f"daily_pnl={daily_pnl_pct:.4%} risk={portfolio_risk.reason} "
                    f"no_trade={selected_snapshot.no_trade_zone_reason or '-'} kill={kill_reason}"
                )

            save_runtime_state(
                position,
                daily_pnl_pct,
                current_equity_usdt=equity_usdt,
                last_event=reconciliation_message or f"loop:{selected_snapshot.symbol}:{selected_snapshot.decision}",
            )

            transfer_result = maybe_auto_transfer(position_is_open=position.is_open)
            build_live_paper_comparison()
            now_ts = time.time()
            if now_ts - last_sqlite_sync >= 60:
                sync_sqlite_store()
                last_sqlite_sync = now_ts
            if now_ts - last_summary_build >= 300:
                build_daily_summary()
                last_summary_build = now_ts
            if now_ts - last_shadow_analysis >= 300:
                build_live_shadow_analysis()
                last_shadow_analysis = now_ts
            if now_ts - last_security_audit >= 3600:
                run_security_audit()
                last_security_audit = now_ts
            if portfolio_risk.mode != "normal":
                log_alert(
                    "WARN" if portfolio_risk.allow_entries else "ERROR",
                    "risk_mode",
                    f"Portfoy modu: {portfolio_risk.mode}",
                    details=f"reason={portfolio_risk.reason} dd={portfolio_risk.drawdown_pct:.2f} losses={portfolio_risk.consecutive_losses}",
                )
            if transfer_result.triggered and transfer_result.executed:
                mode_label = "DRY_RUN" if transfer_result.dry_run else "LIVE"
                print(
                    f"[TRANSFER] mode={mode_label} asset={transfer_result.asset} amount={transfer_result.amount:.8f} "
                    f"details={transfer_result.details}"
                )
                notify_event("INFO", "transfer", "Otomatik transfer tetiklendi", f"{transfer_result.asset} {transfer_result.amount:.8f} {mode_label}")

            time.sleep(SETTINGS.loop_seconds)

        except KeyboardInterrupt:
            print("Bot durduruldu.")
            break
        except Exception as e:
            log_alert("ERROR", "main_loop", "Ana dongu hatasi", details=str(e))
            print(f"Hata: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run()
