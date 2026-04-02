from __future__ import annotations
import json
import os
import random
import time
import pandas as pd
from binance.client import Client
from alerts import log_alert
from config import SETTINGS

KLINE_COLUMNS = [
    "open_time", "o", "h", "l", "c", "v",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]

_LAST_SUCCESSFUL_ENDPOINT: str | None = None


def _disable_proxy_env_for_binance() -> None:
    if not SETTINGS.binance_disable_env_proxy:
        return
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    for key in proxy_keys:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = ",".join(
        [
            "localhost",
            "127.0.0.1",
            "binance.com",
            ".binance.com",
            "binance.vision",
            ".binance.vision",
        ]
    )
    os.environ["no_proxy"] = os.environ["NO_PROXY"]


def _load_api_resilience_state() -> dict:
    if not os.path.exists(SETTINGS.api_resilience_state_path):
        return {}
    try:
        with open(SETTINGS.api_resilience_state_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_api_resilience_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS.api_resilience_state_path), exist_ok=True)
        with open(SETTINGS.api_resilience_state_path, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    except OSError:
        return


def get_market_data_archive_path(symbol: str | None = None) -> str:
    symbol = (symbol or SETTINGS.symbol).upper()
    default_symbol = SETTINGS.symbol.upper()
    base_path = SETTINGS.market_data_archive_path
    if symbol == default_symbol:
        return base_path
    root, ext = os.path.splitext(base_path)
    ext = ext or ".csv"
    return f"{root}_{symbol}{ext}"


def get_market_data_cache_path(symbol: str | None = None) -> str:
    symbol = (symbol or SETTINGS.symbol).upper()
    default_symbol = SETTINGS.symbol.upper()
    base_path = SETTINGS.market_data_cache_path
    if symbol == default_symbol:
        return base_path
    root, ext = os.path.splitext(base_path)
    ext = ext or ".csv"
    return f"{root}_{symbol}{ext}"


def build_client(base_endpoint: str | None = None) -> Client:
    _disable_proxy_env_for_binance()
    use_testnet = SETTINGS.testnet and not SETTINGS.paper_trade
    client = Client(
        SETTINGS.api_key,
        SETTINGS.api_secret,
        testnet=use_testnet,
        base_endpoint=base_endpoint or SETTINGS.base_endpoint,
        ping=False,
    )
    if use_testnet:
        client.API_URL = "https://testnet.binance.vision/api"
    return client


def _websocket_snapshot_freshness_seconds() -> int:
    return max(30, SETTINGS.loop_seconds * 3)


def load_websocket_snapshot(symbol: str | None = None) -> dict | None:
    symbol = (symbol or SETTINGS.symbol).upper()
    if not SETTINGS.websocket_enabled:
        return None
    if not os.path.exists(SETTINGS.websocket_cache_path):
        return None
    try:
        with open(SETTINGS.websocket_cache_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    item = payload.get(symbol)
    if not isinstance(item, dict):
        return None
    event_time = pd.to_datetime(item.get("event_time"), errors="coerce", utc=True)
    if pd.isna(event_time):
        return None
    age_seconds = (pd.Timestamp.utcnow() - event_time).total_seconds()
    if age_seconds > _websocket_snapshot_freshness_seconds():
        return None
    item = dict(item)
    item["age_seconds"] = age_seconds
    return item


def _ordered_base_endpoints() -> tuple[str, ...]:
    endpoints = list(SETTINGS.base_endpoints())
    state = _load_api_resilience_state()
    cooldowns = state.get("endpoint_cooldowns", {}) if isinstance(state.get("endpoint_cooldowns"), dict) else {}
    now = time.time()
    healthy = [endpoint for endpoint in endpoints if float(cooldowns.get(endpoint, 0.0) or 0.0) <= now]
    cooling = [endpoint for endpoint in endpoints if endpoint not in healthy]
    endpoints = healthy + cooling
    if _LAST_SUCCESSFUL_ENDPOINT and _LAST_SUCCESSFUL_ENDPOINT in endpoints:
        endpoints.remove(_LAST_SUCCESSFUL_ENDPOINT)
        endpoints.insert(0, _LAST_SUCCESSFUL_ENDPOINT)
    return tuple(endpoints)


def _remember_successful_endpoint(endpoint: str) -> None:
    global _LAST_SUCCESSFUL_ENDPOINT
    _LAST_SUCCESSFUL_ENDPOINT = endpoint
    state = _load_api_resilience_state()
    cooldowns = state.get("endpoint_cooldowns", {})
    if isinstance(cooldowns, dict) and endpoint in cooldowns:
        cooldowns.pop(endpoint, None)
    state["endpoint_cooldowns"] = cooldowns if isinstance(cooldowns, dict) else {}
    state["last_successful_endpoint"] = endpoint
    state["updated_at"] = time.time()
    _save_api_resilience_state(state)


def _is_transient_api_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "ssl",
        "httpsconnectionpool",
        "max retries exceeded",
        "record layer failure",
        "connection reset",
        "connection aborted",
        "timed out",
        "failed to establish a new connection",
        "temporary failure in name resolution",
    )
    return any(marker in text for marker in markers)


def _cooldown_endpoint(endpoint: str) -> None:
    state = _load_api_resilience_state()
    cooldowns = state.get("endpoint_cooldowns", {})
    if not isinstance(cooldowns, dict):
        cooldowns = {}
    cooldowns[endpoint] = time.time() + SETTINGS.api_endpoint_cooldown_seconds
    state["endpoint_cooldowns"] = cooldowns
    state["updated_at"] = time.time()
    _save_api_resilience_state(state)


def _should_log_transient_api_error(method_name: str, endpoint: str) -> bool:
    state = _load_api_resilience_state()
    transient_logs = state.get("transient_log_times", {})
    if not isinstance(transient_logs, dict):
        transient_logs = {}
    key = f"{method_name}:{endpoint}"
    now = time.time()
    last_logged = float(transient_logs.get(key, 0.0) or 0.0)
    if now - last_logged < SETTINGS.api_transient_log_interval_seconds:
        return False
    transient_logs[key] = now
    state["transient_log_times"] = transient_logs
    state["updated_at"] = now
    _save_api_resilience_state(state)
    return True


def _call_with_retries(fn, attempts: int | None = None, delay_seconds: float | None = None, backoff_factor: float | None = None):
    attempts = attempts or SETTINGS.api_retry_attempts
    delay_seconds = SETTINGS.api_retry_delay_seconds if delay_seconds is None else delay_seconds
    backoff_factor = SETTINGS.api_retry_backoff if backoff_factor is None else backoff_factor
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            sleep_seconds = delay_seconds * (backoff_factor ** attempt)
            sleep_seconds += random.uniform(0.0, 0.15)
            time.sleep(sleep_seconds)
    raise last_error


def _call_client_method(method_name: str, *args, **kwargs):
    last_error = None
    endpoint_errors: list[str] = []
    for endpoint in _ordered_base_endpoints():
        client = build_client(endpoint)
        try:
            result = _call_with_retries(lambda: getattr(client, method_name)(*args, **kwargs))
            _remember_successful_endpoint(endpoint)
            return result
        except Exception as exc:
            last_error = exc
            endpoint_errors.append(f"{endpoint}:{exc}")
            if _is_transient_api_error(exc):
                _cooldown_endpoint(endpoint)
                if _should_log_transient_api_error(method_name, endpoint):
                    log_alert("WARN", "api", f"{method_name} gecici endpoint sorunu", details=f"{endpoint}:{exc}")
            else:
                log_alert("WARN", "api", f"{method_name} endpoint basarisiz", details=f"{endpoint}:{exc}")
    if last_error is not None:
        if endpoint_errors:
            log_alert(
                "ERROR" if not _is_transient_api_error(last_error) else "WARN",
                "api",
                f"{method_name} tum endpointlerde basarisiz",
                details=" | ".join(endpoint_errors[-3:]),
            )
        raise last_error
    raise RuntimeError(f"Client method failed without endpoint candidates: {method_name}")


def _load_symbol_info_cache() -> dict[str, dict]:
    if not os.path.exists(SETTINGS.symbol_info_cache_path):
        return {}
    try:
        with open(SETTINGS.symbol_info_cache_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key).upper(): value for key, value in payload.items() if isinstance(value, dict)}


def _save_symbol_info_cache(cache: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(SETTINGS.symbol_info_cache_path), exist_ok=True)
    with open(SETTINGS.symbol_info_cache_path, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def get_symbol_info_cached(symbol: str, force_refresh: bool = False, allow_cache_fallback: bool = True) -> dict:
    symbol = symbol.upper()
    cache = _load_symbol_info_cache()
    if not force_refresh:
        try:
            info = _call_client_method("get_symbol_info", symbol)
            if info:
                cache[symbol] = info
                _save_symbol_info_cache(cache)
                return info
        except Exception:
            if allow_cache_fallback and symbol in cache:
                return cache[symbol]
            raise
    if symbol in cache:
        return cache[symbol]
    info = _call_client_method("get_symbol_info", symbol)
    if not info:
        raise ValueError(f"Sembol bilgisi bulunamadi: {symbol}")
    cache[symbol] = info
    _save_symbol_info_cache(cache)
    return info


def _interval_to_pandas_freq(interval: str) -> str:
    if interval.endswith("m"):
        return f"{interval[:-1]}min"
    if interval.endswith("h"):
        return f"{interval[:-1]}h"
    if interval.endswith("d"):
        return f"{interval[:-1]}D"
    return "1min"


def _resample_market_df(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    normalized = _normalize_market_df(df)
    if normalized.empty or interval == "1m":
        return normalized.reset_index(drop=True)

    freq = _interval_to_pandas_freq(interval)
    indexed = normalized.set_index("open_time").sort_index()
    agg = indexed.resample(freq).agg(
        {
            "o": "first",
            "h": "max",
            "l": "min",
            "c": "last",
            "v": "sum",
            "quote_asset_volume": "sum",
            "number_of_trades": "sum",
            "taker_buy_base": "sum",
            "taker_buy_quote": "sum",
        }
    )
    agg = agg.dropna(subset=["o", "h", "l", "c"]).reset_index()
    if agg.empty:
        return agg
    agg["close_time"] = agg["open_time"] + pd.to_timedelta(freq) - pd.Timedelta(milliseconds=1)
    agg["ignore"] = 0.0
    ordered = [
        "open_time", "o", "h", "l", "c", "v",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    return _normalize_market_df(agg[ordered])


def _regularize_market_df(df: pd.DataFrame, interval: str | None = None) -> pd.DataFrame:
    df = _normalize_market_df(df)
    if df.empty:
        return df

    interval = interval or SETTINGS.interval
    freq = _interval_to_pandas_freq(interval)
    full_index = pd.date_range(start=df["open_time"].iloc[0], end=df["open_time"].iloc[-1], freq=freq)
    out = df.set_index("open_time").reindex(full_index)

    last_close = out["c"].ffill()
    out["c"] = last_close
    out["o"] = out["o"].fillna(last_close)
    out["h"] = out["h"].fillna(last_close)
    out["l"] = out["l"].fillna(last_close)
    out["v"] = out["v"].fillna(0.0)
    out["quote_asset_volume"] = out["quote_asset_volume"].fillna(0.0)
    out["number_of_trades"] = out["number_of_trades"].fillna(0.0)
    out["taker_buy_base"] = out["taker_buy_base"].fillna(0.0)
    out["taker_buy_quote"] = out["taker_buy_quote"].fillna(0.0)
    out["ignore"] = out["ignore"].fillna(0.0)

    filled_close_time = pd.Series(
        out.index + pd.Timedelta(freq) - pd.Timedelta(milliseconds=1),
        index=out.index,
    )
    out["close_time"] = out["close_time"].fillna(filled_close_time)
    out = out.reset_index(names="open_time")
    return _normalize_market_df(out)


def _interval_to_milliseconds(interval: str) -> int:
    if interval.endswith("m"):
        return int(interval[:-1]) * 60_000
    if interval.endswith("h"):
        return int(interval[:-1]) * 3_600_000
    if interval.endswith("d"):
        return int(interval[:-1]) * 86_400_000
    return 60_000


def _normalize_market_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in ["open_time", "close_time"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")

    numeric_cols = [
        "o", "h", "l", "c", "v", "quote_asset_volume",
        "number_of_trades", "taker_buy_base", "taker_buy_quote",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=["open_time", "close_time", "o", "h", "l", "c", "v"])
    out = out.sort_values("open_time").drop_duplicates(subset=["open_time"], keep="last").reset_index(drop=True)
    return out


def _archive_looks_cloned_from_default(df: pd.DataFrame, symbol: str | None = None) -> bool:
    symbol = (symbol or SETTINGS.symbol).upper()
    default_symbol = SETTINGS.symbol.upper()
    if symbol == default_symbol or df.empty:
        return False

    default_path = get_market_data_archive_path(default_symbol)
    if not os.path.exists(default_path):
        return False

    try:
        default_df = pd.read_csv(default_path)
    except OSError:
        return False

    default_df = _normalize_market_df(default_df)
    if default_df.empty:
        return False

    sample_size = min(10, len(df), len(default_df))
    if sample_size == 0:
        return False

    left = df.head(sample_size)[["open_time", "o", "h", "l", "c"]].reset_index(drop=True)
    right = default_df.head(sample_size)[["open_time", "o", "h", "l", "c"]].reset_index(drop=True)
    return left.equals(right)


def _klines_to_df(klines: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(klines, columns=KLINE_COLUMNS)
    if df.empty:
        return df
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return _normalize_market_df(df)


def _cache_market_data(df: pd.DataFrame, symbol: str | None = None) -> None:
    cache_path = get_market_data_cache_path(symbol)
    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)

    existing = _load_cached_market_data(limit=None, symbol=symbol)
    if existing is not None and len(existing) > len(df):
        return
    _normalize_market_df(df).to_csv(cache_path, index=False)


def _load_cached_market_data(limit: int | None = None, symbol: str | None = None) -> pd.DataFrame | None:
    cache_path = get_market_data_cache_path(symbol)
    if not os.path.exists(cache_path):
        return None

    df = pd.read_csv(cache_path)
    if df.empty:
        return None
    df = _normalize_market_df(df)
    if limit:
        df = df.tail(limit).reset_index(drop=True)
    return df


def _load_latest_close_from_storage(symbol: str | None = None, interval: str | None = None) -> float | None:
    symbol = symbol or SETTINGS.symbol
    interval = interval or SETTINGS.interval
    candidates = (
        _load_cached_market_data(limit=1, symbol=symbol),
        load_market_data_archive(limit=1, symbol=symbol, interval=interval),
        load_market_data_archive(limit=1, symbol=symbol, interval="1m"),
    )
    for candidate in candidates:
        if candidate is None or candidate.empty or "c" not in candidate.columns:
            continue
        try:
            price = float(candidate["c"].iloc[-1])
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _build_ohlcv_from_heartbeat(interval: str, limit: int | None = None) -> pd.DataFrame | None:
    heartbeat_path = SETTINGS.heartbeat_log_source_path
    if not os.path.exists(heartbeat_path):
        return None

    heartbeats = pd.read_csv(heartbeat_path)
    if heartbeats.empty or "time" not in heartbeats.columns or "price" not in heartbeats.columns:
        return None

    heartbeats["time"] = pd.to_datetime(heartbeats["time"], errors="coerce")
    heartbeats["price"] = pd.to_numeric(heartbeats["price"], errors="coerce")
    heartbeats = heartbeats.dropna(subset=["time", "price"]).sort_values("time")
    if heartbeats.empty:
        return None

    freq = _interval_to_pandas_freq(interval)
    sampled = heartbeats.set_index("time")
    ohlc = sampled["price"].resample(freq).ohlc()
    trade_count = sampled["price"].resample(freq).count()
    out = ohlc.dropna().reset_index().rename(columns={"time": "open_time"})
    if out.empty:
        return None

    out = out.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"})
    counts = trade_count.reindex(pd.DatetimeIndex(out["open_time"])).fillna(1).astype(float).to_numpy()
    out["v"] = counts
    out["quote_asset_volume"] = out["c"] * out["v"]
    out["number_of_trades"] = counts.astype(int)
    out["taker_buy_base"] = out["v"] * 0.5
    out["taker_buy_quote"] = out["quote_asset_volume"] * 0.5
    out["ignore"] = 0.0
    out["close_time"] = out["open_time"] + pd.to_timedelta(freq) - pd.Timedelta(milliseconds=1)
    ordered = [
        "open_time", "o", "h", "l", "c", "v",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    out = _normalize_market_df(out[ordered])
    if limit:
        out = out.tail(limit).reset_index(drop=True)
    return out


def _write_market_archive(df: pd.DataFrame, symbol: str | None = None) -> None:
    archive_path = get_market_data_archive_path(symbol)
    archive_dir = os.path.dirname(archive_path)
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
    _normalize_market_df(df).to_csv(archive_path, index=False)


def load_market_data_archive(
    limit: int | None = None,
    symbol: str | None = None,
    interval: str | None = None,
) -> pd.DataFrame | None:
    archive_path = get_market_data_archive_path(symbol)
    if not os.path.exists(archive_path):
        return None
    df = pd.read_csv(archive_path)
    if df.empty:
        return None
    df = _normalize_market_df(df)
    if _archive_looks_cloned_from_default(df, symbol=symbol):
        return None
    requested_interval = interval or SETTINGS.interval
    if requested_interval != "1m":
        df = _resample_market_df(df, requested_interval)
    if limit:
        df = df.tail(limit).reset_index(drop=True)
    return df


def _merge_market_data(existing: pd.DataFrame | None, incoming: pd.DataFrame | None) -> pd.DataFrame:
    if existing is None or existing.empty:
        return _normalize_market_df(incoming if incoming is not None else pd.DataFrame(columns=KLINE_COLUMNS))
    if incoming is None or incoming.empty:
        return _normalize_market_df(existing)
    merged = pd.concat([existing, incoming], ignore_index=True)
    return _normalize_market_df(merged)


def archive_latest_klines(
    symbol: str | None = None,
    interval: str | None = None,
    backfill_bars: int | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    symbol = symbol or SETTINGS.symbol
    interval = interval or SETTINGS.interval
    backfill_bars = backfill_bars or SETTINGS.archive_backfill_bars
    batch_limit = max(1, min(SETTINGS.archive_batch_limit, 1000))
    interval_ms = _interval_to_milliseconds(interval)

    existing = None if force_refresh else load_market_data_archive(limit=None, symbol=symbol)
    fetched_batches: list[pd.DataFrame] = []
    try:
        def _fetch_backward_history(remaining: int, end_time_ms: int | None = None) -> None:
            nonlocal fetched_batches
            while remaining > 0:
                limit = min(batch_limit, remaining)
                kwargs = {"symbol": symbol, "interval": interval, "limit": limit}
                if end_time_ms is not None:
                    kwargs["endTime"] = end_time_ms
                klines = _call_client_method("get_klines", **kwargs)
                batch_df = _klines_to_df(klines)
                if batch_df.empty:
                    break
                fetched_batches.append(batch_df)
                remaining -= len(batch_df)
                if len(batch_df) < limit:
                    break
                first_open_ms = int(batch_df["open_time"].iloc[0].timestamp() * 1000)
                next_end_time_ms = first_open_ms - 1
                if end_time_ms is not None and next_end_time_ms >= end_time_ms:
                    break
                end_time_ms = next_end_time_ms

        if existing is None or existing.empty:
            _fetch_backward_history(backfill_bars)
        else:
            if len(existing) < backfill_bars:
                missing_bars = backfill_bars - len(existing)
                earliest_open_ms = int(existing["open_time"].iloc[0].timestamp() * 1000) - 1
                _fetch_backward_history(missing_bars, end_time_ms=earliest_open_ms)
            start_time_ms = int(existing["open_time"].iloc[-1].timestamp() * 1000) + interval_ms
            for _ in range(10):
                klines = _call_client_method(
                    "get_klines",
                    symbol=symbol,
                    interval=interval,
                    limit=batch_limit,
                    startTime=start_time_ms,
                )
                batch_df = _klines_to_df(klines)
                if batch_df.empty:
                    break
                fetched_batches.append(batch_df)
                if len(batch_df) < batch_limit:
                    break
                start_time_ms = int(batch_df["open_time"].iloc[-1].timestamp() * 1000) + interval_ms
    except Exception:
        if fetched_batches:
            incoming = pd.concat(fetched_batches, ignore_index=True)
            merged = _merge_market_data(existing, incoming)
            _write_market_archive(merged, symbol=symbol)
            return merged
        if existing is not None:
            return existing
        fallback = get_klines_df(symbol=symbol, interval=interval, limit=backfill_bars)
        _write_market_archive(fallback, symbol=symbol)
        return fallback

    incoming = pd.concat(fetched_batches, ignore_index=True) if fetched_batches else None
    merged = _merge_market_data(existing, incoming)
    if merged.empty:
        fallback = get_klines_df(symbol=symbol, interval=interval, limit=backfill_bars)
        merged = _normalize_market_df(fallback)
    _write_market_archive(merged, symbol=symbol)
    return merged


def get_research_klines_df(
    limit: int | None = None,
    symbol: str | None = None,
    interval: str | None = None,
) -> pd.DataFrame:
    limit = limit or SETTINGS.training_lookback_limit
    symbol = symbol or SETTINGS.symbol
    interval = interval or SETTINGS.research_interval_value()
    archived = load_market_data_archive(limit=None, symbol=symbol, interval=interval)
    if archived is not None and len(archived) >= limit:
        return _regularize_market_df(archived.tail(limit).reset_index(drop=True), interval=interval)

    archived = archive_latest_klines(symbol=symbol, interval="1m", backfill_bars=max(limit, SETTINGS.archive_backfill_bars))
    if not archived.empty:
        resampled = _resample_market_df(archived, interval)
        return _regularize_market_df(resampled.tail(limit).reset_index(drop=True), interval=interval)
    return _regularize_market_df(get_klines_df(symbol=symbol, interval=interval, limit=limit), interval=interval)


def get_klines_df(symbol: str | None = None, interval: str | None = None, limit: int | None = None) -> pd.DataFrame:
    symbol = symbol or SETTINGS.symbol
    interval = interval or SETTINGS.interval
    limit = limit or SETTINGS.klines_limit

    try:
        klines = _call_client_method("get_klines", symbol=symbol, interval=interval, limit=limit)
        df = _klines_to_df(klines)
        _cache_market_data(df, symbol=symbol)
        return df
    except Exception:
        cached_full = _load_cached_market_data(limit=None, symbol=symbol)
        if cached_full is not None and (limit is None or len(cached_full) >= limit):
            if limit:
                return cached_full.tail(limit).reset_index(drop=True)
            return cached_full

        archived_full = load_market_data_archive(limit=None, symbol=symbol, interval=interval)
        if archived_full is not None and not archived_full.empty:
            _cache_market_data(archived_full, symbol=symbol)
            if limit:
                return archived_full.tail(limit).reset_index(drop=True)
            return archived_full

        if symbol != SETTINGS.symbol:
            raise

        reconstructed_full = _build_ohlcv_from_heartbeat(interval=interval, limit=None)
        if reconstructed_full is not None:
            _cache_market_data(reconstructed_full, symbol=symbol)
            if limit:
                return reconstructed_full.tail(limit).reset_index(drop=True)
            return reconstructed_full
        raise


def get_orderbook_imbalance(symbol: str | None = None, depth_limit: int = 20) -> float:
    snapshot = get_market_microstructure(symbol=symbol, depth_limit=depth_limit)
    return float(snapshot["imbalance"])


def get_market_microstructure(symbol: str | None = None, depth_limit: int = 20) -> dict[str, float]:
    symbol = symbol or SETTINGS.symbol
    ws = load_websocket_snapshot(symbol=symbol)
    ws_bid = float(ws.get("bid", 0.0)) if ws else 0.0
    ws_ask = float(ws.get("ask", 0.0)) if ws else 0.0
    try:
        depth = _call_client_method("get_order_book", symbol=symbol, limit=depth_limit)
    except Exception:
        if ws and ws_bid > 0 and ws_ask > 0:
            mid = (ws_bid + ws_ask) / 2
            spread_bps = ((ws_ask - ws_bid) / mid) * 10000 if mid > 0 else 0.0
            return {
                "imbalance": 0.5,
                "spread_bps": spread_bps,
                "best_bid": ws_bid,
                "best_ask": ws_ask,
                "bid_depth_notional": 0.0,
                "ask_depth_notional": 0.0,
                "total_depth_notional": 0.0,
            }
        cached_price = _load_latest_close_from_storage(symbol=symbol)
        if cached_price and cached_price > 0:
            return {
                "imbalance": 0.5,
                "spread_bps": 0.0,
                "best_bid": cached_price,
                "best_ask": cached_price,
                "bid_depth_notional": 0.0,
                "ask_depth_notional": 0.0,
                "total_depth_notional": 0.0,
            }
        return {
            "imbalance": 0.5,
            "spread_bps": 0.0,
            "best_bid": 0.0,
            "best_ask": 0.0,
            "bid_depth_notional": 0.0,
            "ask_depth_notional": 0.0,
            "total_depth_notional": 0.0,
        }

    bid_volume = sum(float(x[1]) for x in depth["bids"])
    ask_volume = sum(float(x[1]) for x in depth["asks"])
    total = bid_volume + ask_volume
    imbalance = 0.5 if total == 0 else bid_volume / total
    best_bid = ws_bid or (float(depth["bids"][0][0]) if depth.get("bids") else 0.0)
    best_ask = ws_ask or (float(depth["asks"][0][0]) if depth.get("asks") else 0.0)
    mid = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0.0
    spread_bps = ((best_ask - best_bid) / mid) * 10000 if mid > 0 else 0.0
    bid_depth_notional = sum(float(price) * float(qty) for price, qty in depth.get("bids", []))
    ask_depth_notional = sum(float(price) * float(qty) for price, qty in depth.get("asks", []))
    return {
        "imbalance": imbalance,
        "spread_bps": spread_bps,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "bid_depth_notional": bid_depth_notional,
        "ask_depth_notional": ask_depth_notional,
        "total_depth_notional": bid_depth_notional + ask_depth_notional,
    }


def get_last_price(symbol: str | None = None) -> float:
    symbol = symbol or SETTINGS.symbol
    ws = load_websocket_snapshot(symbol=symbol)
    if ws and float(ws.get("price", 0.0) or 0.0) > 0:
        return float(ws["price"])
    try:
        ticker = _call_client_method("get_symbol_ticker", symbol=symbol)
        return float(ticker["price"])
    except Exception:
        cached_price = _load_latest_close_from_storage(symbol=symbol)
        if cached_price and cached_price > 0:
            return cached_price
        raise


def get_free_asset_balance(asset: str) -> float | None:
    try:
        balance = _call_client_method("get_asset_balance", asset=asset, recvWindow=SETTINGS.recv_window)
    except Exception:
        return None
    if not balance:
        return 0.0
    try:
        return float(balance["free"])
    except (KeyError, TypeError, ValueError):
        return None
