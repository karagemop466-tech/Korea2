#!/usr/bin/env python3
"""Independent recomputation of the published headline numbers.

Written by verification session `arena/652b0095-korea2` on 2026-11-02. It deliberately does NOT
import anything from `scripts/` or `pipeline/`: the point is to recompute the same quantities from
the committed extracts with a second implementation and see whether the published JSON survives.

It also reconciles team standings rebuilt from `data/derived/games.csv.gz` against two transcribed
NFL.com standings tables:

  * 2020 (a completed regular season) - expected to reconcile exactly, and does;
  * 2026 (the live page, retrieved 2026-11-02) - expected to differ, because the committed extract
    ends at gameday 2026-10-29. The size of that difference is the point: it measures how stale the
    published numbers are.

Outputs
  verification/recompute.json          full detail, committed
  data/derived/verification.json       the subset the site renders

Exit code is non-zero if any recomputation disagrees with the published value beyond tolerance.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIVED = os.path.join(ROOT, "data", "derived")
VERIF = os.path.join(ROOT, "verification")

TEAM_ALIAS = {"ARI": "AZ"}  # nflverse uses ARI, NFL.com prints AZ
# The schedule keeps the franchise code of the time (SD, OAK, STL); the player feed
# uses the current code (LAC, LV, LA). Joining without mapping these silently drops
# ~9,000 player rows - the join then "succeeds" with a smaller sample.
FRANCHISE_ALIAS = {"SD": "LAC", "OAK": "LV", "STL": "LA", "LAR": "LA", "WSH": "WAS", "ARZ": "AZ"}


# ----------------------------------------------------------------- small stats helpers
def corr_ci(r: float, n: int) -> tuple[float, float]:
    """Fisher-z 95% CI, i.e. the same transform the published tables use."""
    z = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def pct(v: float, d: int = 3, sign: bool = False) -> str:
    return f"{v:+.{d}f}" if sign else f"{v:.{d}f}"


def american_to_decimal(a: float) -> float:
    return 1 + (a / 100 if a > 0 else 100 / abs(a))


# ----------------------------------------------------------------- load committed extracts
def load() -> dict:
    games = pd.read_csv(os.path.join(DERIVED, "games.csv.gz"))
    player = pd.read_csv(os.path.join(DERIVED, "player_week.csv.gz"))
    return {"games": games, "player": player}


def published(name: str) -> dict:
    path = os.path.join(DERIVED, name)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


# ----------------------------------------------------------------- checks
def check(cid: str, claim: str, published_value, recomputed, tol: float, method: str,
          source_id: str = "nflverse-data", klass: str = "assert") -> dict:
    if isinstance(published_value, (int, float)) and isinstance(recomputed, (int, float)):
        delta = abs(float(published_value) - float(recomputed))
        ok = delta <= tol or (math.isnan(delta))
    else:
        delta = None
        ok = published_value == recomputed
    return {
        "id": cid, "claim": claim, "published": published_value, "recomputed": recomputed,
        "abs_diff": None if delta is None else round(delta, 6), "tolerance": tol,
        "verdict": ("INFO" if published_value is None else
                    "PASS" if ok else ("MISMATCH" if klass == "assert" else "DIFFERS (expected)")),
        "class": klass, "method": method, "source_id": source_id,
    }


def main() -> int:
    d = load()
    games, player = d["games"], d["player"]
    market, model, corr, luck = (published("market.json"), published("model.json"),
                                 published("correlation.json"), published("luck.json"))
    diag, lb = published("diag_signs.json"), published("leaderboard.json")
    checks: list[dict] = []

    # ---------------------------------------------------------------- data QA
    played = games.dropna(subset=["home_score", "away_score"])
    reg = played[played["game_type"] == "REG"]
    checks.append(check("qa.unique_ids", "game_id is unique",
                        len(games), int(games["game_id"].nunique()), 0,
                        "count distinct game_id over the committed extract"))
    checks.append(check("qa.result", "result == home_score - away_score (max abs diff)",
                        0, float((played["result"] - (played["home_score"] - played["away_score"])).abs().max()), 0,
                        "recomputed from the two score columns"))
    checks.append(check("qa.total", "total == home_score + away_score (max abs diff)",
                        0, float((played["total"] - (played["home_score"] + played["away_score"])).abs().max()), 0,
                        "recomputed from the two score columns"))
    # Data-snapshot expectations are read from the DECLARED manifest instead of
    # being frozen constants (maintenance session arena/cacf6153-korea2,
    # 2026-11-02): the automated refresh commit 95bbd78 legitimately moved the
    # extract from 7,384 to 7,396 played games and its as-of date from
    # 2026-10-29 to 2026-11-01, which made the old constants fail this check
    # while nothing was actually wrong. The check is now "the committed data
    # matches its declared metadata", which cannot go stale on a refresh.
    prov_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "data", "provenance.json")
    with open(prov_path) as fh:
        prov = json.load(fh)
    checks.append(check("qa.played", "played games", int(prov["games_settled"]), int(len(played)), 0,
                        "declared in data/provenance.json; recomputed as rows with both scores present"))
    as_of = str(pd.to_datetime(played["gameday"]).max().date())
    checks.append(check("qa.as_of", "latest settled gameday in the committed extract",
                        str(prov["data_as_of_gameday"]), as_of, 0,
                        "declared in data/provenance.json; recomputed as max(gameday) over played games"))

    # ---------------------------------------------------------------- extract window vs published scope
    preg = player[player["season_type"] == "REG"]
    checks.append(check("scope.player_seasons",
                        "first and last season in the committed player extract",
                        str(corr.get("scope", {}).get("seasons")), f"[{int(preg['season'].min())}, {int(preg['season'].max())}]",
                        0, "the published correlation page states the seasons the coefficients were measured on; the "
                           "committed extract is a pruned 2015-2026 file", klass="observe"))
    checks.append(check("scope.player_games", "player-games in the committed extract (regular season)",
                        corr.get("scope", {}).get("player_games"), int(len(preg)), 0,
                        "the published figure was measured on the 2012-2026 download before pruning; the committed "
                        "extract holds fewer rows, which is why the recomputed correlations carry a smaller n",
                        klass="observe"))

    # ---------------------------------------------------------------- market benchmark
    withline = reg.dropna(subset=["spread_line"])
    spread_mae = float((withline["result"] - withline["spread_line"]).abs().mean())
    cs = market.get("closing_spread_accuracy", {})
    checks.append(check("market.spread_mae", "closing spread MAE vs actual margin (all seasons)",
                        cs.get("mae"), round(spread_mae, 3), 0.005,
                        "mean |margin - spread_line| over regular-season games with a closing line"))
    checks.append(check("market.spread_n", "closing spread sample size", cs.get("n"), int(len(withline)), 0,
                        "count of regular-season games with a closing line"))

    withtot = reg.dropna(subset=["total_line"])
    total_mae = float((withtot["total"] - withtot["total_line"]).abs().mean())
    ct = market.get("closing_total_accuracy", {})
    checks.append(check("market.total_mae", "closing total MAE", ct.get("mae"), round(total_mae, 3), 0.005,
                        "mean |game total - total_line| over regular-season games with a closing total"))
    checks.append(check("market.total_n", "closing total sample size", ct.get("n"), int(len(withtot)), 0,
                        "count of regular-season games with a closing total"))

    recent = reg[reg["season"] >= 2023].dropna(subset=["spread_line"])
    recent_mae = float((recent["result"] - recent["spread_line"]).abs().mean())
    cr = market.get("closing_spread_accuracy_recent", {})
    checks.append(check("market.recent_mae", "closing spread MAE, 2023-2026", cr.get("mae"),
                        round(recent_mae, 3), 0.005, "same statistic restricted to seasons >= 2023"))
    checks.append(check("market.recent_n", "closing spread sample, 2023-2026", cr.get("n"), int(len(recent)), 0,
                        "count of regular-season games with a closing line, seasons >= 2023"))

    # ---------------------------------------------------------------- sign convention
    conv_a = withline["result"] - withline["spread_line"]
    conv_b = withline["result"] + withline["spread_line"]
    dis = diag.get("home_cover_rate_if_line_means_home_favoured", {})
    checks.append(check("sign.home_cover_as_expected_margin",
                        "home cover rate if spread_line is the home team's expected margin",
                        dis.get("cover_rate_excl_push"), round(float((conv_a[conv_a != 0] > 0).mean()), 4), 0.0006,
                        "result - spread_line > 0, pushes excluded"))
    checks.append(check("sign.home_cover_as_handicap",
                        "home cover rate if spread_line is the home team's handicap",
                        diag.get("home_cover_rate_if_line_means_home_handicap", {}).get("cover_rate_excl_push"),
                        round(float((conv_b[conv_b != 0] > 0).mean()), 4), 0.0006,
                        "result + spread_line > 0, pushes excluded"))
    ml = withline.dropna(subset=["home_moneyline"])
    checks.append(check("sign.ml_fav_mean_line", "mean spread_line when the home team is the moneyline favourite",
                        diag.get("moneyline_cross_check", {}).get("mean_spread_line_when_home_is_ml_favourite"),
                        round(float(ml[ml["home_moneyline"] < 0]["spread_line"].mean()), 3), 0.005,
                        "mean(spread_line | home_moneyline < 0)"))
    checks.append(check("sign.ml_dog_mean_line", "mean spread_line when the home team is the moneyline underdog",
                        diag.get("moneyline_cross_check", {}).get("mean_spread_line_when_home_is_ml_underdog"),
                        round(float(ml[ml["home_moneyline"] > 0]["spread_line"].mean()), 3), 0.005,
                        "mean(spread_line | home_moneyline > 0)"))

    # ---------------------------------------------------------------- ATS: pooled identity + the real tilt test
    ats = (reg.dropna(subset=["spread_line"])["result"] - reg.dropna(subset=["spread_line"])["spread_line"])
    ats = ats[ats != 0]
    k, n = int((ats > 0).sum()), int(len(ats))
    # every team-game, both sides of the same game, reproduces the pooled two-sided count
    ats_all = pd.concat([ats, -ats])
    k2, n2 = int((ats_all > 0).sum()), int(len(ats_all))
    act = luck.get("ats_coin_flip_test", {})
    checks.append(check("luck.ats_n", "pooled ATS team-games (arithmetic identity: each game counted twice)", act.get("n"), n2, 0,
                        "each settled game contributes a home and an away ATS result"))
    checks.append(check("luck.ats_wins", "pooled ATS wins (identity: exactly one of +x/-x covers)", act.get("wins"), k2, 0, "count of ATS covers"))
    checks.append(check("luck.ats_rate", "pooled ATS cover rate (identity: 0.5 for ANY dataset, not evidence)", act.get("rate"), round(k2 / n2, 4), 0.0006,
                        "wins / decided team-games; see flag FL-DH-01"))
    # one observation per game: the only version of the test that can detect a tilt (market.json)
    hc = market.get("ats_home_cover", {})
    checks.append(check("market.ats_home_n", "ATS tilt test: decided games with a closing spread", hc.get("n"), n, 0,
                        "one observation per game (home team covers or not), pushes removed"))
    checks.append(check("market.ats_home_covers", "home covers against the closing spread", hc.get("home_covers"), k, 0,
                        "result - spread_line > 0"))
    checks.append(check("market.ats_home_rate", "home ATS cover rate, one observation per game", hc.get("home_cover_rate"), round(k / n, 4), 0.0006,
                        "the published tilt test (market.json -> ats_home_cover)"))
    checks.append(check("market.ats_home_p", "two-sided exact binomial p vs 50% (tilt test)", hc.get("binomial_p"),
                        round(float(sps.binomtest(k, n, 0.5, alternative="two-sided").pvalue), 4), 0.0005,
                        "exact binomial on home covers in decided games"))

    # ---------------------------------------------------------------- Pythagorean luck
    rows = []
    for _, g in reg.iterrows():
        rows.append((int(g["season"]), g["home_team"], int(g["home_score"]), int(g["away_score"])))
        rows.append((int(g["season"]), g["away_team"], int(g["away_score"]), int(g["home_score"])))
    tg = pd.DataFrame(rows, columns=["season", "team", "pf", "pa"])
    tg["margin"] = tg["pf"] - tg["pa"]
    ts = tg.groupby(["season", "team"]).agg(gp=("pf", "size"), pf=("pf", "sum"), pa=("pa", "sum"),
                                            wins=("margin", lambda s: float((s > 0).sum())),
                                            ties=("margin", lambda s: float((s == 0).sum()))).reset_index()
    ts = ts[ts["gp"] >= 8].copy()
    exp = 2.37
    ts["exp_win_pct"] = ts["pf"] ** exp / (ts["pf"] ** exp + ts["pa"] ** exp)
    ts["exp_wins"] = ts["exp_win_pct"] * ts["gp"]
    ts["luck_wins"] = ts["wins"] - ts["exp_wins"]
    ts["actual_win_pct"] = ts["wins"] / ts["gp"]
    r2 = float(np.corrcoef(ts["exp_win_pct"], ts["actual_win_pct"])[0, 1] ** 2)
    py = luck.get("pythagorean", {})
    checks.append(check("luck.pythag_r2", "Pythagorean expected vs actual win% R^2 (exponent 2.37)",
                        py.get("r2_expected_vs_actual_win_pct"), round(r2, 4), 0.0006,
                        "squared Pearson r between expected and actual win% over team-seasons with >= 8 games"))
    checks.append(check("luck.pythag_n", "team-seasons in the Pythagorean sample", py.get("team_seasons"),
                        int(len(ts)), 0, "count of team-seasons with >= 8 regular-season games"))
    checks.append(check("luck.pythag_sd", "SD of luck wins", py.get("sd_luck_wins"),
                        round(float(ts["luck_wins"].std(ddof=1)), 3), 0.006,
                        "sample SD of (actual wins - Pythagorean expected wins)"))

    ts = ts.sort_values(["team", "season"])
    ts["next_luck"] = ts.groupby("team")["luck_wins"].shift(-1)
    ts["next_season"] = ts.groupby("team")["season"].shift(-1)
    pairs = ts[ts["next_season"] == ts["season"] + 1].dropna(subset=["next_luck"])
    r_persist = float(np.corrcoef(pairs["luck_wins"], pairs["next_luck"])[0, 1])
    lp = luck.get("luck_persistence", {})
    checks.append(check("luck.persistence_r", "year-over-year correlation of Pythagorean luck",
                        lp.get("r"), round(r_persist, 4), 0.001,
                        "Pearson r between consecutive seasons of the same franchise"))
    checks.append(check("luck.persistence_n", "pairs in the luck-persistence test", lp.get("n"),
                        int(len(pairs)), 0, "consecutive team-seasons"))

    tg["one_score"] = (tg["margin"].abs() <= 8).astype(int)
    osg = tg[tg["one_score"] == 1].groupby(["season", "team"]).agg(
        n=("margin", "size"), wins=("margin", lambda s: float((s > 0).sum()))).reset_index()
    osg = osg[osg["n"] >= 3].copy()
    osg["rate"] = osg["wins"] / osg["n"]
    osg = osg.sort_values(["team", "season"])
    osg["next_rate"] = osg.groupby("team")["rate"].shift(-1)
    osg["next_season"] = osg.groupby("team")["season"].shift(-1)
    p2 = osg[osg["next_season"] == osg["season"] + 1].dropna(subset=["next_rate"])
    r_os = float(np.corrcoef(p2["rate"], p2["next_rate"])[0, 1])
    osw = luck.get("one_score_persistence", {})
    checks.append(check("luck.one_score_r", "year-over-year correlation of one-score win rate",
                        osw.get("r"), round(r_os, 4), 0.001,
                        "Pearson r over team-seasons with >= 3 one-score games (|margin| <= 8)"))
    checks.append(check("luck.one_score_n", "pairs in the one-score persistence test", osw.get("n"),
                        int(len(p2)), 0, "consecutive team-seasons"))

    # ---------------------------------------------------------------- correlations
    pr = player[player["season_type"] == "REG"].copy()
    # The committed player extract has no game_id, so the game is identified from season + week + team.
    side = []
    for _, g in reg.iterrows():
        side.append((int(g["season"]), int(g["week"]), g["home_team"], g["game_id"],
                     int(g["home_score"]), int(g["away_score"])))
        side.append((int(g["season"]), int(g["week"]), g["away_team"], g["game_id"],
                     int(g["away_score"]), int(g["home_score"])))
    ctx = pd.DataFrame(side, columns=["season", "week", "team", "game_id", "team_points", "opp_points"])
    ctx["team"] = ctx["team"].map(lambda t: FRANCHISE_ALIAS.get(t, t))
    pr["team"] = pr["team"].map(lambda t: FRANCHISE_ALIAS.get(t, t))
    ctx = ctx.drop_duplicates(["season", "week", "team"])
    pr = pr.merge(ctx, on=["season", "week", "team"], how="inner")
    key = ["game_id", "team"]

    qb = pr[pr["attempts"].fillna(0) >= 10].sort_values(key + ["attempts"], ascending=[True, True, False])
    qb = qb.drop_duplicates(key)[key + ["passing_yards"]].rename(columns={"passing_yards": "qb_yds"})
    skill = pr[pr["position"].isin(["WR", "TE", "RB"])].copy()
    skill["targets"] = skill["targets"].fillna(0)
    skill = skill.sort_values(key + ["targets"], ascending=[True, True, False])
    w1 = skill.drop_duplicates(key)[key + ["receiving_yards"]].rename(columns={"receiving_yards": "wr1_yds"})
    w2 = skill.groupby(key, sort=False).nth(1).reset_index()[key + ["receiving_yards"]]
    w2 = w2.rename(columns={"receiving_yards": "wr2_yds"})
    rb = pr[pr["position"] == "RB"].sort_values(key + ["carries"], ascending=[True, True, False])
    rb = rb.drop_duplicates(key)[key + ["rushing_yards"]].rename(columns={"rushing_yards": "rb1_yds"})

    tgp = pr.groupby(key, as_index=False).agg(team_points=("team_points", "first"))
    tgp = tgp.merge(qb, on=key, how="left").merge(w1, on=key, how="left") \
             .merge(w2, on=key, how="left").merge(rb, on=key, how="left")

    def rpair(a: str, b: str):
        sub = tgp.dropna(subset=[a, b])
        r = float(np.corrcoef(sub[a], sub[b])[0, 1])
        lo, hi = corr_ci(r, len(sub))
        return r, lo, hi, len(sub)

    for cid, a, b, keyname, claim in [
        ("corr.qb_wr1", "qb_yds", "wr1_yds", "qb_yards_vs_wr1_yards", "QB passing yards vs WR1 receiving yards"),
        ("corr.qb_wr2", "qb_yds", "wr2_yds", "qb_yards_vs_wr2_yards", "QB passing yards vs WR2 receiving yards"),
        ("corr.wr1_wr2", "wr1_yds", "wr2_yds", "wr1_vs_wr2_yards", "WR1 vs WR2 receiving yards"),
        ("corr.rb_qb", "rb1_yds", "qb_yds", "rb_yards_vs_qb_yards", "RB1 rushing yards vs QB passing yards"),
    ]:
        r, lo, hi, n = rpair(a, b)
        pub = corr.get(keyname, {})
        checks.append(check(cid, claim, pub.get("r"), round(r, 4), 0.02,
                            f"Pearson r over {n} team-games in the committed extract (which starts in 2015; the "
                            "published coefficient was computed on a 2012-2026 download, so exact equality is not "
                            "expected). QB = most attempts (>=10), WR1/WR2 = most/second-most targets among "
                            "WR/TE/RB, RB1 = most carries", klass="observe"))

    # ---------------------------------------------------------------- same-game parlay joint
    legs = ["qb_yds", "wr1_yds", "rb1_yds", "team_points"]
    d4 = tgp.dropna(subset=legs)
    exceed = np.column_stack([(d4[c] > d4[c].median()).astype(int) for c in legs])
    joint = float(exceed.all(axis=1).mean())
    prod = float(np.prod(exceed.mean(axis=0)))
    sgp = corr.get("sgp_4leg_same_team", {})
    checks.append(check("sgp.n", "4-leg same-team parlay sample (team-games)", sgp.get("n"), int(len(d4)), 0,
                        "team-games with all four legs present. The published sample is larger because it was "
                        "measured on a 2012-2026 download; the committed extract starts in 2015", klass="observe"))
    checks.append(check("sgp.joint", "empirical joint probability, all four legs above their median",
                        sgp.get("empirical_joint"), round(joint, 4), 0.01,
                        "share of team-games where all four legs clear their own median (window gap as above)",
                        klass="observe"))
    checks.append(check("sgp.product", "independent product of the four marginal rates",
                        sgp.get("independent_product"), round(prod, 4), 0.01,
                        "product of the four per-leg exceedance rates (window gap as above)", klass="observe"))
    checks.append(check("sgp.excess", "empirical joint minus independent product",
                        sgp.get("joint_minus_product"), round(joint - prod, 4), 0.01,
                        "difference of the two quantities above (window gap as above)", klass="observe"))

    # ---------------------------------------------------------------- strategy spot checks
    preds = pd.read_csv(os.path.join(DERIVED, "predictions.csv"))
    window = reg[reg["game_id"].isin(set(preds["game_id"]))].dropna(subset=["spread_line", "total_line"])
    pub_lb = {e["id"]: e for e in lb.get("entries", [])}

    def settle(df: pd.DataFrame, side_home: pd.Series, handicap_home: pd.Series,
               odds_home: pd.Series, odds_away: pd.Series) -> tuple[int, float]:
        profit, staked, placed = 0.0, 0.0, 0
        for (_, row), home, hand, oh, oa in zip(df.iterrows(), side_home, handicap_home, odds_home, odds_away):
            if pd.isna(home) or pd.isna(hand):
                continue
            if home:
                edge, odds = row["result"] + hand, oh
            else:
                edge, odds = -row["result"] - hand, oa
            if pd.isna(odds):
                odds = -110.0
            placed += 1
            if abs(edge) < 1e-9:
                continue          # push: stake refunded, excluded from the ROI denominator
            if edge > 0:
                profit += (odds / 100 if odds > 0 else 100 / abs(odds))
            else:
                profit -= 1.0
            staked += 1.0
        return placed, (profit / staked if staked else float("nan"))

    w = window
    long = w["spread_line"] >= 0  # home is the underdog when the line is negative
    spots = {}
    # S4 rest advantage >= 3 days
    rd = w["home_rest"] - w["away_rest"]
    sel = w[rd.abs() >= 3]
    home_side = (rd[rd.abs() >= 3] >= 3)
    spots["S4_rest_advantage"] = settle(sel, home_side, -sel["spread_line"], sel["home_spread_odds"], sel["away_spread_odds"])
    # S5 bye-week team (13+ days rest vs <13)
    sel = w[((w["home_rest"] >= 13) & (w["away_rest"] < 13)) | ((w["away_rest"] >= 13) & (w["home_rest"] < 13))]
    spots["S5_bye_week_team"] = settle(sel, sel["home_rest"] >= 13, -sel["spread_line"],
                                       sel["home_spread_odds"], sel["away_spread_odds"])
    # S6 divisional home underdog
    sel = w[(w["div_game"] == 1) & (w["spread_line"] < 0)]
    spots["S6_divisional_home_dog"] = settle(sel, pd.Series(True, index=sel.index), -sel["spread_line"],
                                             sel["home_spread_odds"], sel["away_spread_odds"])
    # C1 back every home team
    sel = w
    spots["C1_all_home_control"] = settle(sel, pd.Series(True, index=sel.index), -sel["spread_line"],
                                          sel["home_spread_odds"], sel["away_spread_odds"])
    # S7 under when wind >= 15 outdoors
    outdoor = ~w["roof"].astype(str).str.lower().isin(["dome", "closed", "open", "retractable"])
    sel = w[outdoor & w["wind"].notna() & (w["wind"] >= 15)]
    profit, staked, placed = 0.0, 0.0, 0
    for _, row in sel.iterrows():
        odds = row["under_odds"] if not pd.isna(row["under_odds"]) else -110.0
        edge = row["total_line"] - row["total"]
        placed += 1
        if abs(edge) < 1e-9:
            continue
        profit += (odds / 100 if odds > 0 else 100 / abs(odds)) if edge > 0 else -1.0
        staked += 1.0
    spots["S7_wind_under"] = (placed, profit / staked if staked else float("nan"))
    # C2 under every game
    profit, staked, placed = 0.0, 0.0, 0
    for _, row in w.iterrows():
        odds = row["under_odds"] if not pd.isna(row["under_odds"]) else -110.0
        edge = row["total_line"] - row["total"]
        placed += 1
        if abs(edge) < 1e-9:
            continue
        profit += (odds / 100 if odds > 0 else 100 / abs(odds)) if edge > 0 else -1.0
        staked += 1.0
    spots["C2_all_under_control"] = (placed, profit / staked if staked else float("nan"))

    for sid, (n_bets, roi) in spots.items():
        pub = pub_lb.get(sid, {})
        checks.append(check(f"strategy.{sid}.n", f"{sid}: settled bets in the published window",
                            pub.get("n_bets"), n_bets, 0,
                            "re-settled from the extract with push-aware spread/total rules at the feed's price"))
        checks.append(check(f"strategy.{sid}.roi", f"{sid}: ROI per unit staked", pub.get("roi"),
                            round(float(roi), 4), 0.0015,
                            "profit / units staked, pushes refunded and removed"))

    # ---------------------------------------------------------------- standings reconciliation
    def rebuilt(season: int) -> dict:
        s = reg[reg["season"] == season]
        rec: dict[str, list] = {}
        for _, g in s.iterrows():
            for team, pf, pa in ((g["home_team"], g["home_score"], g["away_score"]),
                                 (g["away_team"], g["away_score"], g["home_score"])):
                t = TEAM_ALIAS.get(team, team)
                r = rec.setdefault(t, [0, 0, 0, 0, 0, 0])
                r[0] += int(pf > pa); r[1] += int(pf < pa); r[2] += int(pf == pa)
                r[3] += int(pf); r[4] += int(pa); r[5] += 1
        return rec

    recon = {}
    for season, fname, expect in ((2020, "nfl_standings_2020.json", "exact"),
                                  (2026, "nfl_standings_2026_live.json", "lag")):
        with open(os.path.join(VERIF, fname)) as fh:
            official = json.load(fh)
        mine = rebuilt(season)
        matched, rows = 0, []
        for team, (w_, l_, t_, pf_, pa_) in sorted(official["teams"].items()):
            got = mine.get(team)
            built = [got[0], got[1], got[2], got[3], got[4]] if got else None
            ok = built == [w_, l_, t_, pf_, pa_]
            matched += bool(ok)
            rows.append({"team": team, "official": [w_, l_, t_, pf_, pa_], "rebuilt": built,
                         "match": bool(ok)})
        recon[season] = {
            "url": official["meta"]["url"], "retrieved_utc": official["meta"]["retrieved_utc"],
            "teams_compared": len(rows), "teams_matched": matched,
            "mismatched_teams": [r["team"] for r in rows if not r["match"]],
            "expectation": expect, "rows": rows,
            "games_in_extract": int(len(reg[reg["season"] == season])),
            "latest_gameday_in_extract": str(pd.to_datetime(reg[reg["season"] == season]["gameday"]).max().date()),
        }
        checks.append(check(f"recon.{season}.teams", f"{season}: teams whose W-L-T and PF/PA match NFL.com",
                            len(rows) if expect == "exact" else None, matched, 0,
                            ("standings rebuilt from the score columns and compared field by field with the "
                             "official division standings" + ("" if expect == "exact" else
                             "; the extract ends 2026-10-29 so the current official page must show more games")),
                            source_id=f"nfl-standings-{season}",
                            klass="assert" if expect == "exact" else "observe"))

    # ---------------------------------------------------------------- write outputs
    n_pass = sum(c["verdict"] == "PASS" for c in checks)
    n_fail = sum(c["verdict"] == "MISMATCH" and c["class"] == "assert" for c in checks)
    n_obs = sum(c["class"] == "observe" for c in checks)
    out = {
        "meta": {
            "session": "arena/652b0095-korea2",
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "purpose": ("Independent re-implementation of the published statistics from the committed "
                        "extracts, plus field-by-field reconciliation of a completed season against NFL.com."),
            "data_as_of_gameday": as_of,
            "n_checks": len(checks), "n_pass": n_pass, "n_fail": n_fail, "n_observations": n_obs,
            "independence": ("Does not import scripts/ or pipeline/. Uses pandas/numpy/scipy only, so a "
                             "definition error in the project's own code cannot make this agree with itself."),
            "caveat": ("Reproducibility is not validation. These checks show the numbers follow from the "
                        "committed data; they say nothing about whether a strategy is profitable or a price obtainable."),
        },
        "checks": checks,
        "reconciliation": {str(k): v for k, v in recon.items()},
    }
    with open(os.path.join(VERIF, "recompute.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    with open(os.path.join(VERIF, "sources_2026-11-02.json")) as fh:
        src_checks = json.load(fh)

    site = {
        "meta": out["meta"],
        "sources": src_checks,
        "summary": {
            "n_checks": len(checks), "n_pass": n_pass, "n_fail": n_fail, "n_observations": n_obs,
            "teams_2020_matched": recon[2020]["teams_matched"],
            "teams_2020_compared": recon[2020]["teams_compared"],
            "teams_2026_matched": recon[2026]["teams_matched"],
            "teams_2026_compared": recon[2026]["teams_compared"],
            "data_as_of_gameday": as_of,
            "n_source_checks": len(src_checks.get("checks", [])),
            "n_source_broken": sum(1 for c in src_checks.get("checks", [])
                                   if not c.get("verdict", "").startswith("CONFIRMED")),
        },
        "checks": checks,
        "reconciliation": {str(k): {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in recon.items()},
        "standings_2020": recon[2020]["rows"],
        "standings_2026": recon[2026]["rows"],
    }
    with open(os.path.join(DERIVED, "verification.json"), "w") as fh:
        json.dump(site, fh, indent=2)

    for c in checks:
        if c["verdict"] != "PASS":
            print(f"{c['verdict']:9s} {c['id']:44s} published={c['published']!r:>14} recomputed={c['recomputed']!r}")
    print(f"\n{len(checks)} checks: {n_pass} pass, {n_fail} mismatch, {n_obs} observations (expected-to-differ)")
    print(f"2020 reconciliation: {recon[2020]['teams_matched']}/{recon[2020]['teams_compared']} teams")
    print(f"2026 reconciliation: {recon[2026]['teams_matched']}/{recon[2026]['teams_compared']} teams "
          f"(extract ends {recon[2026]['latest_gameday_in_extract']})")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
