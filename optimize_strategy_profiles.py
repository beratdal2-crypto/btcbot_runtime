from __future__ import annotations

from optimize_parameters import run_optimization
from research_profiles import profile_names


def run_profile_optimizations() -> None:
    for profile in profile_names():
        print(f"[PROFILE_OPTIMIZER] profile={profile}")
        run_optimization(profile_name=profile, symbols=("BTCUSDT",), output_prefix=f"btc_{profile}")


if __name__ == "__main__":
    run_profile_optimizations()
