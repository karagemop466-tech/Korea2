#!/usr/bin/env python3
"""DA-8/DA-10-adjacent: correlations, prop combos and parlay pricing.

THE RULE THIS FILE ENFORCES
---------------------------
Correlations are computed from BOX SCORES ONLY — the per-player, per-week stat lines in the
nflverse player-week feed, which redistribute the NFL's own Game Statistics & Information System
credits (SRC-NFL-GSIS). No market price, no line, no closing number, and no model output enters
any coefficient. That is what makes an "officially sourced" correlation possible at all; a
correlation computed against a book's line would be a correlation with the book.

Every coefficient is published with n and a Fisher-z 95% interval, and the joint rate that a
parlay would need is published next to the independent product so the parlay premium is visible.

WHAT THIS FILE DOES NOT DO
--------------------------
There are no historical player-prop PRICES in any committed feed. So prop combos cannot be
priced, ROI cannot be computed for them, and DA-S10/DA-S11 are published as EXECUTION_BLOCKED
rather than as tested strategies. The measured joint rates are exactly what a pricing model
would need once a price feed exists.
"""
from __future__ import annotations

import csv
import gzip
import math
import os
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402

ROOT = A.ROOT
REPO = os.path.dirname(ROOT)
PLAYER_WEEK = os.path.join(REPO, "data", "derived", "player_week.csv.gz")
SRC_STATS = "SRC-NFLVERSE-STATS"
SRC_GSIS = "SRC-NFL-GSIS"


def rows(path):
    with gzip.open(path, "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def f(v):
    try:
        return float(v) if v not in ("", None) else 0.0
    except ValueError:
        return 0.0


def coef(pairs, label, note=""):
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    r, n = A.pearson(xs, ys)
    if n < 3 or math.isnan(r):
        return {"label": label, "n": n, "r": None, "ci": None, "p": None, "note": note}
    lo, hi = A.fisher_ci(r, n)
    return {
        "label": label, "n": n,
        "r": round(r, 4), "ci": [round(lo, 4), round(hi, 4)],
        "p": A.corr_p(r, n), "r2": round(r * r, 4),
        "ci_excludes_zero": (lo > 0 or hi < 0),
        "note": note,
    }


def main():
    pw = rows(PLAYER_WEEK)
    print(f"player-week rows: {len(pw)}")

    # ---------------------------------------------------- team-game and player-game frames
    team_game = {}
    for r in pw:
        key = (r["season"], r["week"], r["team"])
        d = team_game.setdefault(key, {"pass_yds": 0.0, "rush_yds": 0.0, "rec_yds": 0.0,
                                       "players": {}})
        d["pass_yds"] += f(r["passing_yards"])
        d["rush_yds"] += f(r["rushing_yards"])
        d["rec_yds"] += f(r["receiving_yards"])
        d["players"][r["player_id"]] = {
            "name": r["player_display_name"], "pos": r["position"],
            "rec_yds": f(r["receiving_yards"]), "receptions": f(r["receptions"]),
            "targets": f(r["targets"]), "target_share": f(r["target_share"]),
            "rush_yds": f(r["rushing_yards"]), "pass_yds": f(r["passing_yards"]),
        }

    # QB of a team-game = the player with the most passing attempts that week
    qb_of = {}
    for r in pw:
        if r["position"] == "QB" and f(r["attempts"]) > 0:
            key = (r["season"], r["week"], r["team"])
            cur = qb_of.get(key)
            if cur is None or f(r["attempts"]) > cur[1]:
                qb_of[key] = (r["player_id"], f(r["attempts"]))

    # team points: sum of passing + rushing TDs * 6 plus a field goal proxy is NOT derivable from
    # the box score we have, so team points are read from the games feed instead and joined by
    # team-week. That join is stated in the output, and the games feed is third-party.
    games = {}
    with gzip.open(os.path.join(REPO, "data", "derived", "games.csv.gz"), "rt", newline="") as fh:
        for g in csv.DictReader(fh):
            if g["game_type"] != "REG" or g["home_score"] in ("", "NA"):
                continue
            key = (g["season"], g["week"])
            games.setdefault(key, {})[(g["home_team"])] = (float(g["home_score"]), float(g["away_score"]), g["away_team"])
            games.setdefault(key, {})[(g["away_team"])] = (float(g["away_score"]), float(g["home_score"]), g["home_team"])

    def team_points(season, week, team):
        rec = games.get((season, week), {}).get(team)
        return rec[0] if rec else None

    def opp_points(season, week, team):
        rec = games.get((season, week), {}).get(team)
        return rec[1] if rec else None

    # WR1 / WR2 by targets within a team-game
    wr_ranks = {}
    for (season, week, team), d in team_game.items():
        wrs = [(p["targets"], pid, p) for pid, p in d["players"].items() if p["pos"] == "WR"]
        wrs.sort(key=lambda x: (-x[0], x[1]))
        for rank, (_, pid, p) in enumerate(wrs, 1):
            if rank <= 3:
                wr_ranks[(season, week, team, rank)] = (pid, p)

    rb1 = {}
    for (season, week, team), d in team_game.items():
        rbs = [(p["rush_yds"], pid, p) for pid, p in d["players"].items() if p["pos"] == "RB"]
        rbs.sort(key=lambda x: (-x[0], x[1]))
        if rbs:
            rb1[(season, week, team)] = rbs[0][2]

    # ---------------------------------------------------- the correlation set
    pair_hp_ap, pair_margin_total = [], []
    pair_qb_wr1, pair_qb_wr2, pair_wr1_wr2 = [], [], []
    pair_qb_points, pair_rb_points, pair_rb_qb = [], [], []
    pair_rec_rec_yds = []          # receptions vs receiving yards, same player-game
    pair_receptions_targets = []   # control pair: should be high, proves the pipeline is sane
    pair_qb_opp_qb = []
    pair_team_opp = []
    pair_ru_pass = []              # team rushing yards vs team passing yards (play-calling trade-off)
    coverage = {"team_games": len(team_game), "player_games": len(pw),
                "seasons": [int(min(r["season"] for r in pw)), int(max(r["season"] for r in pw))]}

    for (season, week, team), d in team_game.items():
        pts, opp = team_points(season, week, team), opp_points(season, week, team)
        if pts is None:
            continue
        pair_team_opp.append((pts, opp))
        pair_ru_pass.append((d["rush_yds"], d["pass_yds"]))
        qb = qb_of.get((season, week, team))
        if qb:
            qbp = d["players"][qb[0]]
            pair_qb_points.append((qbp["pass_yds"], pts))
            if (season, week, team) in rb1:
                pair_rb_qb.append((rb1[(season, week, team)]["rush_yds"], qbp["pass_yds"]))
            w1 = wr_ranks.get((season, week, team, 1))
            w2 = wr_ranks.get((season, week, team, 2))
            if w1:
                pair_qb_wr1.append((qbp["pass_yds"], w1[1]["rec_yds"]))
            if w2:
                pair_qb_wr2.append((qbp["pass_yds"], w2[1]["rec_yds"]))
            if w1 and w2:
                pair_wr1_wr2.append((w1[1]["rec_yds"], w2[1]["rec_yds"]))
        if (season, week, team) in rb1:
            pair_rb_points.append((rb1[(season, week, team)]["rush_yds"], pts))
        # the opposing team's QB in the same game
        rec = games.get((season, week), {}).get(team)
        if rec:
            opp_team = rec[2]
            oqb = qb_of.get((season, week, opp_team))
            if oqb:
                pair_qb_opp_qb.append((d["players"][qb[0]]["pass_yds"] if qb else 0.0,
                                       team_game[(season, week, opp_team)]["players"][oqb[0]]["pass_yds"]))

    for r in pw:
        if f(r["receptions"]) > 0 or f(r["receiving_yards"]) > 0:
            pair_rec_rec_yds.append((f(r["receptions"]), f(r["receiving_yards"])))
        if f(r["targets"]) > 0:
            pair_receptions_targets.append((f(r["receptions"]), f(r["targets"])))

    corr = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": {
            "inputs": "player-week box scores only (SRC-NFLVERSE-STATS, GSIS definitions SRC-NFL-GSIS); "
                      "team points joined from the schedules feed (SRC-NFLVERSE-SCHED)",
            "excluded": "no market price, no line, no model output enters any coefficient on this page",
            **coverage,
        },
        "method": {
            "estimator": "Pearson product-moment r",
            "interval": "Fisher z, 95% (NIST/SEMATECH)",
            "p_value": "two-sided t approximation, normal limit above n=400",
            "multiple_comparisons": "not applied: these are descriptive measurements published with n, "
                                    "not hypothesis tests used to select a strategy. The strategy page "
                                    "applies BH/Bonferroni where selection happens.",
        },
        "live_values": {},
        "same_game": {},
        "control": {},
    }
    corr["live_values"]["qb_yards_vs_team_points"] = coef(pair_qb_points, "QB passing yards vs own team points")
    corr["live_values"]["rb_yards_vs_team_points"] = coef(pair_rb_points, "RB1 rushing yards vs own team points")
    corr["live_values"]["wr1_yards_vs_team_points"] = coef(
        [(wr_ranks[k][1]["rec_yds"], team_points(k[0], k[1], k[2]))
         for k in wr_ranks if k[3] == 1 and team_points(k[0], k[1], k[2]) is not None],
        "WR1 receiving yards vs own team points")
    corr["live_values"]["rb_yards_vs_qb_yards"] = coef(pair_rb_qb, "RB1 rushing yards vs QB passing yards")
    corr["live_values"]["qb_yards_vs_opp_qb_yards"] = coef(pair_qb_opp_qb, "QB passing yards vs opposing QB passing yards")
    corr["live_values"]["team_points_vs_opp_points"] = coef(pair_team_opp, "Team points vs opponent points")
    corr["live_values"]["rush_yards_vs_pass_yards"] = coef(pair_ru_pass, "Team rushing yards vs team passing yards")

    corr["same_game"]["qb_yards_vs_wr1_yards"] = coef(pair_qb_wr1, "QB passing yards vs WR1 receiving yards",
                                                      "the core same-game parlay pair")
    corr["same_game"]["qb_yards_vs_wr2_yards"] = coef(pair_qb_wr2, "QB passing yards vs WR2 receiving yards")
    corr["same_game"]["wr1_vs_wr2_yards"] = coef(pair_wr1_wr2, "WR1 receiving yards vs WR2 receiving yards")
    corr["same_game"]["receptions_vs_receiving_yards"] = coef(pair_rec_rec_yds, "Receptions vs receiving yards (same player-game)",
                                                               "near-substitutes: do not price as independent legs")
    corr["control"]["receptions_vs_targets"] = coef(pair_receptions_targets, "Receptions vs targets (same player-game)",
                                                     "control pair: a mechanically near-tautological relation that must come out high if the pipeline is sane")
    corr["control"]["margin_vs_total"] = coef(
        [(m, m) for m in []], "placeholder")

    # margin vs total, from the games feed only
    mt = []
    with gzip.open(os.path.join(REPO, "data", "derived", "games.csv.gz"), "rt", newline="") as fh:
        for g in csv.DictReader(fh):
            if g["game_type"] != "REG" or g["home_score"] in ("", "NA"):
                continue
            try:
                h, a = float(g["home_score"]), float(g["away_score"])
            except ValueError:
                continue
            mt.append((h - a, h + a))
    corr["control"]["margin_vs_total"] = coef([(abs(x), y) for x, y in mt], "Absolute margin vs game total",
                                              "control pair from the results feed, not the box score")

    # ---------------------------------------------------- parlay pricing from measured joint rates
    corr["parlay_pricing"] = build_parlay_pricing(pair_qb_wr1, pw)
    corr["prop_combos"] = build_prop_combos(corr, pw)

    A.dump(os.path.join(ROOT, "data", "correlation.json"), corr)
    for sec in ("live_values", "same_game", "control"):
        print(f"\n{sec}:")
        for k, v in corr[sec].items():
            print(f"  {k:34s} r={v['r']} n={v['n']} ci={v['ci']} excl0={v.get('ci_excludes_zero')}")
    pp = corr["parlay_pricing"]
    print(f"\nparlay pricing: 4-leg joint {pp.get('joint_4leg')} vs independent {pp.get('independent_4leg')} "
          f"(overstatement factor {pp.get('factor_4leg')}), n={pp.get('n')}")


def build_parlay_pricing(pair_qb_wr1, pw):
    """P(4 legs) measured against the independent product, using the two same-game pairs.

    A 4-leg parlay here is: QB over, WR1 over (same game, correlated) in two different games.
    The joint of the correlated pair is measured directly; the cross-game multiplication is the
    only independence assumption, and it is named as such.
    """
    if not pair_qb_wr1:
        return {}
    # thresholds at the sample median so P(each leg) = 0.5 by construction, which makes the
    # product comparison exact rather than dependent on the threshold choice
    qb = [p[0] for p in pair_qb_wr1]
    wr = [p[1] for p in pair_qb_wr1]
    qb_t = statistics.median(qb)
    wr_t = statistics.median(wr)
    both = sum(1 for a, b in pair_qb_wr1 if a > qb_t and b > wr_t)
    n = len(pair_qb_wr1)
    p_qb, p_wr = 0.5, 0.5
    joint2 = both / n
    independent2 = p_qb * p_wr
    # two such games in a 4-leg parlay
    joint4 = joint2 ** 2
    independent4 = independent2 ** 2
    lo2, hi2 = A.wilson(both, n)
    return {
        "definition": "4-leg parlay = QB-over + WR1-over (same game) in two independent games.",
        "thresholds": {"qb_pass_yards_over": qb_t, "wr1_rec_yards_over": wr_t,
                       "rule": "sample median, so each leg is a 50% proposition by construction"},
        "n": n,
        "p_leg_each": 0.5,
        "joint_2leg_same_game": round(joint2, 4),
        "joint_2leg_ci": [round(lo2, 4), round(hi2, 4)],
        "independent_2leg": round(independent2, 4),
        "joint_4leg": round(joint4, 4),
        "independent_4leg": round(independent4, 4),
        "factor_4leg": round(joint4 / independent4, 3) if independent4 else None,
        "note": ("Multiplying four legs as if independent would price this parlay at the "
                 "independent figure; the measured joint is the correct number because two legs "
                 "share a game. The cross-game step IS an independence assumption and is labelled."),
        "source": SRC_STATS,
    }


def build_prop_combos(corr, pw):
    """The prop-combo candidates a price feed would let us test. Measured, priced: never."""
    out = {
        "status": "MEASURED_BUT_UNPRICEABLE",
        "reason": ("No historical player-prop prices exist in any committed feed, so no combo can be "
                   "priced or ROI-tested. The joint rates below are what a pricer needs."),
        "combos": [],
        "source": SRC_STATS,
    }
    sg = corr["same_game"]
    for cid, label, keys in [
        ("PC-1", "Receptions over X + receiving yards over Y (same player)", ["receptions_vs_receiving_yards"]),
        ("PC-2", "QB passing yards over X + WR1 receiving yards over Y (same game)", ["qb_yards_vs_wr1_yards"]),
        ("PC-3", "QB passing yards over X + WR2 receiving yards over Y (same game)", ["qb_yards_vs_wr2_yards"]),
        ("PC-4", "WR1 yards over X + WR2 yards over Y (same game)", ["wr1_vs_wr2_yards"]),
    ]:
        c = sg.get(keys[0], {})
        out["combos"].append({
            "id": cid, "label": label, "r": c.get("r"), "n": c.get("n"),
            "ci": c.get("ci"), "ci_excludes_zero": c.get("ci_excludes_zero"),
            "pricing_implication": (
                "positive: independent pricing understates the joint, so the operator's adjusted price "
                "is the one that matters" if (c.get("r") or 0) > 0 else
                "non-positive: legs roughly independent or slightly substitutable"),
            "price_available": False,
            "roi_testable": False,
            "source": SRC_STATS,
        })
    return out


if __name__ == "__main__":
    main()
