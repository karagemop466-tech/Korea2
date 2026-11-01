#!/usr/bin/env python3
"""Removing luck from the equation.

Five independent attacks on chance:
  1. Null bettor simulation    - where a zero-edge bettor's ROI distribution sits.
  2. Skill/luck variance split - beta-binomial on team-season ATS records.
  3. Persistence tests         - split-half and year-over-year reliability.
  4. Per-strategy luck share   - observed season-to-season spread vs pure chance.
  5. Evidence requirements     - how many bets a real edge needs before it is
                                 distinguishable from noise (this is what sets
                                 gate G1).

Outputs data/derived/luck.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nflcore as nc

OUT = nc.DERIVED / "luck.json"
MD = lambda x, n=4: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


def null_bettors(n_bets=1000, n_sims=20000, odds=-110, seed=5):
    rng = np.random.default_rng(seed)
    dec = nc.american_to_decimal(odds)
    wins = rng.binomial(n_bets, 0.5, size=n_sims)
    roi = (wins * (dec - 1) - (n_bets - wins)) / n_bets
    best_of = roi.reshape(-1, 100).max(axis=1) if n_sims % 100 == 0 else roi
    return {
        "n_bets_per_bettor": n_bets, "n_bettors": int(n_sims), "price": odds,
        "roi_mean": MD(roi.mean()), "roi_sd": MD(roi.std(), 5),
        "p05": MD(np.percentile(roi, 5)), "p50": MD(np.percentile(roi, 50)),
        "p95": MD(np.percentile(roi, 95)), "p99": MD(np.percentile(roi, 99)),
        "best_of_100_mean": MD(best_of.mean()),
        "p_roi_above_5pct": MD(float((roi > 0.05).mean()), 5),
        "p_roi_above_10pct": MD(float((roi > 0.10).mean()), 5),
        "histogram": [{"bucket": f"{lo:.0f}% to {lo + 2:.0f}%",
                       "count": int(((roi * 100 >= lo) & (roi * 100 < lo + 2)).sum())}
                      for lo in range(-14, 14, 2)],
    }


def _team_ats_frame(g):
    lg = pd.concat([
        g[["game_id", "season", "week", "home_team", "home_margin", "home_line"]].rename(
            columns={"home_team": "team"}),
        g[["game_id", "season", "week", "away_team", "home_margin", "home_line"]].assign(
            home_margin=lambda d: -d.home_margin,
            home_line=lambda d: -d.home_line).rename(columns={"away_team": "team"})],
        ignore_index=True)
    lg = lg[lg.home_margin + lg.home_line != 0]
    lg["hit"] = (lg.home_margin + lg.home_line) > 0
    return lg


def skill_variance(g, n_perm=300, seed=17):
    """Split team-season ATS dispersion into skill + chance.

    The chance benchmark is a PERMUTATION null, not a binomial: every game
    produces exactly one ATS winner, so the two teams' outcomes are negatively
    dependent and a naive binomial over-states the expected dispersion.
    """
    lg = _team_ats_frame(g)
    d = lg.groupby(["season", "team"]).agg(n=("hit", "size"), wins=("hit", "sum")).reset_index()
    d = d[d.n >= 8]
    p_bar = d.wins.sum() / d.n.sum()
    obs_var = float(((d.wins / d.n - p_bar) ** 2).mean())

    rng = np.random.default_rng(seed)
    null_vars = []
    games = lg.groupby("game_id").hit.apply(list)
    keys = list(games.index)
    season_of = lg.drop_duplicates("game_id").set_index("game_id").season
    base = lg[["game_id", "season", "team", "hit"]].copy()
    for _ in range(n_perm):
        # flip the winner of a random subset of games (keeps one winner per game)
        flip = rng.random(len(keys)) < 0.5
        fl = dict(zip(keys, flip))
        sim = base.copy()
        sim["hit"] = np.where(sim.game_id.map(fl), ~sim.hit, sim.hit)
        dd = sim.groupby(["season", "team"]).agg(n=("hit", "size"), wins=("hit", "sum")).reset_index()
        dd = dd[dd.n >= 8]
        null_vars.append(float(((dd.wins / dd.n - p_bar) ** 2).mean()))
    null_mean = float(np.mean(null_vars))
    skill_var = obs_var - null_mean
    return {
        "team_seasons": int(len(d)),
        "mean_ats_rate": MD(p_bar),
        "observed_var_of_rates": MD(obs_var, 6),
        "permutation_chance_var": MD(null_mean, 6),
        "permutation_chance_var_sd": MD(float(np.std(null_vars)), 6),
        "skill_var": MD(max(skill_var, 0.0), 6),
        "luck_share_of_variance": MD(min(1.0, null_mean / obs_var), 4),
        "skill_sd_win_rate": MD(math.sqrt(max(skill_var, 0.0)), 4),
        "implied_95pct_skill_band": [MD(p_bar - 1.96 * math.sqrt(max(skill_var, 0.0))),
                                     MD(p_bar + 1.96 * math.sqrt(max(skill_var, 0.0)))],
        "games_per_team_season_mean": MD(d.n.mean(), 1),
        "verdict": ("no detectable team-level ATS skill" if skill_var <= 0 else
                    "small but non-zero team-level ATS skill"),
        "note": ("The chance benchmark comes from 300 permutations that reassign ATS winners "
                 "inside each game, so it respects the one-winner-per-game constraint. The "
                 "observed dispersion of team-season ATS rates is not larger than that benchmark "
                 "unless skill_var > 0."),
    }


def persistence(g):
    """Split-half and year-over-year reliability of team ATS performance."""
    lg = _team_ats_frame(g)
    lg["half"] = np.where(lg.week <= lg.week.max() / 2, "first", "second")
    piv = lg.pivot_table(index=["season", "team"], columns="half", values="hit", aggfunc="mean")
    piv = piv.dropna()
    r_half = float(piv["first"].corr(piv["second"])) if len(piv) > 10 else float("nan")
    n_pairs = int(len(piv))
    sb = 2 * r_half / (1 + r_half) if np.isfinite(r_half) else float("nan")

    by_season = lg.groupby(["season", "team"]).hit.mean().reset_index().sort_values(["team", "season"])
    by_season["prev"] = by_season.groupby("team").hit.shift(1)
    yy = by_season.dropna()
    r_yy = float(yy.hit.corr(yy.prev)) if len(yy) > 10 else float("nan")
    return {
        "split_half_r": MD(r_half), "split_half_n": n_pairs,
        "spearman_brown_reliability": MD(sb),
        "year_over_year_r": MD(r_yy), "year_over_year_n": int(len(yy)),
        "interpretation": ("Split-half reliability near zero means a team's first-half ATS record "
                           "carries almost no information about its second half."),
    }


def strategy_luck(results):
    out = []
    for r in results:
        v = r.get("validation")
        if not v or not v.get("per_season"):
            continue
        rois = np.array(list(v["per_season"].values()), dtype=float)
        counts = np.array([v["bet_counts_by_season"].get(k, 0) for k in v["per_season"]], dtype=float)
        if len(rois) < 4:
            continue
        obs_sd = float(rois.std(ddof=1))
        # binomial sd of ROI given the number of bets actually placed each season
        exp_sd = float(np.mean(1.0 / np.sqrt(np.maximum(counts, 1))))
        luck_share = min(exp_sd ** 2 / obs_sd ** 2, 1.0) if obs_sd > 0 else 1.0
        out.append({
            "key": r["key"], "name": r["name"], "category": r["category"],
            "validation_roi": v["roi"], "validation_bets": v["bets"],
            "season_roi_sd": MD(obs_sd), "chance_sd": MD(exp_sd),
            "luck_share_of_variance": MD(luck_share),
            "skill_share_of_variance": MD(1 - luck_share),
            "validation_p": v.get("p_value"),
            "reality_check_p": r.get("reality_check_p"),
        })
    out.sort(key=lambda x: -(x["skill_share_of_variance"] or 0))
    return out


def evidence_requirement():
    """Bets required to separate a true edge from noise, one-sided 95% / 80% power."""
    rows = []
    for roi in [0.01, 0.02, 0.03, 0.05, 0.10]:
        # per-bet sd of a -110 bet is ~0.95; required n ~ (z * sd / roi)^2
        sd = 0.9539
        n95 = (1.645 * sd / roi) ** 2
        n80 = (0.84 + 1.645) ** 2 * sd ** 2 / roi ** 2
        rows.append({"true_roi": roi, "bets_95pct_one_sided": int(math.ceil(n95)),
                     "bets_80pct_power": int(math.ceil(n80)),
                     "seasons_at_150_bets": MD(n95 / 150, 1)})
    return rows


def main():
    g = nc.load_games()
    g = g[(g.season >= 2006) & g.spread_line.notna()]

    strat_path = nc.DERIVED / "strategies.json"
    strategies = json.loads(strat_path.read_text())["leaderboard"] if strat_path.exists() else []

    sig_path = nc.DERIVED / "signals.json"
    sig = json.loads(sig_path.read_text()) if sig_path.exists() else {}

    payload = {
        "null_bettors": null_bettors(),
        "skill_variance": skill_variance(g),
        "persistence": persistence(g),
        "strategy_luck": strategy_luck(strategies),
        "evidence_requirement": evidence_requirement(),
        "multiple_testing": {
            "signals_tested": sig.get("n_tests"),
            "expected_false_positives_at_p05": sig.get("expected_false_positives_at_05"),
            "fdr_threshold": sig.get("fdr_threshold"),
            "survivors": sig.get("survivors", []),
            "strategies_tested": len(strategies),
            "best_strategy_reality_check_p": min(
                [s.get("reality_check_p") for s in strategies
                 if s.get("reality_check_p") is not None], default=None),
        },
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: payload[k] for k in ("null_bettors", "skill_variance",
                                              "persistence", "multiple_testing")},
                     indent=1)[:2600])
    print("strategy luck rows", len(payload["strategy_luck"]))


if __name__ == "__main__":
    main()
