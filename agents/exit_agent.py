from config import SETTINGS


def should_signal_exit(
    position_side: str | None,
    regime: str,
    trend: int,
    scalp: int,
    rl_action: int,
    prob_up: float,
) -> bool:
    if not SETTINGS.enable_signal_exit:
        return False
    if position_side != "LONG":
        return False
    if regime == "DOWNTREND":
        return True
    if trend < 0 and scalp < 0:
        return True
    if prob_up <= SETTINGS.signal_exit_prob_threshold and rl_action < 0:
        return True
    return False
