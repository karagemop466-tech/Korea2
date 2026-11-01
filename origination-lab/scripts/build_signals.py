#!/usr/bin/env python3
"""Signal research: test a pre-registered list of pregame signals, then control
for multiple testing and out-of-sample decay.

Discovery window: seasons <= 2015.  Validation window: seasons >= 2016.
A signal only earns the label "skill-based candidate" if it survives
  (a) Benjamini-Hochberg FDR across all tests, and
  (b) the same-direction effect in the untouched validation window.

Outputs data/derived/signals.json
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

OUT = nc.DERIVED / "signals.json"
MD = lambda x, n=4: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


def prep():
    g = nc.load_games()
    tg = nc.team_games(g)
    g = nc.attach_team_features(g, tg)
    p = pd.read_csv(nc.DERIVED / "predictions.csv")
    g = g.merge(p[["game_id", "pred_margin", "pred_total"]], on="game_id", how="left")
    g["weekday"] = g["weekday"].fillna("")
    g["roof"] = g["roof"].fillna("")
    return g


def evaluate(df, market, mask, take):
    """Settle at the recorded price. mask/take are boolean arrays aligned to df
    by position. take=True means the home side (ATS) or the over (totals)."""
    mask = np.asarray(mask, dtype=bool)
    take = np.asarray(take, dtype=bool)
    pos = np.flatnonzero(mask)
    sub = df.iloc[pos]
    t = take[pos]
    hm = sub.home_margin.to_numpy(dtype=float)
    hl = sub.home_line.to_numpy(dtype=float)
    if market == "ats":
        keep = (hm + hl) != 0
        won_all = (hm + hl) > 0
        odds_all = np.where(t, sub.home_spread_odds.to_numpy(dtype=float),
                            sub.away_spread_odds.to_numpy(dtype=float))
        line_taken = np.where(t, hl, -hl)
    else:
        tt = sub.total.to_numpy(dtype=float)
        tl = sub.total_line.to_numpy(dtype=float)
        keep = tt != tl
        won_all = (tt - tl) > 0
        odds_all = np.where(t, sub.over_odds.to_numpy(dtype=float),
                            sub.under_odds.to_numpy(dtype=float))
        line_taken = np.where(t, tl, tl)
    keep = keep & pd.notna(odds_all)
    if keep.sum() == 0:
        return None
    won, odds, sub2, lt = won_all[keep], odds_all[keep], sub[keep], line_taken[keep]
    n = int(len(won))
    k = int(won.sum())
    units = np.where(won, [nc.american_to_decimal(o) - 1 for o in odds], -1.0)
    p0 = float(np.mean([nc.american_to_prob(o) for o in odds]))
    lo, hi = nc.wilson(k, n)
    return {
        "bets": n, "wins": k, "hit_rate": MD(k / n), "breakeven_rate": MD(p0),
        "roi": MD(np.mean(units)), "avg_odds": MD(np.mean(odds), 1),
        "wilson_lo": MD(lo), "wilson_hi": MD(hi),
        "p_value": MD(nc.binom_p_greater(k, n, p0), 5),
        "avg_line_taken": MD(np.mean(lt), 2),
        "seasons": f"{int(sub2.season.min())}-{int(sub2.season.max())}",
        "units": MD(np.sum(units), 2),
        "positive_seasons": int(sum(1 for _, u in pd.Series(units, index=sub2.index)
                                    .groupby(sub2.season) if np.mean(u) > 0)),
        "n_seasons": int(sub2.season.nunique()),
    }


def build_registry(df):
    """Each entry: (key, label, market, mask, take_first home/over?, hypothesis)."""
    d = df
    R = []
    add = R.append

    def ats(key, label, mask, side, hyp):
        take = (np.ones(len(d), bool) if side == "home" else np.zeros(len(d), bool))
        add(dict(key=key, label=label, market="ats", mask=mask.values, take=take,
                 side=side, hypothesis=hyp))

    def tot(key, label, mask, side, hyp):
        take = (np.ones(len(d), bool) if side == "over" else np.zeros(len(d), bool))
        add(dict(key=key, label=label, market="total", mask=mask.values, take=take,
                 side=side, hypothesis=hyp))

    ats("home_dog", "Home underdog (ATS)", d.spread_line < 0, "home",
        "Home dogs are systematically under-priced because public money lands on favourites.")
    ats("home_dog_3", "Home underdog by 3+ (ATS)", d.spread_line <= -3, "home",
        "Same as above, restricted to meaningful underdogs.")
    ats("home_fav_7", "Home favourite by 7+ (ATS)", d.spread_line >= 7, "home",
        "Big home favourites are asked to cover inflated numbers.")
    ats("away_fav", "Road favourite (ATS)", d.spread_line < 0, "away",
        "Road favourites win but do not cover at a profitable rate.")
    ats("div_game_home", "Divisional game: home side (ATS)", d.div_game == 1, "home",
        "Divisional familiarity compresses margins toward the number.")
    ats("home_rest3", "Home rest advantage 3+ days (ATS)",
        (d.home_rest - d.away_rest) >= 3, "home",
        "Rest differential is only partly priced into the number.")
    ats("away_rest3", "Away rest advantage 3+ days (ATS)",
        (d.away_rest - d.home_rest) >= 3, "away",
        "Mirror of the rest signal.")
    ats("short_week_home", "Home team on short week (<=5 days rest) (ATS)",
        d.home_rest <= 5, "away", "Short-week teams under-perform the number.")
    ats("thursday", "Thursday games: away side (ATS)", d.weekday == "Thursday", "away",
        "Short-week road teams are the classic fade.")
    ats("monday", "Monday games: home side (ATS)", d.weekday == "Monday", "home",
        "Extra preparation favours the host.")
    ats("dome_home", "Dome game: home side (ATS)", d.roof.isin(["dome", "closed"]), "home",
        "Controlled environment removes weather variance, helping the better team.")
    ats("hot_form_home", "Home team hot last 3 (avg margin >= +7) (ATS)",
        d.h_form3 >= 7, "away", "Recency bias inflates the price of hot teams.")
    ats("cold_form_home", "Home team cold last 3 (avg margin <= -7) (ATS)",
        d.h_form3 <= -7, "home", "Recency bias over-punishes cold teams.")
    ats("ats_hot_home", "Home covered 4+ of last 5 (ATS)",
        d.h_ats_form5 >= 0.79, "away", "Mean reversion in against-the-spread results.")
    ats("ats_cold_home", "Home covered 1 or fewer of last 5 (ATS)",
        d.h_ats_form5 <= 0.21, "home", "Mean reversion in against-the-spread results.")
    ats("qb_change_home", "Home starting QB changed vs previous game (ATS)",
        d.h_qb_changed == 1, "away", "The market over-reacts to a backup QB announcement.")
    ats("qb_change_away", "Away starting QB changed vs previous game (ATS)",
        d.a_qb_changed == 1, "home", "Mirror of the QB-change signal.")
    ats("model_edge_1", "Model spread edge >= 1 pt (ATS)",
        (d.pred_margin - d.spread_line).abs() >= 1.0,
        "model", "Our rating model finds value against the close.")
    tot("wind_15", "Wind >= 15 mph (Under)", d.wind.fillna(0) >= 15, "under",
        "Wind suppresses passing efficiency and scoring.")
    tot("cold_32", "Kickoff temp <= 32F (Under)", d.temp.fillna(99) <= 32, "under",
        "Cold weather suppresses scoring.")
    tot("dome_over", "Dome game (Over)", d.roof.isin(["dome", "closed"]), "over",
        "Controlled conditions and fast turf raise scoring.")
    tot("total_high", "Total >= 50 (Over)", d.total_line >= 50, "over",
        "High totals may under-price the modern passing boom.")
    tot("total_low", "Total <= 40 (Under)", d.total_line <= 40, "under",
        "Low totals may under-price defensive matchups.")
    tot("div_under", "Divisional game (Under)", d.div_game == 1, "under",
        "Familiarity produces lower-scoring games.")
    tot("model_total_edge_1", "Model total edge >= 1 pt (Over side)",
        (d.pred_total - d.total_line) >= 1.0, "over",
        "Our scoring model finds value against the close.")
    tot("week1_over", "Week 1 (Over)", d.week == 1, "over",
        "Offences are ahead of defences early in the season.")
    tot("playoff_under", "Playoff games (Under)", d.game_type != "REG", "under",
        "Playoff games are lower-scoring than the market expects.")
    return R


def main():
    df = prep()
    df = df[df.season >= nc.FIRST_EVAL_SEASON]
    # model-side rule needs per-row side selection
    reg = build_registry(df)
    for r in reg:
        if r["side"] == "model":
            r["take"] = ((df.pred_margin - df.spread_line) > 0).values

    disc = df.season <= nc.DISCOVERY_END
    rows = []
    for r in reg:
        base = evaluate(df, r["market"], r["mask"], r["take"])
        if base is None:
            continue
        d_eval = evaluate(df[disc], r["market"], r["mask"][disc.values], r["take"][disc.values])
        v_eval = evaluate(df[~disc], r["market"], r["mask"][~disc.values], r["take"][~disc.values])
        rows.append({
            "key": r["key"], "label": r["label"], "market": r["market"],
            "side": r["side"], "hypothesis": r["hypothesis"],
            "full": base, "discovery": d_eval, "validation": v_eval,
        })

    # multiple-testing control over the full-sample p-values
    p = [r["full"]["p_value"] if r["full"]["p_value"] is not None else 1.0 for r in rows]
    q = nc.bh_qvalues(p)
    for r, qq, pp in zip(rows, q, p):
        r["full"]["q_value"] = MD(qq, 5)
        r["screened"] = bool(qq < 0.10 and pp < 0.05)
        val = r["validation"]
        if val is None:
            r["verdict"] = "insufficient data"
        elif r["screened"] and (val["hit_rate"] > val["breakeven_rate"]):
            r["verdict"] = "survives OOS"
        elif r["screened"]:
            r["verdict"] = "fails OOS"
        elif pp < 0.05:
            r["verdict"] = "fails FDR"
        else:
            r["verdict"] = "no signal"

    rows.sort(key=lambda r: (r["full"]["p_value"] if r["full"]["p_value"] is not None else 1))
    n_tests = len(rows)
    payload = {
        "n_tests": n_tests,
        "windows": {"discovery": f"{nc.FIRST_EVAL_SEASON}-{nc.DISCOVERY_END}",
                    "validation": f"{nc.DISCOVERY_END + 1}-{int(df.season.max())}"},
        "fdr_threshold": 0.10,
        "expected_false_positives_at_05": MD(n_tests * 0.05, 2),
        "signals": rows,
        "survivors": [r["key"] for r in rows if r["verdict"] == "survives OOS"],
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"tests={n_tests} survivors={payload['survivors']}")
    for r in rows[:8]:
        f = r["full"]
        print(f"{r['key']:22s} n={f['bets']:5d} hit={f['hit_rate']:.3f} "
              f"roi={f['roi']:+.4f} p={f['p_value']:.4f} q={f['q_value']:.3f} "
              f"val={'-' if not r['validation'] else round(r['validation']['roi'],3)} {r['verdict']}")


if __name__ == "__main__":
    main()
