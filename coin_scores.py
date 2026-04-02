from __future__ import annotations

import os

import pandas as pd
from pandas.errors import EmptyDataError

from config import SETTINGS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_load_csv(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        df = pd.read_csv(path)
    except EmptyDataError:
        return None
    return None if df.empty else df


def _compute_backtest_metrics(backtest_trades: pd.DataFrame | None) -> dict[str, dict]:
    if backtest_trades is None or backtest_trades.empty or "symbol" not in backtest_trades.columns:
        return {}

    metrics: dict[str, dict] = {}
    grouped = backtest_trades.groupby("symbol")
    for symbol, group in grouped:
        returns = pd.to_numeric(group.get("return_pct"), errors="coerce").fillna(0.0)
        pnl = pd.to_numeric(group.get("net_pnl"), errors="coerce").fillna(0.0)
        losses = pnl[pnl < 0]
        profits = pnl[pnl > 0]
        profit_factor = float(profits.sum() / abs(losses.sum())) if not losses.empty else float("inf")
        metrics[str(symbol).upper()] = {
            "bt_trade_count": int(len(group)),
            "bt_avg_return_pct": float(returns.mean() * 100) if len(returns) else 0.0,
            "bt_total_return_pct": float(returns.sum() * 100) if len(returns) else 0.0,
            "bt_win_rate_pct": float((returns > 0).mean() * 100) if len(returns) else 0.0,
            "bt_profit_factor": profit_factor,
            "bt_net_pnl": float(pnl.sum()),
        }
    return metrics


def _compute_walkforward_metrics(walkforward: pd.DataFrame | None) -> dict[str, dict]:
    if walkforward is None or walkforward.empty or "symbol" not in walkforward.columns:
        return {}

    metrics: dict[str, dict] = {}
    grouped = walkforward.groupby("symbol")
    for symbol, group in grouped:
        returns = pd.to_numeric(group.get("total_return_pct"), errors="coerce").fillna(0.0)
        trade_counts = pd.to_numeric(group.get("trade_count"), errors="coerce").fillna(0)
        metrics[str(symbol).upper()] = {
            "wf_fold_count": int(len(group)),
            "wf_trade_count": int(trade_counts.sum()),
            "wf_avg_return_pct": float(returns.mean()),
            "wf_avg_win_rate_pct": float(pd.to_numeric(group.get("win_rate_pct"), errors="coerce").fillna(0.0).mean()),
            "wf_avg_max_drawdown_pct": float(pd.to_numeric(group.get("max_drawdown_pct"), errors="coerce").fillna(0.0).mean()),
            "wf_negative_fold_count": int((returns < 0).sum()),
            "wf_zero_trade_fold_count": int((trade_counts <= 0).sum()),
            "wf_positive_fold_ratio_pct": float((returns > 0).mean() * 100) if len(returns) else 0.0,
        }
    return metrics


def compute_coin_scores(
    backtest_trades: pd.DataFrame | None = None,
    walkforward: pd.DataFrame | None = None,
    configured_symbols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    configured = [symbol.upper() for symbol in (configured_symbols or SETTINGS.trading_symbols())]
    bt_metrics = _compute_backtest_metrics(backtest_trades)
    wf_metrics = _compute_walkforward_metrics(walkforward)

    rows: list[dict] = []
    for symbol in configured:
        bt = bt_metrics.get(symbol, {})
        wf = wf_metrics.get(symbol, {})

        bt_trade_count = int(bt.get("bt_trade_count", 0))
        wf_trade_count = int(wf.get("wf_trade_count", 0))
        total_trade_count = bt_trade_count + wf_trade_count
        wf_fold_count = int(wf.get("wf_fold_count", 0))
        bt_avg_return_pct = float(bt.get("bt_avg_return_pct", 0.0))
        wf_avg_return_pct = float(wf.get("wf_avg_return_pct", 0.0))
        bt_win_rate_pct = float(bt.get("bt_win_rate_pct", 0.0))
        wf_avg_win_rate_pct = float(wf.get("wf_avg_win_rate_pct", 0.0))
        bt_profit_factor = float(bt.get("bt_profit_factor", 0.0))
        wf_avg_max_drawdown_pct = float(wf.get("wf_avg_max_drawdown_pct", 0.0))
        wf_negative_fold_count = int(wf.get("wf_negative_fold_count", 0))
        wf_zero_trade_fold_count = int(wf.get("wf_zero_trade_fold_count", 0))
        wf_positive_fold_ratio_pct = float(wf.get("wf_positive_fold_ratio_pct", 0.0))

        if total_trade_count == 0 and wf_fold_count == 0:
            score = 0.0
        else:
            score = 50.0
            score += _clamp(bt_avg_return_pct * 6.0, -18.0, 18.0)
            score += _clamp(wf_avg_return_pct * 11.0, -26.0, 22.0)
            score += _clamp((bt_win_rate_pct - 45.0) * 0.45, -10.0, 10.0)
            score += _clamp((wf_avg_win_rate_pct - 45.0) * 0.30, -8.0, 8.0)
            score += _clamp((wf_positive_fold_ratio_pct - 45.0) * 0.20, -8.0, 8.0)
            if bt_profit_factor == float("inf"):
                score += 8.0
            elif bt_profit_factor > 0:
                score += _clamp((bt_profit_factor - 1.0) * 8.0, -10.0, 12.0)
            score += _clamp(total_trade_count * 0.35, 0.0, 12.0)
            score += _clamp(wf_fold_count * 0.25, 0.0, 8.0)
            score -= _clamp(max(0.0, wf_avg_max_drawdown_pct - 8.0) * 1.4, 0.0, 20.0)
            score -= _clamp(wf_negative_fold_count * 5.5, 0.0, 22.0)
            score -= _clamp(wf_zero_trade_fold_count * 1.8, 0.0, 10.0)
            score = _clamp(score, 0.0, 100.0)

        hard_block = bool(
            score < SETTINGS.coin_score_hard_block
            or wf_avg_max_drawdown_pct >= 14.0
            or (wf_fold_count > 0 and wf_avg_return_pct < SETTINGS.coin_score_min_wf_avg_return)
            or wf_negative_fold_count > SETTINGS.coin_score_max_negative_folds
        )
        eligible = bool(
            not hard_block
            and
            score >= SETTINGS.coin_score_min
            and total_trade_count >= SETTINGS.coin_score_min_trades
            and wf_negative_fold_count <= SETTINGS.coin_score_max_negative_folds
            and wf_zero_trade_fold_count <= SETTINGS.coin_score_max_zero_trade_folds
        )

        reason_bits: list[str] = []
        if not eligible:
            if score < SETTINGS.coin_score_min:
                reason_bits.append("skor_dusuk")
            if total_trade_count < SETTINGS.coin_score_min_trades:
                reason_bits.append("islem_az")
            if wf_negative_fold_count > SETTINGS.coin_score_max_negative_folds:
                reason_bits.append("negatif_fold_fazla")
            if wf_zero_trade_fold_count > SETTINGS.coin_score_max_zero_trade_folds:
                reason_bits.append("trade_yok")
            if wf_fold_count > 0 and wf_avg_return_pct < SETTINGS.coin_score_min_wf_avg_return:
                reason_bits.append("wf_getiri_zayif")
        if wf_avg_max_drawdown_pct >= 12:
            reason_bits.append("drawdown_yuksek")
        if hard_block:
            reason_bits.append("hard_block")

        rows.append(
            {
                "symbol": symbol,
                "score": round(score, 3),
                "eligible": eligible,
                "hard_block": hard_block,
                "reason": ",".join(reason_bits) if reason_bits else "uygun",
                "bt_trade_count": bt_trade_count,
                "bt_avg_return_pct": round(bt_avg_return_pct, 4),
                "bt_total_return_pct": round(float(bt.get("bt_total_return_pct", 0.0)), 4),
                "bt_win_rate_pct": round(bt_win_rate_pct, 3),
                "bt_profit_factor": round(bt_profit_factor, 4) if bt_profit_factor != float("inf") else float("inf"),
                "bt_net_pnl": round(float(bt.get("bt_net_pnl", 0.0)), 4),
                "wf_fold_count": wf_fold_count,
                "wf_trade_count": wf_trade_count,
                "wf_avg_return_pct": round(wf_avg_return_pct, 4),
                "wf_avg_win_rate_pct": round(wf_avg_win_rate_pct, 3),
                "wf_avg_max_drawdown_pct": round(wf_avg_max_drawdown_pct, 3),
                "wf_negative_fold_count": wf_negative_fold_count,
                "wf_zero_trade_fold_count": wf_zero_trade_fold_count,
                "wf_positive_fold_ratio_pct": round(wf_positive_fold_ratio_pct, 3),
                "total_trade_count": total_trade_count,
            }
        )

    df = pd.DataFrame(rows).sort_values(["eligible", "score", "total_trade_count"], ascending=[False, False, False])
    return df.reset_index(drop=True)


def save_coin_scores(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(SETTINGS.coin_scores_path), exist_ok=True)
    df.to_csv(SETTINGS.coin_scores_path, index=False)


def _profile_report_rows_to_coin_scores(profile_report: pd.DataFrame) -> pd.DataFrame:
    if profile_report.empty or "symbol" not in profile_report.columns:
        return pd.DataFrame()

    rows: list[dict] = []
    for symbol, group in profile_report.groupby(profile_report["symbol"].astype(str).str.upper()):
        ordered = group.sort_values(
            by=[col for col in ("research_score", "wf_avg_return_pct", "bt_total_return_pct") if col in group.columns],
            ascending=False,
        )
        row = ordered.iloc[0]
        bt_trade_count = int(row.get("bt_trade_count", 0))
        wf_trade_count = int(row.get("wf_trade_count", 0))
        total_trade_count = bt_trade_count + wf_trade_count
        wf_fold_count = int(row.get("wf_fold_count", 0))
        bt_total_return_pct = float(row.get("bt_total_return_pct", 0.0))
        wf_avg_return_pct = float(row.get("wf_avg_return_pct", 0.0))
        bt_profit_factor = float(row.get("bt_profit_factor", 0.0))
        wf_avg_max_drawdown_pct = float(row.get("wf_avg_max_drawdown_pct", 0.0))
        research_score = float(row.get("research_score", 0.0))

        score = _clamp(50.0 + research_score * 10.0, 0.0, 100.0)
        hard_block = bool(
            score < SETTINGS.coin_score_hard_block
            or (wf_fold_count > 0 and wf_avg_return_pct < SETTINGS.coin_score_min_wf_avg_return)
        )
        eligible = bool(
            not hard_block
            and score >= SETTINGS.coin_score_min
            and total_trade_count >= SETTINGS.coin_score_min_trades
            and bt_total_return_pct >= 0.0
            and wf_avg_return_pct >= SETTINGS.coin_score_min_wf_avg_return
        )

        reason_bits: list[str] = []
        if score < SETTINGS.coin_score_min:
            reason_bits.append("skor_dusuk")
        if total_trade_count < SETTINGS.coin_score_min_trades:
            reason_bits.append("islem_az")
        if bt_total_return_pct < 0:
            reason_bits.append("bt_getiri_zayif")
        if wf_avg_return_pct < SETTINGS.coin_score_min_wf_avg_return:
            reason_bits.append("wf_getiri_zayif")
        if hard_block:
            reason_bits.append("hard_block")

        rows.append(
            {
                "symbol": symbol,
                "score": round(score, 3),
                "eligible": eligible,
                "hard_block": hard_block,
                "reason": ",".join(reason_bits) if reason_bits else "uygun",
                "bt_trade_count": bt_trade_count,
                "bt_avg_return_pct": round(bt_total_return_pct / max(bt_trade_count, 1), 4) if bt_trade_count else 0.0,
                "bt_total_return_pct": round(bt_total_return_pct, 4),
                "bt_win_rate_pct": 0.0,
                "bt_profit_factor": round(bt_profit_factor, 4) if bt_profit_factor != float("inf") else float("inf"),
                "bt_net_pnl": 0.0,
                "wf_fold_count": wf_fold_count,
                "wf_trade_count": wf_trade_count,
                "wf_avg_return_pct": round(wf_avg_return_pct, 4),
                "wf_avg_win_rate_pct": round(float(row.get("wf_avg_win_rate_pct", 0.0)), 3),
                "wf_avg_max_drawdown_pct": round(wf_avg_max_drawdown_pct, 3),
                "wf_negative_fold_count": 0,
                "wf_zero_trade_fold_count": max(0, wf_fold_count - (1 if wf_trade_count > 0 else 0)),
                "wf_positive_fold_ratio_pct": 0.0,
                "total_trade_count": total_trade_count,
            }
        )
    return pd.DataFrame(rows)


def merge_profile_report_into_coin_scores(profile_report_path: str) -> pd.DataFrame:
    report = _safe_load_csv(profile_report_path)
    if report is None or report.empty:
        return load_coin_scores() or pd.DataFrame()

    profile_scores = _profile_report_rows_to_coin_scores(report)
    existing = load_coin_scores()
    if existing is None or existing.empty:
        merged = profile_scores
    else:
        remaining = existing.loc[~existing["symbol"].astype(str).isin(profile_scores["symbol"].astype(str))].copy()
        merged = pd.concat([remaining, profile_scores], ignore_index=True)
        merged = merged.sort_values(["eligible", "score", "total_trade_count"], ascending=[False, False, False]).reset_index(drop=True)
    save_coin_scores(merged)
    return merged


def refresh_coin_scores(
    backtest_trades: pd.DataFrame | None = None,
    walkforward: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if backtest_trades is None:
        backtest_trades = _safe_load_csv(SETTINGS.backtest_trades_path)
    if walkforward is None:
        walkforward = _safe_load_csv(SETTINGS.walkforward_results_path)
    scores = compute_coin_scores(backtest_trades=backtest_trades, walkforward=walkforward)
    save_coin_scores(scores)
    return scores


def load_coin_scores() -> pd.DataFrame | None:
    return _safe_load_csv(SETTINGS.coin_scores_path)


def live_entry_guard(symbol: str, scores: pd.DataFrame | None = None) -> tuple[bool, str]:
    if not SETTINGS.live_require_score_guard:
        return True, ""

    scores = load_coin_scores() if scores is None else scores
    if scores is None or scores.empty or "symbol" not in scores.columns:
        return False, "coin_score_yok"

    scoped = scores.loc[scores["symbol"].astype(str).str.upper() == symbol.upper()]
    if scoped.empty:
        return False, "coin_score_satiri_yok"

    row = scoped.iloc[0]
    hard_block = bool(row.get("hard_block", False))
    score = float(row.get("score", 0.0))
    eligible = bool(row.get("eligible", False))
    reason = str(row.get("reason", "")).strip()

    if SETTINGS.live_block_on_hard_block and hard_block:
        return False, reason or "hard_block"
    if score < SETTINGS.live_min_coin_score:
        return False, reason or "canli_skor_dusuk"
    if not eligible:
        return False, reason or "coin_eligible_degil"
    return True, ""


def select_tradeable_symbols(configured_symbols: tuple[str, ...] | None = None) -> tuple[tuple[str, ...], pd.DataFrame | None]:
    configured = tuple(symbol.upper() for symbol in (configured_symbols or SETTINGS.trading_symbols()))
    scores = load_coin_scores()
    if scores is None or scores.empty or "symbol" not in scores.columns:
        primary = SETTINGS.primary_symbol()
        return ((primary,) if primary in configured else configured[:1]), scores

    scoped = scores[scores["symbol"].isin(configured)].copy()
    if scoped.empty:
        primary = SETTINGS.primary_symbol()
        return ((primary,) if primary in configured else configured[:1]), scores
    if "hard_block" not in scoped.columns:
        scoped["hard_block"] = False
    primary = SETTINGS.primary_symbol()
    secondaries = set(SETTINGS.secondary_symbols())

    selected: list[str] = []
    primary_row = scoped.loc[scoped["symbol"] == primary]
    if not primary_row.empty:
        row = primary_row.iloc[0]
        if bool(row.get("eligible", False)) and not bool(row.get("hard_block", False)):
            selected.append(primary)

    for symbol in configured:
        if symbol == primary or symbol not in secondaries:
            continue
        symbol_row = scoped.loc[scoped["symbol"] == symbol]
        if symbol_row.empty:
            continue
        row = symbol_row.iloc[0]
        if bool(row.get("hard_block", False)):
            continue
        if not bool(row.get("eligible", False)):
            continue
        if float(row.get("score", 0.0)) < SETTINGS.secondary_symbol_min_score:
            continue
        if float(row.get("bt_total_return_pct", 0.0)) <= SETTINGS.secondary_symbol_min_bt_return:
            continue
        if float(row.get("wf_avg_return_pct", 0.0)) <= SETTINGS.secondary_symbol_min_wf_return:
            continue
        selected.append(symbol)

    return tuple(selected), scoped
