#!/usr/bin/env python3
"""Measure real correlations between legs of NFL parlays, and quantify the pricing error that
independent-leg parlay maths makes.

Outputs data/derived/correlation.json
"""
from __future__ import annotations

import json
import os
import traceback

import numpy as np
import pandas as pd
from scipy import stats as sps

from lib import data as D
from lib import stats as S

DERIVED = os.path.join("data", "derived")


def team_game_features(pg: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game: passing, receiving, rushing leaders and scoring context."""
    pg = pg.copy()
    key = ["game_id", "team"]

    qb = pg[pg["attempts"].fillna(0) >= 10].sort_values(key + ["attempts"], ascending=[True, True, False])
    qb = qb.drop_duplicates(subset=key, keep="first")[key + ["player_id", "player_display_name", "attempts", "passing_yards"]]
    qb = qb.rename(columns={"player_id": "qb_id", "player_display_name": "qb_name",
                            "attempts": "qb_attempts", "passing_yards": "qb_pass_yds"})

    skill = pg[pg["position"].isin(["WR", "TE", "RB"])].copy()
    skill["targets"] = skill["targets"].fillna(0)
    wr = skill.sort_values(key + ["targets"], ascending=[True, True, False])
    wr1 = wr.drop_duplicates(subset=key, keep="first")[key + ["player_display_name", "targets",
                                                             "receptions", "receiving_yards"]]
    wr1 = wr1.rename(columns={"player_display_name": "wr1_name", "targets": "wr1_targets",
                              "receptions": "wr1_rec", "receiving_yards": "wr1_yards"})
    wr2 = wr.groupby(key, sort=False).nth(1).reset_index()[
        key + ["player_display_name", "targets", "receiving_yards"]]
    wr2 = wr2.rename(columns={"player_display_name": "wr2_name", "targets": "wr2_targets",
                              "receiving_yards": "wr2_yards"})

    rb = pg[(pg["position"] == "RB")].sort_values(key + ["carries"], ascending=[True, True, False])
    rb1 = rb.drop_duplicates(subset=key, keep="first")[key + ["player_display_name", "carries", "rushing_yards"]]
    rb1 = rb1.rename(columns={"player_display_name": "rb1_name", "carries": "rb1_carries",
                              "rushing_yards": "rb1_yards"})

    base = pg.groupby(key, as_index=False).agg(team_points=("team_points", "first"),
                                               opp_points=("opp_points", "first"),
                                               season=("season", "first"), week=("week", "first"))
    out = base.merge(qb, on=key, how="left").merge(wr1, on=key, how="left") \
              .merge(wr2, on=key, how="left").merge(rb1, on=key, how="left")
    out["diff_points"] = out["team_points"] - out["opp_points"]
    out["game_total"] = out["team_points"] + out["opp_points"]
    return out


def pair(out: dict, key: str, label: str, a: np.ndarray, b: np.ndarray, note: str = "") -> None:
    res = S.corr_pair(a, b)
    out[key] = {"label": label, **res, "note": note}


def joint_ratio(df: pd.DataFrame, cols: list[str]) -> dict:
    """Empirical P(all above own median) vs product of marginals for a set of legs."""
    d = df.dropna(subset=cols).copy()
    if len(d) < 100:
        return {"n": int(len(d)), "status": "insufficient_data"}
    marg, ind = [], []
    exceed = []
    for c in cols:
        med = d[c].median()
        e = (d[c] > med).astype(int)
        exceed.append(e)
        marg.append(float(e.mean()))
    E = np.column_stack(exceed)
    n = len(d)
    joint = float(E.all(axis=1).mean())
    prod = float(np.prod(marg))
    # standard error of the joint rate
    se = float(np.sqrt(joint * (1 - joint) / n))
    return {
        "n": n, "legs": cols, "marginal_rates": [round(m, 4) for m in marg],
        "empirical_joint": round(joint, 4), "independent_product": round(prod, 4),
        "joint_minus_product": round(joint - prod, 4),
        "joint_ci": [round(max(0.0, joint - 1.96 * se), 4), round(min(1.0, joint + 1.96 * se), 4)],
        "fair_odds_empirical": round(1 / joint, 3) if joint > 0 else None,
        "fair_odds_independent": round(1 / prod, 3) if prod > 0 else None,
        "status": "measured",
    }


def copula_joint(rho: np.ndarray, probs: list[float]) -> float:
    """Gaussian-copula joint probability P(all legs win) given a correlation matrix."""
    z = np.array([sps.norm.ppf(p) for p in probs])
    mvn = sps.multivariate_normal(mean=np.zeros(len(probs)), cov=rho, allow_singular=True)
    return float(mvn.cdf(-z))  # P(all X_i > z_i) = P(all -X_i < -z_i)


def main() -> None:
    out: dict = {}
    games, _ = D.load_games()
    player, _ = D.load_player_week()
    pg = D.player_games(player, games)
    tg = team_game_features(pg, games)

    out["scope"] = {
        "seasons": [int(pg["season"].min()), int(pg["season"].max())],
        "team_games": int(len(tg)),
        "player_games": int(len(pg)),
        "definition": ("Pearson correlation between same-game quantities. Legs are counted per "
                       "team-game (two observations per game) so both sides of a game are included."),
    }

    # ------------------------------------------------- game-level correlations
    g = games.dropna(subset=["home_score", "away_score"])
    g = g[g["game_type"] == "REG"]
    pair(out, "home_points_vs_away_points", "Home points vs away points (pace coupling)",
         g["home_score"].to_numpy(float), g["away_score"].to_numpy(float),
         "Positive: fast, high-possession games lift both teams' scoring.")
    pair(out, "margin_vs_total", "Winning margin vs game total",
         g["result"].to_numpy(float), g["total"].to_numpy(float),
         "Blowouts and high totals are mildly linked; weak but non-zero.")

    # ------------------------------------------------- team-game correlations
    pair(out, "qb_yards_vs_team_points", "QB passing yards vs own team points",
         tg["qb_pass_yds"].to_numpy(float), tg["team_points"].to_numpy(float))
    pair(out, "qb_yards_vs_wr1_yards", "QB passing yards vs WR1 receiving yards",
         tg["qb_pass_yds"].to_numpy(float), tg["wr1_yards"].to_numpy(float),
         "The core same-game-parlay pair: same passing volume drives both legs.")
    pair(out, "qb_yards_vs_wr2_yards", "QB passing yards vs WR2 receiving yards",
         tg["qb_pass_yds"].to_numpy(float), tg["wr2_yards"].to_numpy(float))
    pair(out, "wr1_vs_wr2_yards", "WR1 receiving yards vs WR2 receiving yards",
         tg["wr1_yards"].to_numpy(float), tg["wr2_yards"].to_numpy(float),
         "Team-mates compete for the same targets, so this is the one common negative pair.")
    pair(out, "rb_yards_vs_team_points", "RB1 rushing yards vs own team points",
         tg["rb1_yards"].to_numpy(float), tg["team_points"].to_numpy(float))
    pair(out, "rb_yards_vs_qb_yards", "RB1 rushing yards vs QB passing yards",
         tg["rb1_yards"].to_numpy(float), tg["qb_pass_yds"].to_numpy(float),
         "Game script: trailing teams abandon the run.")
    pair(out, "qb_yards_vs_opp_points", "QB passing yards vs opponent points",
         tg["qb_pass_yds"].to_numpy(float), tg["opp_points"].to_numpy(float))
    pair(out, "team_points_vs_opp_points", "Team points vs opponent points",
         tg["team_points"].to_numpy(float), tg["opp_points"].to_numpy(float))
    pair(out, "wr1_yards_vs_team_points", "WR1 receiving yards vs own team points",
         tg["wr1_yards"].to_numpy(float), tg["team_points"].to_numpy(float))

    # opposing passers
    opp = tg[["game_id", "team", "qb_pass_yds"]].copy()
    swap = tg[["game_id", "team", "qb_pass_yds"]].rename(
        columns={"team": "opp_team", "qb_pass_yds": "opp_qb_pass_yds"})
    # opponent_team is carried on player rows; rebuild the opponent link from the schedule
    fix = games[["game_id", "home_team", "away_team"]]
    opp = opp.merge(fix, on="game_id", how="left")
    opp["opp_team"] = np.where(opp["team"] == opp["home_team"], opp["away_team"], opp["home_team"])
    opp = opp.merge(swap, left_on=["game_id", "opp_team"], right_on=["game_id", "opp_team"], how="left")
    pair(out, "qb_yards_vs_opp_qb_yards", "QB passing yards vs opposing QB passing yards",
         opp["qb_pass_yds"].to_numpy(float), opp["opp_qb_pass_yds"].to_numpy(float),
         "Shared game environment: weather, pace and shootout dynamics.")

    # ------------------------------------------------- same-player prop pairs
    wrte = pg[pg["position"].isin(["WR", "TE"]) & (pg["targets"].fillna(0) > 0)]
    pair(out, "receptions_vs_receiving_yards", "Receptions vs receiving yards (same player-game)",
         wrte["receptions"].to_numpy(float), wrte["receiving_yards"].to_numpy(float),
         "Two props on the same player are near-substitutes: do not price them as independent.")
    rb = pg[(pg["position"] == "RB") & (pg["carries"].fillna(0) > 0)]
    pair(out, "carries_vs_rushing_yards", "Carries vs rushing yards (same player-game)",
         rb["carries"].to_numpy(float), rb["rushing_yards"].to_numpy(float))
    qbs = pg[(pg["position"] == "QB") & (pg["attempts"].fillna(0) >= 10)]
    pair(out, "pass_yards_vs_pass_tds", "Passing yards vs passing TDs (same QB-game)",
         qbs["passing_yards"].to_numpy(float), qbs["passing_tds"].to_numpy(float))

    # ------------------------------------------------- parlay pricing: 4-leg same-team SGP
    legs = ["qb_pass_yds", "wr1_yards", "rb1_yards", "team_points"]
    d4 = tg.dropna(subset=legs)
    out["sgp_4leg_same_team"] = joint_ratio(tg, legs)
    probs = [0.5, 0.5, 0.5, 0.5]
    rho = np.corrcoef(d4[legs].to_numpy(float).T) if len(d4) > 100 else None
    if rho is not None:
        out["sgp_4leg_same_team"]["correlation_matrix"] = {
            "legs": legs, "matrix": [[round(float(v), 3) for v in row] for row in rho]
        }
        cop = copula_joint(rho, probs)
        out["sgp_4leg_same_team"]["copula_joint"] = round(cop, 4)
        out["sgp_4leg_same_team"]["copula_fair_odds"] = round(1 / cop, 3) if cop > 0 else None
        ind = float(np.prod(probs))
        out["sgp_4leg_same_team"]["pricing_error_pct"] = round(100 * (cop / ind - 1), 1)

    # 2-leg and 3-leg versions for the payout table
    variants = {
        "2leg_qb_wr1": ["qb_pass_yds", "wr1_yards"],
        "3leg_qb_wr1_teampoints": ["qb_pass_yds", "wr1_yards", "team_points"],
        "2leg_qb_wr1_opposing": None,
    }
    out["sgp_variants"] = {}
    for name, cols in variants.items():
        if cols is None:
            continue
        out["sgp_variants"][name] = joint_ratio(tg, cols)

    # cross-game (independent) control: QB yards in game A vs QB yards in game B
    rng = np.random.default_rng(20261101)
    a = d4["qb_pass_yds"].to_numpy(float)
    b = np.roll(a, 137)[rng.permutation(len(a))]
    out["cross_game_control"] = S.corr_pair(a, b)
    out["cross_game_control"]["label"] = ("Placebo: QB yards in unrelated team-games. Should be ~0, "
                                          "which validates the measurement method.")

    # ------------------------------------------------- what this means for pricing
    if "sgp_4leg_same_team" in out and out["sgp_4leg_same_team"].get("copula_joint"):
        j = out["sgp_4leg_same_team"]
        out["pricing_notes"] = {
            "independent_fair_odds": j.get("fair_odds_independent"),
            "correlation_aware_fair_odds": j.get("copula_fair_odds"),
            "message": ("Correlated legs that all lean the same way make the true joint probability "
                        "materially HIGHER than the product when the legs share a driver, so a book "
                        "pricing legs independently overprices the parlay in the bettor's favour - and "
                        "that is exactly why books cap or reprice same-game parlays."),
        }

    with open(os.path.join(DERIVED, "correlation.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    for k, v in out.items():
        if isinstance(v, dict) and v.get("status") == "measured" and "r" in v:
            print(f"{k:34s} r={v['r']:+.3f} n={v['n']:6d} CI[{v['ci_low']:+.3f},{v['ci_high']:+.3f}]")
    print(json.dumps(out.get("sgp_4leg_same_team", {}), indent=2, default=str)[:1500])


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "correlation.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        raise SystemExit(1)
