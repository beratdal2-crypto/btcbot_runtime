from __future__ import annotations
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

RL_COLUMNS = ["return", "rsi", "vol", "imbalance", "micro_return", "atr_pct"]


class TradingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df.reset_index(drop=True)
        self.idx = 0
        self.action_space = spaces.Discrete(3)  # 0 HOLD, 1 BUY, 2 SELL
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(len(RL_COLUMNS),), dtype=np.float32
        )

    def _get_obs(self):
        row = self.df.iloc[self.idx]
        return np.array([row[c] for c in RL_COLUMNS], dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.idx = 0
        return self._get_obs(), {}

    def step(self, action):
        price_now = float(self.df.iloc[self.idx]["c"])
        self.idx += 1
        done = self.idx >= len(self.df) - 2
        price_next = float(self.df.iloc[self.idx]["c"])

        if action == 1:
            raw_reward = (price_next - price_now) / price_now
        elif action == 2:
            raw_reward = (price_now - price_next) / price_now
        else:
            raw_reward = 0.0

        vol_penalty = float(self.df.iloc[self.idx]["vol"]) * 0.1
        reward = raw_reward - vol_penalty
        return self._get_obs(), reward, done, False, {}
