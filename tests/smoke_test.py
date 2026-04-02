from pathlib import Path

REQUIRED = [
    "config.py",
    "data.py",
    "features.py",
    "trainer.py",
    "rl_train.py",
    "main.py",
    "dashboard.py",
    "backtest.py",
]

for item in REQUIRED:
    assert Path(item).exists(), f"Eksik dosya: {item}"

print("Smoke test OK")
