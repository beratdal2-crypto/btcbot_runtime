from stable_baselines3 import PPO
import pandas as pd
from data import get_orderbook_imbalance, get_research_klines_df
from features import build_features
from rl_env import TradingEnv
from config import SETTINGS


def _safe_imbalance(symbol: str) -> float:
    try:
        return float(get_orderbook_imbalance(symbol=symbol))
    except Exception as exc:
        print(f"[RL] {symbol} imbalance fallback: {exc}")
        return 0.0


def train_rl_model_on_df(df, total_timesteps: int = 20000):
    env = TradingEnv(df)
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=total_timesteps)
    return model


def build_rl_training_frame() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in SETTINGS.trading_symbols():
        try:
            imbalance = _safe_imbalance(symbol)
            raw = get_research_klines_df(limit=SETTINGS.training_lookback_limit, symbol=symbol)
            df = build_features(raw, imbalance=imbalance)
        except Exception as exc:
            print(f"[RL] {symbol} skipped: {exc}")
            continue
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        raise ValueError("RL egitimi icin kullanilabilir veri bulunamadi.")
    return pd.concat(frames, ignore_index=True)


def train_rl() -> None:
    df = build_rl_training_frame()
    model = train_rl_model_on_df(df, total_timesteps=20000)
    model.save(SETTINGS.rl_model_path)
    print(f"RL model saved: {SETTINGS.rl_model_path}")


if __name__ == "__main__":
    train_rl()
