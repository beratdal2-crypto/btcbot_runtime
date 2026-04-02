import joblib
import pandas as pd
import json
import os
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from data import get_orderbook_imbalance, get_research_klines_df
from features import build_features, FEATURE_COLUMNS
from config import SETTINGS


def _safe_imbalance(symbol: str) -> float:
    try:
        return float(get_orderbook_imbalance(symbol=symbol))
    except Exception as exc:
        print(f"[TRAIN] {symbol} imbalance fallback: {exc}")
        return 0.0


def train_model_on_df(df):
    X = df[FEATURE_COLUMNS]
    y = df["target"]

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=10,
        min_samples_split=12,
        min_samples_leaf=6,
        max_features="sqrt",
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X, y)
    return model


def _symbol_model_path(symbol: str) -> str:
    return os.path.join(SETTINGS.symbol_model_dir, f"{symbol.upper()}.pkl")


def _strategy_model_path(strategy_name: str) -> str:
    if strategy_name == "mean_reversion":
        return SETTINGS.mean_reversion_model_path
    return SETTINGS.trend_model_path


def build_training_frame() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in SETTINGS.trading_symbols():
        try:
            imbalance = _safe_imbalance(symbol)
            raw = get_research_klines_df(limit=SETTINGS.training_lookback_limit, symbol=symbol)
            df = build_features(raw, imbalance=imbalance, symbol=symbol)
        except Exception as exc:
            print(f"[TRAIN] {symbol} skipped: {exc}")
            continue
        if df.empty:
            continue
        df["symbol"] = symbol
        frames.append(df)
    if not frames:
        raise ValueError("Egitim icin kullanilabilir veri bulunamadi.")
    return pd.concat(frames, ignore_index=True)


def build_symbol_training_frames() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in SETTINGS.trading_symbols():
        try:
            imbalance = _safe_imbalance(symbol)
            raw = get_research_klines_df(limit=SETTINGS.training_lookback_limit, symbol=symbol)
            df = build_features(raw, imbalance=imbalance, symbol=symbol)
        except Exception as exc:
            print(f"[TRAIN] {symbol} skipped: {exc}")
            continue
        if df.empty:
            continue
        df["symbol"] = symbol
        frames[symbol] = df
    return frames


def build_strategy_training_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    trend_mask = (
        (pd.to_numeric(df.get("ema20"), errors="coerce") > pd.to_numeric(df.get("ema50"), errors="coerce"))
        & (pd.to_numeric(df.get("price_vs_ema20"), errors="coerce") >= -0.003)
        & (pd.to_numeric(df.get("volume_ratio"), errors="coerce") >= 0.80)
    )
    breakout_mask = (
        (pd.to_numeric(df.get("breakout_up_20"), errors="coerce") >= SETTINGS.breakout_min_breakout_up_20 * 0.5)
        & (pd.to_numeric(df.get("close_location"), errors="coerce") >= max(0.44, SETTINGS.breakout_min_close_location - 0.10))
        & (pd.to_numeric(df.get("range_efficiency"), errors="coerce") >= max(0.28, SETTINGS.breakout_min_range_efficiency - 0.12))
        & (pd.to_numeric(df.get("volume_ratio"), errors="coerce") >= max(0.72, SETTINGS.breakout_min_volume_ratio - 0.25))
        & (pd.to_numeric(df.get("signed_volume_proxy"), errors="coerce") >= max(0.01, SETTINGS.breakout_min_signed_volume_proxy - 0.05))
    )
    ont_breakout_mask = breakout_mask & (df.get("symbol") == "ONTUSDT")
    trend_df = df[trend_mask | breakout_mask | ont_breakout_mask].copy()
    mean_reversion_df = df[
        (
            (pd.to_numeric(df.get("rsi"), errors="coerce") <= SETTINGS.mean_reversion_rsi_max + 6)
            | (pd.to_numeric(df.get("bb_pos"), errors="coerce") <= SETTINGS.mean_reversion_bb_pos_max + 0.10)
            | (pd.to_numeric(df.get("range_pos_20"), errors="coerce") <= SETTINGS.mean_reversion_range_pos_max + 0.10)
        )
        & (pd.to_numeric(df.get("price_vs_ema20"), errors="coerce") <= 0.001)
    ].copy()
    return {
        "trend": trend_df,
        "mean_reversion": mean_reversion_df,
    }


def _train_validation_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) < 50:
        return df, df
    split_index = max(20, int(len(df) * 0.8))
    return df.iloc[:split_index].copy(), df.iloc[split_index:].copy()


def _build_training_report(model, train_df: pd.DataFrame, valid_df: pd.DataFrame) -> dict:
    X_valid = valid_df[FEATURE_COLUMNS]
    y_valid = valid_df["target"]
    prob_up = model.predict_proba(X_valid)[:, 1]
    pred = (prob_up >= 0.5).astype(int)
    report = {
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(valid_df)),
        "accuracy": float(accuracy_score(y_valid, pred)) if len(valid_df) else 0.0,
        "brier_score": float(brier_score_loss(y_valid, prob_up)) if len(valid_df) else 0.0,
        "log_loss": float(log_loss(y_valid, prob_up, labels=[0, 1])) if len(valid_df) else 0.0,
        "roc_auc": float(roc_auc_score(y_valid, prob_up)) if len(valid_df) and y_valid.nunique() > 1 else 0.0,
    }
    if len(valid_df) and y_valid.nunique() > 1:
        frac_pos, mean_pred = calibration_curve(y_valid, prob_up, n_bins=5, strategy="uniform")
        calibration_rows = []
        ece = 0.0
        for actual, predicted in zip(frac_pos, mean_pred):
            calibration_rows.append({"mean_pred": float(predicted), "frac_pos": float(actual)})
            ece += abs(float(actual) - float(predicted))
        report["expected_calibration_error"] = float(ece / max(len(calibration_rows), 1))
        report["calibration_curve"] = calibration_rows
    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        top_features = sorted(zip(FEATURE_COLUMNS, importances), key=lambda item: item[1], reverse=True)[:10]
        report["top_features"] = [{"feature": name, "importance": float(value)} for name, value in top_features]
    return report


def _save_training_report(report: dict, model) -> None:
    os.makedirs(os.path.dirname(SETTINGS.training_report_path), exist_ok=True)
    with open(SETTINGS.training_report_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        pd.DataFrame(
            [{"feature": feature, "importance": float(value)} for feature, value in zip(FEATURE_COLUMNS, importances)]
        ).sort_values("importance", ascending=False).to_csv(SETTINGS.feature_importance_path, index=False)


def train_model() -> None:
    symbol_frames = build_symbol_training_frames()
    if not symbol_frames:
        raise ValueError("Egitim icin kullanilabilir veri bulunamadi.")
    df = pd.concat(symbol_frames.values(), ignore_index=True)
    train_df, valid_df = _train_validation_split(df)
    model = train_model_on_df(train_df)
    joblib.dump(model, SETTINGS.model_path)
    report = _build_training_report(model, train_df, valid_df)
    symbol_reports: list[dict] = []
    strategy_reports: list[dict] = []
    os.makedirs(SETTINGS.symbol_model_dir, exist_ok=True)
    for symbol, symbol_df in symbol_frames.items():
        if len(symbol_df) < SETTINGS.symbol_min_training_rows:
            symbol_reports.append({"symbol": symbol, "rows": int(len(symbol_df)), "trained": False, "reason": "veri_az"})
            continue
        sym_train, sym_valid = _train_validation_split(symbol_df)
        symbol_model = train_model_on_df(sym_train)
        model_path = _symbol_model_path(symbol)
        joblib.dump(symbol_model, model_path)
        symbol_report = _build_training_report(symbol_model, sym_train, sym_valid)
        symbol_reports.append(
            {
                "symbol": symbol,
                "rows": int(len(symbol_df)),
                "trained": True,
                "model_path": model_path,
                "accuracy": symbol_report.get("accuracy", 0.0),
                "roc_auc": symbol_report.get("roc_auc", 0.0),
            }
        )
    strategy_frames = build_strategy_training_frames(df)
    for strategy_name, strategy_df in strategy_frames.items():
        if len(strategy_df) < SETTINGS.strategy_model_min_rows:
            strategy_reports.append(
                {
                    "strategy": strategy_name,
                    "rows": int(len(strategy_df)),
                    "trained": False,
                    "reason": "veri_az",
                }
            )
            continue
        strat_train, strat_valid = _train_validation_split(strategy_df)
        strategy_model = train_model_on_df(strat_train)
        model_path = _strategy_model_path(strategy_name)
        joblib.dump(strategy_model, model_path)
        strategy_report = _build_training_report(strategy_model, strat_train, strat_valid)
        strategy_reports.append(
            {
                "strategy": strategy_name,
                "rows": int(len(strategy_df)),
                "trained": True,
                "model_path": model_path,
                "accuracy": strategy_report.get("accuracy", 0.0),
                "roc_auc": strategy_report.get("roc_auc", 0.0),
            }
        )
    report["symbol_models"] = symbol_reports
    report["strategy_models"] = strategy_reports
    _save_training_report(report, model)
    pd.DataFrame(symbol_reports).to_csv(SETTINGS.symbol_training_report_path, index=False)
    print(f"Model saved: {SETTINGS.model_path}")
    print(f"Training report: {SETTINGS.training_report_path}")


if __name__ == "__main__":
    train_model()
