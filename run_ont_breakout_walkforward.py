from __future__ import annotations

from walkforward import run_walkforward


def main() -> None:
    run_walkforward(
        profile_name="ont_15m_breakout",
        symbols=("ONTUSDT",),
        output_path="logs/ont_15m_breakout_walkforward.csv",
        refresh_scores=False,
    )


if __name__ == "__main__":
    main()
