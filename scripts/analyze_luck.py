#!/usr/bin/env python3
"""Remove luck from the record: what part of a win/loss record is repeatable skill, and what is noise?

Outputs data/derived/luck.json
"""
from __future__ import annotations

import json
import math
import os
import traceback

import numpy as np
import pandas as pd
from scipy import stats as sps

from lib import data as D
from lib import stats as S

DERIVED = os.path.join("data", "derived")
PYTH_EXP = 2.37  # Bill James' Pythagorean exponent as applied to the NFL
GAMMA = 0.5772156649  # Euler-Mascheroni, in the Bailey & Lopez de Prado expected-maximum formula


def expected_max_sharpe(k: int, n: int = 1000) -> float:
    """Expected maximum per-bet Sharpe of k zero-skill strategies.

    Bailey & Lopez de Prado's extreme-value approximation, scaled by sqrt(1/n) with n bets.
    For k = 1 the expected maximum is the mean of a single draw, i.e. exactly 0; the approximation
    is undefined there, and the earlier build wrote -Infinity, which is neither a probability
    statement nor valid JSON.
    """
    if k <= 1:
        return 0.0
    return math.sqrt(1.0 / n) * ((1 - GAMMA) * sps.norm.ppf(1 - 1 / k)
                                 + GAMMA * sps.norm.ppf(1 - 1 / (k * math.e)))


def main() -> None:
    games, _ = D.load_games()
    tg = D.team_game_rows(games)
    out: dict = {}

    # ---------------------------------------------------------------- Pythagorean luck
    ts = tg.groupby(["season", "team"], as_index=False).agg(
        gp=("pf", "size"), pf=("pf", "sum"), pa=("pa", "sum"), wins=("margin", lambda s: float((s > 0).sum())),
        ties=("margin", lambda s: float((s == 0).sum())),
    )
    ts = ts[ts["gp"] >= 8].copy()
    ts["exp_win_pct"] = ts["pf"] ** PYTH_EXP / (ts["pf"] ** PYTH_EXP + ts["pa"] ** PYTH_EXP)
    ts["exp_wins"] = ts["exp_win_pct"] * ts["gp"]
    ts["luck_wins"] = ts["wins"] - ts["exp_wins"]
    ts["actual_win_pct"] = ts["wins"] / ts["gp"]
    r2 = float(np.corrcoef(ts["exp_win_pct"], ts["actual_win_pct"])[0, 1] ** 2)
    out["pythagorean"] = {
        "exponent": PYTH_EXP,
        "team_seasons": int(len(ts)),
        "seasons": [int(ts["season"].min()), int(ts["season"].max())],
        "r2_expected_vs_actual_win_pct": round(r2, 4),
        "sd_luck_wins": round(float(ts["luck_wins"].std(ddof=1)), 3),
        "mean_abs_luck_wins": round(float(ts["luck_wins"].abs().mean()), 3),
        "definition": "luck_wins = actual wins - Pythagorean expected wins over the same games",
        "method_source": "Bill James Pythagorean expectation; exponent 2.37 is the value used for the NFL in the literature",
    }

    # does luck persist? if it does, it is skill; if not, it is noise
    ts = ts.sort_values(["team", "season"])
    ts["next_luck"] = ts.groupby("team")["luck_wins"].shift(-1)
    ts["next_season"] = ts.groupby("team")["season"].shift(-1)
    pairs = ts[(ts["next_season"] == ts["season"] + 1)].dropna(subset=["next_luck"])
    persist = S.corr_pair(pairs["luck_wins"].to_numpy(float), pairs["next_luck"].to_numpy(float))
    out["luck_persistence"] = {**persist,
                              "label": "Year-over-year correlation of Pythagorean luck (wins)",
                              "interpretation": ("Near zero means last season's luck did not carry "
                                                 "forward: the deviation was noise, not skill.")}

    # one-score games: the classic luck proxy
    tg["one_score"] = (tg["margin"].abs() <= 8).astype(int)
    os_games = tg[tg["one_score"] == 1]
    per_team = os_games.groupby(["season", "team"], as_index=False).agg(
        n=("margin", "size"), wins=("margin", lambda s: float((s > 0).sum())))
    per_team = per_team[per_team["n"] >= 3]
    per_team["rate"] = per_team["wins"] / per_team["n"]
    out["one_score_games"] = {
        "n_team_seasons": int(len(per_team)),
        "mean_win_rate": round(float(per_team["rate"].mean()), 4),
        "sd_win_rate": round(float(per_team["rate"].std(ddof=1)), 4),
        "share_of_games": round(float(tg["one_score"].mean()), 4),
        "note": "A team that wins most one-score games is mostly lucky; the rate should regress hard.",
    }
    per_team = per_team.sort_values(["team", "season"])
    per_team["next_rate"] = per_team.groupby("team")["rate"].shift(-1)
    per_team["next_season"] = per_team.groupby("team")["season"].shift(-1)
    p2 = per_team[per_team["next_season"] == per_team["season"] + 1].dropna(subset=["next_rate"])
    out["one_score_persistence"] = {**S.corr_pair(p2["rate"].to_numpy(float), p2["next_rate"].to_numpy(float)),
                                   "label": "Year-over-year correlation of one-score win rate"}

    # ---------------------------------------------------------------- variance decomposition
    out["variance_decomposition"] = {
        "note": ("Share of variance in season win% explained by point differential, and by "
                 "Pythagorean expectation. The unexplained part is the luck budget."),
        "r2_point_diff": round(float(np.corrcoef(ts["pf"] - ts["pa"], ts["actual_win_pct"])[0, 1] ** 2), 4),
        "r2_pythagorean": round(r2, 4),
        "unexplained_share": round(1 - r2, 4),
        "sd_actual_win_pct": round(float(ts["actual_win_pct"].std(ddof=1)), 4),
        "sd_expected_win_pct": round(float(ts["exp_win_pct"].std(ddof=1)), 4),
    }

    # ---------------------------------------------------------------- pooled ATS identity (and the real test elsewhere)
    # NOTE (integration session arena/193e54ca-korea2, 2026-11-13, flag FL-DH-01): pooling every
    # team-game with its own negation makes the cover rate exactly 0.5 for ANY dataset, so this
    # block is an arithmetic identity, not a test. It is kept only for bookkeeping. The real ATS
    # tilt test — one observation per game — is market.json -> ats_home_cover.
    ats = tg.dropna(subset=["ats_margin"])
    ats = ats[ats["ats_margin"] != 0]
    k, n = int((ats["ats_margin"] > 0).sum()), int(len(ats))
    lo, hi = S.wilson_ci(k, n)
    out["ats_coin_flip_test"] = {
        "n": n, "wins": k, "rate": round(k / n, 4), "ci": [round(lo, 4), round(hi, 4)],
        "binomial_p_vs_50": round(S.binomial_p(k, n), 4),
        "is_identity": True,
        "note": ("Arithmetic identity (flag FL-DH-01): every team-game is pooled twice, once as "
                 "+margin and once as -margin, so exactly one of each pair covers and the rate is "
                 "0.5 for every possible dataset. Not evidence about the market. The real tilt "
                 "test is one observation per game: market.json -> ats_home_cover."),
    }

    # ---------------------------------------------------------------- how much sample is enough
    edges = [0.51, 0.52, 0.524, 0.53, 0.55, 0.57]
    out["sample_size_requirements"] = {
        "note": ("Bets needed for 80% power at alpha=0.05 to detect a true win rate, two-sided, "
                 "against a null of 50%. Uses the standard normal approximation."),
        "rows": [{"true_win_rate": e, "bets_needed": S.min_sample_size(e, 0.50)} for e in edges],
        "breakeven_win_rate_at_minus_110": 0.5238,
        "breakeven_note": "100/210 = 52.38% is the break-even rate at -110.",
    }

    # ---------------------------------------------------------------- deflated significance
    out["multiple_testing"] = {
        "note": ("With k candidate strategies tested, the best one will look good by chance. "
                 "The deflated-Sharpe threshold is the Sharpe a zero-skill strategy would be "
                 "expected to reach as the maximum of k tries."),
        "rows": [{"strategies_tested": k_,
                  "expected_max_sharpe_per_bet_under_null": round(expected_max_sharpe(k_), 4)}
                 for k_ in (1, 5, 10, 25, 50, 100)],
        "assumption": "per-bet Sharpe variance approximated as 1/n with n=1000 bets",
    }

    # ---------------------------------------------------------------- luck-adjusted records
    adj = ts[ts["season"] >= 2023].copy()
    adj = adj.sort_values(["season", "luck_wins"], ascending=[True, False])
    out["luck_table_recent"] = [
        {"season": int(r.season), "team": r.team, "wins": float(r.wins), "gp": int(r.gp),
         "exp_wins": round(float(r.exp_wins), 2), "luck_wins": round(float(r.luck_wins), 2)}
        for r in adj.itertuples()
    ]

    with open(os.path.join(DERIVED, "luck.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps({k: out[k] for k in ("pythagorean", "luck_persistence", "one_score_persistence",
                                          "ats_coin_flip_test", "variance_decomposition")}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "luck.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        raise SystemExit(1)
