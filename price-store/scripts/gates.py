"""Demotion gate: sends a live strategy back to paper when its SIGNAL is shown to be bad.

Design rules (PROPOSED: thresholds and method are a proposal, not an official standard):

1. The signal is judged on closing-line value (CLV), not on profit. CLV for one bet is
   ``p_close - p_bet`` where ``p`` is the raw American-odds implied probability. Positive CLV
   means the bet was priced better than the closing line.
2. Staking (ROI, bankroll path, stake sizes) is reported in its own block and is NEVER an input
   to the demotion decision. A lucky staking run therefore cannot keep a bad signal live.
3. Demotion fires only when the sample is large enough (N_MIN) AND the one-sided 95% upper
   bound of mean CLV is below zero. Below N_MIN the state is HOLD, never demote on noise.
4. Pushes count toward CLV (the line still existed) and are excluded from ROI.

Pure standard library. Nothing in this file is real data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

N_MIN = 200          # PROPOSED minimum settled bets before any demotion decision
Z_ONE_SIDED_95 = 1.645

DECISION_HOLD = "HOLD"                 # sample too small; state unchanged
DECISION_KEEP_LIVE = "KEEP_LIVE"       # large sample, upper CLV bound >= 0
DECISION_DEMOTE = "DEMOTE_TO_PAPER"    # large sample, upper CLV bound < 0


def implied_prob(american: float) -> float:
    """Raw implied probability from American odds (vig is NOT removed)."""
    if american == 0:
        raise ValueError("American odds cannot be 0")
    if american < 0:
        return -american / (-american + 100.0)
    return 100.0 / (american + 100.0)


def clv(bet_price: float, close_price: float) -> float:
    """Positive = bet was priced better than the closing line."""
    return implied_prob(close_price) - implied_prob(bet_price)


def _mean_sd(xs: Sequence[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var)


@dataclass(frozen=True)
class Bet:
    bet_price: float      # American odds taken
    close_price: float    # American odds at the close for the same side
    stake: float          # units risked
    profit: float         # units won (negative on a loss, 0 on a push)
    result: str           # "W", "L" or "P"


def evaluate(bets: Iterable[Bet], current_state: str = "live") -> dict:
    """Return the demotion decision plus separated signal and staking blocks."""
    bets = list(bets)
    if current_state != "live":
        raise ValueError("the demotion gate only applies to strategies that are currently live")

    clvs = [clv(b.bet_price, b.close_price) for b in bets]
    n = len(clvs)
    mean_clv, sd_clv = _mean_sd(clvs)
    upper = mean_clv + Z_ONE_SIDED_95 * sd_clv / math.sqrt(n) if n >= 2 else float("nan")

    # ---- signal block (the only input to the decision) ----
    if n < N_MIN:
        decision = DECISION_HOLD
    elif upper < 0:
        decision = DECISION_DEMOTE
    else:
        decision = DECISION_KEEP_LIVE

    # ---- staking block (informational only, never changes the decision) ----
    staked = [b for b in bets if b.result != "P"]
    total_stake = sum(b.stake for b in staked)
    total_profit = sum(b.profit for b in staked)
    roi = total_profit / total_stake if total_stake else float("nan")

    return {
        "decision": decision,
        "n_bets": n,
        "n_min": N_MIN,
        "signal": {
            "metric": "mean closing-line value (probability points)",
            "mean_clv": mean_clv,
            "sd_clv": sd_clv,
            "upper_95_one_sided": upper,
            "drives_decision": True,
        },
        "staking": {
            "metric": "ROI on non-push stake",
            "roi": roi,
            "staked_bets": len(staked),
            "drives_decision": False,
        },
    }
