from stable_baselines3 import PPO
from rl_env import TradingEnv
from config import SETTINGS


def normalize_rl_action(action) -> int:
    if int(action) == 1:
        return 1
    if int(action) == 2:
        return -1
    return 0


def get_rl_action_from_df(df, model=None) -> int:
    model = model or PPO.load(SETTINGS.rl_model_path)
    env = TradingEnv(df)
    obs, _ = env.reset()
    action, _ = model.predict(obs, deterministic=True)
    return normalize_rl_action(action)
