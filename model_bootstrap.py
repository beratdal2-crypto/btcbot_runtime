from __future__ import annotations

import os
from dataclasses import dataclass

import joblib
import numpy as np

from config import SETTINGS


@dataclass
class ConstantProbabilityModel:
    prob_up: float = 0.5

    def predict_proba(self, x):
        n = len(x) if hasattr(x, "__len__") else 1
        p = float(min(max(self.prob_up, 0.01), 0.99))
        down = 1.0 - p
        return np.column_stack((np.full(n, down), np.full(n, p)))


def ensure_base_models() -> list[str]:
    os.makedirs("models", exist_ok=True)
    created: list[str] = []
    defaults = [
        SETTINGS.model_path,
        SETTINGS.trend_model_path,
        SETTINGS.mean_reversion_model_path,
    ]
    for path in defaults:
        if not os.path.exists(path):
            joblib.dump(ConstantProbabilityModel(prob_up=0.5), path)
            created.append(path)
    return created
