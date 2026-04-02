from dataclasses import dataclass
import json
import os
from dotenv import load_dotenv

load_dotenv()

def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_symbols(value: str, fallback: str) -> tuple[str, ...]:
    raw_items = [item.strip().upper() for item in value.split(",") if item.strip()]
    symbols = raw_items or [fallback.strip().upper()]
    deduped: list[str] = []
    for symbol in symbols:
        if symbol not in deduped:
            deduped.append(symbol)
    return tuple(deduped)


def _parse_csv_values(value: str, fallback: str) -> tuple[str, ...]:
    raw_items = [item.strip() for item in value.split(",") if item.strip()]
    items = raw_items or [fallback.strip()]
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return tuple(deduped)

@dataclass
class Settings:
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    testnet: bool = _to_bool(os.getenv("BINANCE_TESTNET", "true"), True)
    base_endpoint: str = os.getenv("BINANCE_BASE_ENDPOINT", "1")
    base_endpoints_csv: str = os.getenv("BINANCE_BASE_ENDPOINTS", "")
    live_trading: bool = _to_bool(os.getenv("LIVE_TRADING", "false"), False)
    live_test_orders: bool = _to_bool(os.getenv("LIVE_TEST_ORDERS", "true"), True)
    allow_unrestricted_api_key: bool = _to_bool(os.getenv("ALLOW_UNRESTRICTED_API_KEY", "false"), False)

    symbol: str = os.getenv("SYMBOL", "BTCUSDT")
    symbols_csv: str = os.getenv("SYMBOLS", "")
    primary_symbol_csv: str = os.getenv("PRIMARY_SYMBOL", "")
    secondary_symbols_csv: str = os.getenv("SECONDARY_SYMBOLS", "")
    alt_research_symbols_csv: str = os.getenv("ALT_RESEARCH_SYMBOLS", "XRPUSDT,ONTUSDT")
    interval: str = os.getenv("INTERVAL", "1m")
    research_interval: str = os.getenv("RESEARCH_INTERVAL", "")
    klines_limit: int = 1000
    loop_seconds: int = int(os.getenv("LOOP_SECONDS", "20"))
    shadow_mode_enabled: bool = _to_bool(os.getenv("SHADOW_MODE_ENABLED", "true"), True)
    websocket_enabled: bool = _to_bool(os.getenv("WEBSOCKET_ENABLED", "false"), False)

    paper_trade: bool = _to_bool(os.getenv("PAPER_TRADE", "true"), True)
    long_only: bool = _to_bool(os.getenv("LONG_ONLY", "true"), True)

    buy_threshold: float = 0.60
    sell_threshold: float = 0.40
    entry_score_threshold: float = float(os.getenv("ENTRY_SCORE_THRESHOLD", "0.56"))
    entry_prob_buffer: float = float(os.getenv("ENTRY_PROB_BUFFER", "0.015"))
    entry_min_volume_ratio: float = float(os.getenv("ENTRY_MIN_VOLUME_RATIO", "1.0"))
    entry_max_atr_pct: float = float(os.getenv("ENTRY_MAX_ATR_PCT", "0.006"))
    max_entry_spread_bps: float = float(os.getenv("MAX_ENTRY_SPREAD_BPS", "10"))
    min_entry_depth_notional: float = float(os.getenv("MIN_ENTRY_DEPTH_NOTIONAL", "5000"))
    require_trend_alignment: bool = _to_bool(os.getenv("REQUIRE_TREND_ALIGNMENT", "true"), True)
    require_nonnegative_rl: bool = _to_bool(os.getenv("REQUIRE_NONNEGATIVE_RL", "true"), True)
    block_dowtrend_longs: bool = _to_bool(os.getenv("BLOCK_DOWNTREND_LONGS", "true"), True)
    allow_countertrend_reversion: bool = _to_bool(os.getenv("ALLOW_COUNTERTREND_REVERSION", "true"), True)
    countertrend_reversion_prob_threshold: float = float(os.getenv("COUNTERTREND_REVERSION_PROB_THRESHOLD", "0.58"))
    countertrend_reversion_min_volume_ratio: float = float(os.getenv("COUNTERTREND_REVERSION_MIN_VOLUME_RATIO", "0.75"))
    countertrend_reversion_max_atr_pct: float = float(os.getenv("COUNTERTREND_REVERSION_MAX_ATR_PCT", "0.008"))
    btc_mean_reversion_only: bool = _to_bool(os.getenv("BTC_MEAN_REVERSION_ONLY", "false"), False)
    mean_reversion_enabled: bool = _to_bool(os.getenv("MEAN_REVERSION_ENABLED", "true"), True)
    mean_reversion_rsi_max: float = float(os.getenv("MEAN_REVERSION_RSI_MAX", "42"))
    mean_reversion_bb_pos_max: float = float(os.getenv("MEAN_REVERSION_BB_POS_MAX", "0.20"))
    mean_reversion_range_pos_max: float = float(os.getenv("MEAN_REVERSION_RANGE_POS_MAX", "0.25"))
    mean_reversion_return_5_min: float = float(os.getenv("MEAN_REVERSION_RETURN_5_MIN", "-0.004"))
    mean_reversion_atr_pct_max: float = float(os.getenv("MEAN_REVERSION_ATR_PCT_MAX", "0.01"))
    mean_reversion_prob_floor: float = float(os.getenv("MEAN_REVERSION_PROB_FLOOR", "0.46"))
    mean_reversion_require_reversal_confirmation: bool = _to_bool(os.getenv("MEAN_REVERSION_REQUIRE_REVERSAL_CONFIRMATION", "true"), True)
    mean_reversion_rsi_delta_min: float = float(os.getenv("MEAN_REVERSION_RSI_DELTA_MIN", "1.0"))
    mean_reversion_body_pct_min: float = float(os.getenv("MEAN_REVERSION_BODY_PCT_MIN", "0.15"))
    mean_reversion_lower_wick_min: float = float(os.getenv("MEAN_REVERSION_LOWER_WICK_MIN", "0.30"))
    mean_reversion_price_vs_ema20_max: float = float(os.getenv("MEAN_REVERSION_PRICE_VS_EMA20_MAX", "-0.001"))
    mean_reversion_min_close_location: float = float(os.getenv("MEAN_REVERSION_MIN_CLOSE_LOCATION", "0.40"))
    mean_reversion_min_signed_volume_proxy: float = float(os.getenv("MEAN_REVERSION_MIN_SIGNED_VOLUME_PROXY", "0.0"))
    enable_signal_exit: bool = _to_bool(os.getenv("ENABLE_SIGNAL_EXIT", "true"), True)
    signal_exit_prob_threshold: float = float(os.getenv("SIGNAL_EXIT_PROB_THRESHOLD", "0.48"))
    no_trade_zone_enabled: bool = _to_bool(os.getenv("NO_TRADE_ZONE_ENABLED", "true"), True)
    no_trade_min_probability_edge: float = float(os.getenv("NO_TRADE_MIN_PROBABILITY_EDGE", "0.045"))
    second_validation_enabled: bool = _to_bool(os.getenv("SECOND_VALIDATION_ENABLED", "true"), True)
    max_price_drift_bps: float = float(os.getenv("MAX_PRICE_DRIFT_BPS", "12"))
    prefer_limit_entry: bool = _to_bool(os.getenv("PREFER_LIMIT_ENTRY", "false"), False)

    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.05"))
    max_daily_loss: float = 0.03
    take_profit_pct: float = 0.005
    stop_loss_pct: float = 0.003
    break_even_trigger_pct: float = float(os.getenv("BREAK_EVEN_TRIGGER_PCT", "0.003"))
    break_even_buffer_pct: float = float(os.getenv("BREAK_EVEN_BUFFER_PCT", "0.0005"))
    trailing_activation_pct: float = float(os.getenv("TRAILING_ACTIVATION_PCT", "0.005"))
    trailing_stop_pct: float = float(os.getenv("TRAILING_STOP_PCT", "0.0025"))
    cooldown_bars: int = 1

    starting_equity: float = float(os.getenv("STARTING_EQUITY", "10000"))
    max_live_quote_per_order: float = float(os.getenv("MAX_LIVE_QUOTE_PER_ORDER", "25"))
    min_quote_balance: float = float(os.getenv("MIN_QUOTE_BALANCE", "15"))
    live_min_notional_buffer_pct: float = float(os.getenv("LIVE_MIN_NOTIONAL_BUFFER_PCT", "0.05"))
    dynamic_sizing_enabled: bool = _to_bool(os.getenv("DYNAMIC_SIZING_ENABLED", "true"), True)
    position_size_min_fraction: float = float(os.getenv("POSITION_SIZE_MIN_FRACTION", "0.01"))
    position_size_max_fraction: float = float(os.getenv("POSITION_SIZE_MAX_FRACTION", "0.15"))
    sizing_target_atr_pct: float = float(os.getenv("SIZING_TARGET_ATR_PCT", "0.003"))
    sizing_min_volatility_factor: float = float(os.getenv("SIZING_MIN_VOLATILITY_FACTOR", "0.50"))
    sizing_max_volatility_factor: float = float(os.getenv("SIZING_MAX_VOLATILITY_FACTOR", "1.40"))
    sizing_score_floor: float = float(os.getenv("SIZING_SCORE_FLOOR", "0.70"))
    sizing_score_ceiling: float = float(os.getenv("SIZING_SCORE_CEILING", "1.35"))
    recv_window: int = int(os.getenv("RECV_WINDOW", "5000"))
    api_retry_attempts: int = int(os.getenv("API_RETRY_ATTEMPTS", "4"))
    api_retry_delay_seconds: float = float(os.getenv("API_RETRY_DELAY_SECONDS", "1.0"))
    api_retry_backoff: float = float(os.getenv("API_RETRY_BACKOFF", "1.8"))
    api_endpoint_cooldown_seconds: int = int(os.getenv("API_ENDPOINT_COOLDOWN_SECONDS", "120"))
    api_transient_log_interval_seconds: int = int(os.getenv("API_TRANSIENT_LOG_INTERVAL_SECONDS", "90"))
    order_status_poll_attempts: int = int(os.getenv("ORDER_STATUS_POLL_ATTEMPTS", "3"))
    order_status_poll_delay_seconds: float = float(os.getenv("ORDER_STATUS_POLL_DELAY_SECONDS", "0.8"))
    high_slippage_alert_bps: float = float(os.getenv("HIGH_SLIPPAGE_ALERT_BPS", "18"))
    max_trades_per_day: int = int(os.getenv("MAX_TRADES_PER_DAY", "8"))
    portfolio_max_daily_drawdown_pct: float = float(os.getenv("PORTFOLIO_MAX_DAILY_DRAWDOWN_PCT", "4.0"))
    portfolio_max_consecutive_losses: int = int(os.getenv("PORTFOLIO_MAX_CONSECUTIVE_LOSSES", "3"))
    portfolio_caution_drawdown_pct: float = float(os.getenv("PORTFOLIO_CAUTION_DRAWDOWN_PCT", "2.4"))
    reconcile_trade_limit: int = int(os.getenv("RECONCILE_TRADE_LIMIT", "200"))
    backtest_fee_rate: float = float(os.getenv("BACKTEST_FEE_RATE", "0.001"))
    backtest_slippage_rate: float = float(os.getenv("BACKTEST_SLIPPAGE_RATE", "0.0005"))
    backtest_risk_fraction: float = float(os.getenv("BACKTEST_RISK_FRACTION", "0.03"))
    backtest_partial_fill_floor: float = float(os.getenv("BACKTEST_PARTIAL_FILL_FLOOR", "0.65"))
    backtest_reject_rate: float = float(os.getenv("BACKTEST_REJECT_RATE", "0.03"))
    backtest_trades_path: str = "logs/backtest_trades.csv"
    backtest_summary_path: str = "logs/backtest_summary.csv"
    walkforward_results_path: str = "logs/walkforward_results.csv"
    report_archive_dir: str = "logs/report_archives"
    market_data_cache_path: str = "logs/market_data_cache.csv"
    market_data_archive_path: str = "logs/market_data_archive.csv"
    heartbeat_log_source_path: str = "logs/heartbeat.csv"
    training_lookback_limit: int = int(os.getenv("TRAINING_LOOKBACK_LIMIT", "5000"))
    long_validation_lookback_limit: int = int(os.getenv("LONG_VALIDATION_LOOKBACK_LIMIT", "10000"))
    long_validation_intervals_csv: str = os.getenv("LONG_VALIDATION_INTERVALS", "1m,5m")
    long_validation_horizons_csv: str = os.getenv("LONG_VALIDATION_HORIZONS", "3,5,8")
    target_horizon_bars: int = int(os.getenv("TARGET_HORIZON_BARS", "5"))
    target_min_return_pct: float = float(os.getenv("TARGET_MIN_RETURN_PCT", "0.0025"))
    target_take_profit_pct: float = float(os.getenv("TARGET_TAKE_PROFIT_PCT", "0.004"))
    target_stop_loss_pct: float = float(os.getenv("TARGET_STOP_LOSS_PCT", "0.0025"))
    target_min_r_multiple: float = float(os.getenv("TARGET_MIN_R_MULTIPLE", "0.25"))
    archive_batch_limit: int = int(os.getenv("ARCHIVE_BATCH_LIMIT", "1000"))
    archive_backfill_bars: int = int(os.getenv("ARCHIVE_BACKFILL_BARS", "5000"))
    walkforward_train_bars: int = int(os.getenv("WALKFORWARD_TRAIN_BARS", "300"))
    walkforward_test_bars: int = int(os.getenv("WALKFORWARD_TEST_BARS", "120"))
    walkforward_step_bars: int = int(os.getenv("WALKFORWARD_STEP_BARS", "120"))
    walkforward_rl_timesteps: int = int(os.getenv("WALKFORWARD_RL_TIMESTEPS", "4000"))
    optimization_results_path: str = "logs/optimization_results.csv"
    best_params_path: str = "logs/best_params.json"
    coin_scores_path: str = "logs/coin_scores.csv"
    live_paper_comparison_path: str = "logs/live_paper_comparison.csv"
    training_report_path: str = "logs/training_report.json"
    feature_importance_path: str = "logs/feature_importance.csv"
    coin_score_min: float = float(os.getenv("COIN_SCORE_MIN", "45"))
    coin_score_min_trades: int = int(os.getenv("COIN_SCORE_MIN_TRADES", "5"))
    coin_score_hard_block: float = float(os.getenv("COIN_SCORE_HARD_BLOCK", "30"))
    coin_score_min_wf_avg_return: float = float(os.getenv("COIN_SCORE_MIN_WF_AVG_RETURN", "-0.02"))
    coin_score_max_negative_folds: int = int(os.getenv("COIN_SCORE_MAX_NEGATIVE_FOLDS", "2"))
    coin_score_max_zero_trade_folds: int = int(os.getenv("COIN_SCORE_MAX_ZERO_TRADE_FOLDS", "4"))
    live_require_score_guard: bool = _to_bool(os.getenv("LIVE_REQUIRE_SCORE_GUARD", "true"), True)
    live_block_on_hard_block: bool = _to_bool(os.getenv("LIVE_BLOCK_ON_HARD_BLOCK", "true"), True)
    live_min_coin_score: float = float(os.getenv("LIVE_MIN_COIN_SCORE", "20"))
    live_gate_min_quick_return_pct: float = float(os.getenv("LIVE_GATE_MIN_QUICK_RETURN_PCT", "0.0"))
    live_gate_max_quick_drawdown_pct: float = float(os.getenv("LIVE_GATE_MAX_QUICK_DRAWDOWN_PCT", "2.5"))
    live_gate_min_wf_trades: int = int(os.getenv("LIVE_GATE_MIN_WF_TRADES", "3"))
    live_gate_min_wf_avg_return_pct: float = float(os.getenv("LIVE_GATE_MIN_WF_AVG_RETURN_PCT", "0.0"))
    live_gate_min_bt_return_pct: float = float(os.getenv("LIVE_GATE_MIN_BT_RETURN_PCT", "0.0"))
    live_gate_min_bt_profit_factor: float = float(os.getenv("LIVE_GATE_MIN_BT_PROFIT_FACTOR", "1.1"))
    live_gate_min_bt_trades: int = int(os.getenv("LIVE_GATE_MIN_BT_TRADES", "5"))
    live_gate_candidate_min_score: int = int(os.getenv("LIVE_GATE_CANDIDATE_MIN_SCORE", "6"))
    live_gate_candidate_min_bt_return_pct: float = float(os.getenv("LIVE_GATE_CANDIDATE_MIN_BT_RETURN_PCT", "-0.5"))
    live_gate_candidate_min_bt_profit_factor: float = float(os.getenv("LIVE_GATE_CANDIDATE_MIN_BT_PROFIT_FACTOR", "0.55"))
    live_gate_candidate_min_bt_trades: int = int(os.getenv("LIVE_GATE_CANDIDATE_MIN_BT_TRADES", "2"))
    live_gate_candidate_max_bt_drawdown_pct: float = float(os.getenv("LIVE_GATE_CANDIDATE_MAX_BT_DRAWDOWN_PCT", "2.0"))
    live_gate_candidate_max_quick_drawdown_pct: float = float(os.getenv("LIVE_GATE_CANDIDATE_MAX_QUICK_DRAWDOWN_PCT", "2.5"))
    live_gate_candidate_min_wf_avg_return_pct: float = float(os.getenv("LIVE_GATE_CANDIDATE_MIN_WF_AVG_RETURN_PCT", "-0.05"))
    secondary_symbol_min_score: float = float(os.getenv("SECONDARY_SYMBOL_MIN_SCORE", "55"))
    secondary_symbol_min_bt_return: float = float(os.getenv("SECONDARY_SYMBOL_MIN_BT_RETURN", "0.0"))
    secondary_symbol_min_wf_return: float = float(os.getenv("SECONDARY_SYMBOL_MIN_WF_RETURN", "0.0"))
    coin_cooldown_enabled: bool = _to_bool(os.getenv("COIN_COOLDOWN_ENABLED", "true"), True)
    coin_cooldown_minutes: int = int(os.getenv("COIN_COOLDOWN_MINUTES", "180"))
    coin_max_consecutive_losses: int = int(os.getenv("COIN_MAX_CONSECUTIVE_LOSSES", "2"))
    coin_cooldown_state_path: str = "logs/coin_cooldowns.json"
    symbol_model_dir: str = "models/symbols"
    symbol_best_params_path: str = "logs/symbol_best_params.json"
    symbol_training_report_path: str = "logs/symbol_training_report.csv"
    symbol_min_training_rows: int = int(os.getenv("SYMBOL_MIN_TRAINING_ROWS", "120"))
    auto_load_best_params: bool = _to_bool(os.getenv("AUTO_LOAD_BEST_PARAMS", "true"), True)
    walkforward_cache_enabled: bool = _to_bool(os.getenv("WALKFORWARD_CACHE_ENABLED", "true"), True)
    walkforward_rl_retrain_interval: int = int(os.getenv("WALKFORWARD_RL_RETRAIN_INTERVAL", "2"))
    auto_transfer_enabled: bool = _to_bool(os.getenv("AUTO_TRANSFER_ENABLED", "false"), False)
    auto_transfer_dry_run: bool = _to_bool(os.getenv("AUTO_TRANSFER_DRY_RUN", "true"), True)
    auto_transfer_asset: str = os.getenv("AUTO_TRANSFER_ASSET", "USDT")
    auto_transfer_trigger_balance: float = float(os.getenv("AUTO_TRANSFER_TRIGGER_BALANCE", "100"))
    auto_transfer_fraction: float = float(os.getenv("AUTO_TRANSFER_FRACTION", "0.5"))
    auto_transfer_reset_balance: float = float(os.getenv("AUTO_TRANSFER_RESET_BALANCE", "90"))
    auto_transfer_min_interval_seconds: int = int(os.getenv("AUTO_TRANSFER_MIN_INTERVAL_SECONDS", "1800"))
    auto_transfer_network: str = os.getenv("AUTO_TRANSFER_NETWORK", "")
    auto_transfer_address: str = os.getenv("AUTO_TRANSFER_ADDRESS", "")
    auto_transfer_address_tag: str = os.getenv("AUTO_TRANSFER_ADDRESS_TAG", "")
    auto_transfer_address_name: str = os.getenv("AUTO_TRANSFER_ADDRESS_NAME", "BinanceTR")
    auto_transfer_wallet_type: int = int(os.getenv("AUTO_TRANSFER_WALLET_TYPE", "0"))
    auto_transfer_transaction_fee_flag: bool = _to_bool(os.getenv("AUTO_TRANSFER_TRANSACTION_FEE_FLAG", "false"), False)
    auto_transfer_state_path: str = "logs/auto_transfer_state.json"
    auto_transfer_log_path: str = "logs/auto_transfers.csv"
    notification_enabled: bool = _to_bool(os.getenv("NOTIFICATION_ENABLED", "false"), False)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    notification_timeout_seconds: int = int(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "8"))

    model_path: str = "models/xgb_model.pkl"
    trend_model_path: str = "models/trend_model.pkl"
    mean_reversion_model_path: str = "models/mean_reversion_model.pkl"
    rl_model_path: str = "models/rl_trader"
    strategy_model_min_rows: int = int(os.getenv("STRATEGY_MODEL_MIN_ROWS", "60"))
    strategy_edge_min_margin: float = float(os.getenv("STRATEGY_EDGE_MIN_MARGIN", "0.03"))
    mean_reversion_edge_min_margin: float = float(os.getenv("MEAN_REVERSION_EDGE_MIN_MARGIN", "0.02"))
    trend_min_prob_up: float = float(os.getenv("TREND_MIN_PROB_UP", "0.56"))
    mean_reversion_min_prob_up: float = float(os.getenv("MEAN_REVERSION_MIN_PROB_UP", "0.54"))
    mean_reversion_min_model_prob_up: float = float(os.getenv("MEAN_REVERSION_MIN_MODEL_PROB_UP", "0.40"))
    breakout_max_bb_width: float = float(os.getenv("BREAKOUT_MAX_BB_WIDTH", "0.018"))
    breakout_min_breakout_up_20: float = float(os.getenv("BREAKOUT_MIN_BREAKOUT_UP_20", "0.0015"))
    breakout_min_volume_ratio: float = float(os.getenv("BREAKOUT_MIN_VOLUME_RATIO", "1.20"))
    breakout_min_close_location: float = float(os.getenv("BREAKOUT_MIN_CLOSE_LOCATION", "0.70"))
    breakout_min_range_efficiency: float = float(os.getenv("BREAKOUT_MIN_RANGE_EFFICIENCY", "0.55"))
    breakout_min_signed_volume_proxy: float = float(os.getenv("BREAKOUT_MIN_SIGNED_VOLUME_PROXY", "0.20"))
    breakout_min_price_vs_ema20: float = float(os.getenv("BREAKOUT_MIN_PRICE_VS_EMA20", "0.0005"))
    breakout_prob_floor: float = float(os.getenv("BREAKOUT_PROB_FLOOR", "0.62"))
    breakout_min_prob_up: float = float(os.getenv("BREAKOUT_MIN_PROB_UP", "0.54"))
    trade_log_path: str = "logs/trades.csv"
    order_audit_log_path: str = "logs/order_audit.csv"
    candidate_signal_log_path: str = "logs/candidate_signals.csv"
    near_candidate_signal_log_path: str = "logs/near_candidate_signals.csv"
    signal_diagnostics_log_path: str = "logs/signal_diagnostics.csv"
    signal_readiness_log_path: str = "logs/signal_readiness.csv"
    heartbeat_log_path: str = "logs/heartbeat.csv"
    quote_balance_cache_path: str = "logs/quote_balance_cache.json"
    runtime_state_path: str = "logs/runtime_state.json"
    symbol_info_cache_path: str = "logs/symbol_info_cache.json"
    equity_log_path: str = "logs/equity.csv"
    alerts_log_path: str = "logs/alerts.csv"
    notification_log_path: str = "logs/notifications.csv"
    portfolio_report_path: str = "logs/portfolio_report.json"
    portfolio_periods_path: str = "logs/portfolio_periods.csv"
    coin_contribution_path: str = "logs/coin_contribution.csv"
    system_health_path: str = "logs/system_health.json"
    live_readiness_path: str = "logs/live_readiness.json"
    symbol_optimization_results_path: str = "logs/symbol_optimization_results.csv"
    daily_summary_path: str = "logs/daily_summary.json"
    live_shadow_analysis_path: str = "logs/live_shadow_analysis.csv"
    security_audit_path: str = "logs/security_audit.json"
    sqlite_db_path: str = "logs/btcbot.sqlite3"
    websocket_cache_path: str = "logs/websocket_cache.json"
    walkforward_cache_dir: str = "logs/walkforward_cache"
    api_resilience_state_path: str = "logs/api_resilience.json"
    self_protection_state_path: str = "logs/self_protection.json"
    shadow_state_path: str = "logs/shadow_state.json"
    shadow_trade_log_path: str = "logs/shadow_trades.csv"
    kill_switch_state_path: str = "logs/kill_switch.json"
    watchdog_state_path: str = "logs/watchdog_state.json"
    watchdog_heartbeat_timeout_seconds: int = int(os.getenv("WATCHDOG_HEARTBEAT_TIMEOUT_SECONDS", "180"))
    watchdog_error_threshold: int = int(os.getenv("WATCHDOG_ERROR_THRESHOLD", "5"))
    self_protection_enabled: bool = _to_bool(os.getenv("SELF_PROTECTION_ENABLED", "true"), True)
    self_protection_max_loss_streak: int = int(os.getenv("SELF_PROTECTION_MAX_LOSS_STREAK", "4"))
    self_protection_drawdown_pct: float = float(os.getenv("SELF_PROTECTION_DRAWDOWN_PCT", "5.0"))
    self_protection_reduced_size_multiplier: float = float(os.getenv("SELF_PROTECTION_REDUCED_SIZE_MULTIPLIER", "0.35"))
    kill_switch_enabled: bool = _to_bool(os.getenv("KILL_SWITCH_ENABLED", "true"), True)
    kill_switch_error_threshold: int = int(os.getenv("KILL_SWITCH_ERROR_THRESHOLD", "5"))
    kill_switch_window_minutes: int = int(os.getenv("KILL_SWITCH_WINDOW_MINUTES", "20"))

    def trading_symbols(self) -> tuple[str, ...]:
        return _parse_symbols(self.symbols_csv, self.symbol)

    def primary_symbol(self) -> str:
        explicit = self.primary_symbol_csv.strip().upper()
        return explicit or self.symbol.strip().upper()

    def secondary_symbols(self) -> tuple[str, ...]:
        if self.secondary_symbols_csv.strip():
            return tuple(
                symbol
                for symbol in _parse_symbols(self.secondary_symbols_csv, self.primary_symbol())
                if symbol != self.primary_symbol()
            )
        return tuple(symbol for symbol in self.trading_symbols() if symbol != self.primary_symbol())

    def alt_research_symbols(self) -> tuple[str, ...]:
        return tuple(
            symbol
            for symbol in _parse_symbols(self.alt_research_symbols_csv, "ETHUSDT")
            if symbol != self.primary_symbol()
        )

    def research_interval_value(self) -> str:
        value = self.research_interval.strip()
        return value or self.interval

    def long_validation_intervals(self) -> tuple[str, ...]:
        return _parse_csv_values(self.long_validation_intervals_csv, self.research_interval_value())

    def long_validation_horizons(self) -> tuple[int, ...]:
        values = [item.strip() for item in self.long_validation_horizons_csv.split(",") if item.strip()]
        parsed = [int(item) for item in values] if values else [self.target_horizon_bars]
        deduped: list[int] = []
        for item in parsed:
            if item not in deduped:
                deduped.append(item)
        return tuple(deduped)

    def base_endpoints(self) -> tuple[str, ...]:
        return _parse_csv_values(self.base_endpoints_csv, self.base_endpoint)

SETTINGS = Settings()


def _load_best_param_overrides(settings: Settings) -> None:
    if not settings.auto_load_best_params:
        return
    if not os.path.exists(settings.best_params_path):
        return
    try:
        with open(settings.best_params_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    parameters = payload.get("parameters", payload)
    allowed = {
        "buy_threshold",
        "sell_threshold",
        "take_profit_pct",
        "stop_loss_pct",
        "backtest_risk_fraction",
        "entry_score_threshold",
        "entry_prob_buffer",
        "entry_min_volume_ratio",
        "entry_max_atr_pct",
        "require_trend_alignment",
        "require_nonnegative_rl",
        "block_dowtrend_longs",
        "enable_signal_exit",
        "signal_exit_prob_threshold",
    }
    for key, value in parameters.items():
        if key in allowed and hasattr(settings, key):
            setattr(settings, key, value)


_load_best_param_overrides(SETTINGS)
