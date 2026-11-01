#!/usr/bin/env python3
"""Strategy backtesting, validation gates, and the leaderboard.

Every strategy is a deterministic rule over pregame information. Bets are settled
at the American price recorded in the source extract (never at an assumed -110).
Pushes return the stake.

WINDOWS
  discovery : 2006-2015 (odds coverage starts in 2006 in the source extract)
  validation: 2016-latest

GATES (all must pass for a strategy to be ranked on the leaderboard)
  G1 sample        n >= 150 settled bets in the validation window
  G2 significance  validation rois_p < 0.05 AND BH q < 0.10 across all strategies
  G3 consistency   discovery ROI > 0 AND validation ROI > 0 AND positive-season
                   share >= 0.55
  G4 price shock   ROI stays > 0 when every recorded price is made 5 cents worse
  G5 drawdown      validation max drawdown <= 20u and no single season carries
                   more than 40% of validation profit
  G6 reality check max-statistic permutation p < 0.10 (controls selecting the
                   best of N tested strategies)
  G7 coverage      >= 25 bets per season on average, and every input reproducible
                   from the hashed manifest

Outputs data/derived/strategies.json
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nflcore as nc

OUT = nc.DERIVED / "strategies.json"
MD = lambda x, n=4: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)
MIN_BETS_G1 = 150
PRICE_SHOCK = 5.0
TEASER_PRICE = -110.0   # standard 2-team 6-pt price; sensitivity shown on the site


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def haircut(odds, cents=PRICE_SHOCK):
    """Make a price `cents` worse (more negative / smaller positive)."""
    o = np.asarray(odds, dtype=float)
    out = np.where(o < 0, o - cents, o - cents)
    out = np.where(out > -100, np.where(o < 0, -100, out), out)
    return out


def bet_row(season, week, gameday, label, strat, odds, won, push=False, legs=""):
    return dict(season=int(season), week=int(week), gameday=gameday, label=label,
                strategy=strat, odds=float(odds), won=bool(won), push=bool(push),
                legs=legs)


def profit(odds, won, push=False):
    if push:
        return 0.0
    return (nc.american_to_decimal(odds) - 1.0) if won else -1.0


def ats_bets(df, side_home, label, strat):
    """df rows already filtered; side_home is a boolean array."""
    out = []
    for (_, r), home in zip(df.iterrows(), side_home):
        m = r.home_margin + r.home_line
        if m == 0:
            out.append(bet_row(r.season, r.week, r.gameday, label, strat,
                               r.home_spread_odds if home else r.away_spread_odds,
                               False, True, f"{r.away_team}@{r.home_team} {r.home_line:+.1f}"))
            continue
        won = (m > 0) == bool(home)
        odds = r.home_spread_odds if home else r.away_spread_odds
        out.append(bet_row(r.season, r.week, r.gameday, label, strat, odds, won, False,
                           f"{'home' if home else 'away'} {r.away_team}@{r.home_team} {r.home_line:+.1f}"))
    return out


def total_bets(df, take_over, label, strat):
    out = []
    for (_, r), over in zip(df.iterrows(), take_over):
        m = r.total - r.total_line
        if m == 0:
            out.append(bet_row(r.season, r.week, r.gameday, label, strat,
                               r.over_odds, False, True, f"{r.away_team}@{r.home_team} O/U {r.total_line}"))
            continue
        won = (m > 0) == bool(over)
        odds = r.over_odds if over else r.under_odds
        out.append(bet_row(r.season, r.week, r.gameday, label, strat, odds, won, False,
                           f"{'over' if over else 'under'} {r.total_line} {r.away_team}@{r.home_team}"))
    return out


def ml_bets(df, side_home, label, strat):
    out = []
    for (_, r), home in zip(df.iterrows(), side_home):
        if r.home_margin == 0:
            out.append(bet_row(r.season, r.week, r.gameday, label, strat,
                               r.home_moneyline if home else r.away_moneyline, False, True,
                               f"{r.away_team}@{r.home_team} ML"))
            continue
        won = (r.home_margin > 0) == bool(home)
        odds = r.home_moneyline if home else r.away_moneyline
        out.append(bet_row(r.season, r.week, r.gameday, label, strat, odds, won, False,
                           f"{'home' if home else 'away'} ML {r.away_team}@{r.home_team}"))
    return out


def dec_to_american(dec: float) -> float:
    dec = max(dec, 1.01)
    return round((dec - 1.0) * 100.0) if dec >= 2.0 else round(-100.0 / (dec - 1.0))


def parlay_settle(legs, label, strat):
    """legs: list of dicts with odds (American), won, push.

    The ticket price is the product of the leg decimal prices expressed back in
    American odds, so the settlement code has a single code path."""
    dec = 1.0
    for lg in legs:
        dec *= nc.american_to_decimal(lg["odds"])
    odds = dec_to_american(dec)
    push = all(lg["push"] for lg in legs)
    won = all(lg["won"] or lg["push"] for lg in legs) and not any(lg["push"] for lg in legs)
    if any(lg["push"] for lg in legs) and not push:
        # Provider-specific rule. We settle conservatively: the whole ticket is a
        # push. This under-states any edge, never over-states it.
        return dict(odds=odds, won=False, push=True, decimal=dec)
    return dict(odds=odds, won=won, push=push, decimal=dec)


# --------------------------------------------------------------------------- #
# strategy definitions
# --------------------------------------------------------------------------- #
def build_bets(df):
    """Return {key: (meta, list_of_bet_rows)}."""
    S = {}

    def add(key, name, category, market, thesis, rows, notes=""):
        S[key] = dict(key=key, name=name, category=category, market=market,
                      thesis=thesis, notes=notes, rows=rows)

    # ---------- singles ----------
    d = df[df.odds_complete & (df.pred_margin.notna())]
    take_home = (d.pred_margin - d.spread_line) > 0
    add("S1_model_ats_1", "Model spread edge >= 1 pt (ATS)", "single", "spread",
        "Bet the side our rating model rates above the market close.",
        ats_bets(d[(d.pred_margin - d.spread_line).abs() >= 1.0],
                 take_home[(d.pred_margin - d.spread_line).abs() >= 1.0],
                 "model-1", "S1_model_ats_1"))

    d2 = d[(d.pred_margin - d.spread_line).abs() >= 2.0]
    add("S2_model_ats_2", "Model spread edge >= 2 pts (ATS)", "single", "spread",
        "Stricter version of S1: only large disagreements with the close.",
        ats_bets(d2, (d2.pred_margin - d2.spread_line) > 0, "model-2", "S2_model_ats_2"))

    t = df[df.odds_complete & df.pred_total.notna()]
    edge = t.pred_total - t.total_line
    add("S3_model_total_2", "Model total edge >= 2 pts", "single", "total",
        "Bet the over/under when our points model disagrees with the close by 2+.",
        total_bets(t[edge.abs() >= 2.0], edge[edge.abs() >= 2.0] > 0,
                   "model-ot-2", "S3_model_total_2"))

    m = df[df.odds_complete & df.pred_margin.notna() & df.home_moneyline.notna()].copy()
    from scipy.stats import norm
    m["p_home"] = norm.cdf(m.pred_margin / 13.6)
    m["p_mkt"] = [nc.american_to_prob(h) / (nc.american_to_prob(h) + nc.american_to_prob(a))
                  for h, a in zip(m.home_moneyline, m.away_moneyline)]
    m["edge_ml"] = m.p_home - m.p_mkt
    sel = m[m.edge_ml.abs() >= 0.03]
    add("S4_model_ml_3", "Model moneyline edge >= 3 pts", "single", "moneyline",
        "Bet the moneyline side when our win probability beats the no-vig market by 3+.",
        ml_bets(sel, sel.edge_ml > 0, "model-ml-3", "S4_model_ml_3"))

    # market-structure singles tested in the signal layer but carried here for the board
    dogs = d[d.spread_line < 0]
    add("S5_home_dog", "Home underdogs (ATS)", "single", "spread",
        "Classic public-fade: back every home underdog at the close.",
        ats_bets(dogs, np.ones(len(dogs), bool), "home-dog", "S5_home_dog"))

    dogs3 = d[d.spread_line <= -3]
    add("S6_home_dog_3", "Home underdogs of 3+ (ATS)", "single", "spread",
        "Home underdogs of a field goal or more.",
        ats_bets(dogs3, np.ones(len(dogs3), bool), "home-dog3", "S6_home_dog_3"))

    fav7 = d[d.spread_line >= 7]
    add("S7_fade_home_fav7", "Fade home favourites of 7+ (ATS)", "single", "spread",
        "Take the road dog against big home favourites.",
        ats_bets(fav7, np.zeros(len(fav7), bool), "fade-fav7", "S7_fade_home_fav7"))

    div = d[(d.div_game == 1) & (d.spread_line < 0)]
    add("S8_div_home_dog", "Divisional home underdogs (ATS)", "single", "spread",
        "Familiarity plus a hostile crowd is the least-priced combination.",
        ats_bets(div, np.ones(len(div), bool), "div-dog", "S8_div_home_dog"))

    rest = d[(d.home_rest - d.away_rest) >= 3]
    add("S9_rest_home", "Home rest advantage 3+ days (ATS)", "single", "spread",
        "Rest differential of at least three days in the home team's favour.",
        ats_bets(rest, np.ones(len(rest), bool), "rest-home", "S9_rest_home"))

    coldform = d[d.h_form3 <= -7]
    add("S10_buy_cold", "Buy cold home teams (avg margin <= -7 last 3) (ATS)", "single", "spread",
        "Mean reversion: the market chases recency.",
        ats_bets(coldform, np.ones(len(coldform), bool), "cold-home", "S10_buy_cold"))

    windy = df[df.odds_complete & (df.wind.fillna(0) >= 15)]
    add("S11_wind_under", "Wind 15+ mph (Under)", "single", "total",
        "Wind degrades passing efficiency; bet the under.",
        total_bets(windy, np.zeros(len(windy), bool), "wind-u", "S11_wind_under"))

    dome = df[df.odds_complete & df.roof.isin(["dome", "closed"])]
    add("S12_dome_over", "Dome games (Over)", "single", "total",
        "Fast, dry, windless conditions raise scoring.",
        total_bets(dome, np.ones(len(dome), bool), "dome-o", "S12_dome_over"))

    off = df[df.odds_complete & df.off_market & (df.open_total.notna())]
    off = off[(off.open_total - off.total_line) >= 1.5]      # total moved DOWN from the open
    add("S13_off_market_total", "Unders when the total moves down 1.5+ from the open (2021 only)",
        "single", "total",
        "Follow reverse line movement in the totals market (opening lines exist in the source "
        "extract for the 2021 season only, so this is a one-season probe, not a validated strategy).",
        total_bets(off, np.zeros(len(off), bool), "rlm-u", "S13_off_market_total"),
        notes="Exploratory: one season, fails G1 by construction.")

    # ---------- parlays ----------
    p = df[df.odds_complete & df.pred_margin.notna()].copy()
    p["edge"] = (p.pred_margin - p.spread_line).abs()
    rows = []
    for (season, week), wk in p.groupby(["season", "week"]):
        top = wk.sort_values("edge", ascending=False).head(4)
        for a, b in itertools.combinations(top.itertuples(), 2):
            legs = []
            for r in (a, b):
                mres = r.home_margin + r.home_line
                home = (r.pred_margin - r.spread_line) > 0
                legs.append(dict(odds=r.home_spread_odds if home else r.away_spread_odds,
                                 won=mres > 0 if home else mres < 0, push=mres == 0))
            # note: push and non-push together cannot both be true; guard below
            s = parlay_settle(legs, "parlay", "S14")
            rows.append(bet_row(season, week, a.gameday, f"{a.away_team}@{a.home_team}+{b.away_team}@{b.home_team}",
                                "S14_model_ats_parlay2", s["odds"], s["won"], s["push"]))
    add("S14_model_ats_parlay2", "2-leg parlay: top-2 model spread edges each week", "parlay", "spread",
        "Combines the two largest model disagreements of the week into a 2-leg parlay.",
        rows)

    # 3-leg parlay of the biggest model edges
    rows = []
    for (season, week), wk in p.groupby(["season", "week"]):
        topl = wk.sort_values("edge", ascending=False).head(3)
        if len(topl) < 3:
            continue
        legs = []
        for r in topl.itertuples():
            mres = r.home_margin + r.home_line
            home = (r.pred_margin - r.spread_line) > 0
            legs.append(dict(odds=r.home_spread_odds if home else r.away_spread_odds,
                             won=(mres > 0) if home else (mres < 0), push=mres == 0))
        s = parlay_settle(legs, "parlay3", "S15")
        rows.append(bet_row(season, week, topl.gameday.iloc[0], f"3-leg wk{week}",
                            "S15_model_ats_parlay3", s["odds"], s["won"], s["push"]))
    add("S15_model_ats_parlay3", "3-leg parlay: top-3 model spread edges each week", "parlay", "spread",
        "Three-leg version of S14; variance is higher and the vig compounds.", rows)

    # 2-leg moneyline parlay on the week's two shortest-priced favourites
    mlf = df[df.odds_complete & df.home_moneyline.notna()].copy()
    # "shortest-priced favourite" = the side with the highest implied win probability
    mlf["fav_prob"] = np.maximum(mlf.home_moneyline.map(nc.american_to_prob),
                                 mlf.away_moneyline.map(nc.american_to_prob))
    rows = []
    for (season, week), wk in mlf.groupby(["season", "week"]):
        top = wk.sort_values("fav_prob", ascending=False).head(2)
        if len(top) < 2:
            continue
        legs = []
        for r in top.itertuples():
            home_is_fav = r.home_moneyline < r.away_moneyline
            legs.append(dict(odds=r.home_moneyline if home_is_fav else r.away_moneyline,
                             won=(r.home_margin > 0) if home_is_fav else (r.home_margin < 0),
                             push=r.home_margin == 0))
        s = parlay_settle(legs, "ml2", "S16")
        rows.append(bet_row(season, week, top.gameday.iloc[0], f"2-leg ML favs wk{week}",
                            "S16_ml_fav_parlay2", s["odds"], s["won"], s["push"]))
    add("S16_ml_fav_parlay2", "2-leg moneyline parlay: two shortest-priced favourites each week",
        "parlay", "moneyline",
        "The most popular recreational parlay construction; included as a benchmark.", rows)

    # same-game parlay: spread + total of the same game (correlation matters)
    sgp = df[df.odds_complete & df.pred_margin.notna() & df.pred_total.notna()].copy()
    sgp["e_s"] = sgp.pred_margin - sgp.spread_line
    sgp["e_t"] = sgp.pred_total - sgp.total_line
    pick = sgp[(sgp.e_s.abs() >= 1.5) & (sgp.e_t.abs() >= 1.5)]
    rows = []
    for r in pick.itertuples():
        home = r.e_s > 0
        over = r.e_t > 0
        mres = r.home_margin + r.home_line
        tres = r.total - r.total_line
        legs = [dict(odds=r.home_spread_odds if home else r.away_spread_odds,
                     won=(mres > 0) if home else (mres < 0), push=mres == 0),
                dict(odds=r.over_odds if over else r.under_odds,
                     won=(tres > 0) if over else (tres < 0), push=tres == 0)]
        s = parlay_settle(legs, "sgp", "S17")
        rows.append(bet_row(r.season, r.week, r.gameday,
                            f"{r.away_team}@{r.home_team} SGP",
                            "S17_sgp_spread_total", s["odds"], s["won"], s["push"]))
    add("S17_sgp_spread_total", "Same-game parlay: model spread + model total in one game",
        "sgp", "spread+total",
        "Two model edges in the same game; the legs are correlated, so the product of the "
        "prices over-states the true payout requirement.", rows,
        notes="Priced as the product of the two closing prices; correlated-pricing analysis "
              "is on the Correlation page.")

    # ---------- teasers ----------
    def tease_rows(dfin, side_rules, points, key):
        out = []
        for _, r in dfin.iterrows():
            hm = r.home_margin
            gt = r.total
            ok = True
            legs = []
            for side in side_rules(r):
                if side[0] == "sd":
                    line = r.home_line + side[1] * points
                    res = hm + line
                    legs.append(dict(res=res))
                else:
                    line = r.total_line + side[1] * points
                    res = (gt - line) * (1 if side[0] == "over" else -1)
                    legs.append(dict(res=res))
            if not legs:
                ok = False
            out.append((r, legs, key))
        return out

    # Wong-style 6-point two-team teaser: dogs +1.5/+2.5 and favourites -7.5/-8.5
    wong = df[df.odds_complete].copy()
    rows = []
    cand = {}
    for _, r in wong.iterrows():
        hl = r.home_line
        who = None
        if 1.5 <= hl <= 2.5:
            who = ("away", hl)
        elif -8.5 <= hl <= -7.5:
            who = ("home", hl)
        if who:
            cand.setdefault((r.season, r.week), []).append((r, who))
    for (season, week), items in cand.items():
        if len(items) < 2:
            continue
        picked = items[:2]
        legs = []
        for r, (side, hl) in picked:
            if side == "away":
                # away line is -hl; +6 in the away side's favour -> covers if
                # (-home_margin) + (-hl + 6) > 0
                res = -r.home_margin - hl + 6.0
            else:
                # home line hl; +6 in the home side's favour -> covers if
                # home_margin + (hl + 6) > 0
                res = r.home_margin + hl + 6.0
            legs.append(dict(odds=-110.0, won=res > 0, push=res == 0))
        s = parlay_settle(legs, "wong6", "S18")
        rows.append(bet_row(season, week, picked[0][0].gameday,
                            f"wong {picked[0][1][0]}/{picked[1][1][0]}", "S18_wong_teaser6",
                            s["odds"], s["won"], s["push"]))
    # A teaser pays a fixed two-team price, not the product of the leg prices.
    # evaluate_strategy() overrides `odds` with TEASER_PRICE for this category.
    add("S18_wong_teaser6", "2-team 6-pt teaser on Wong legs (+1.5/+2.5 dogs, -7.5/-8.5 favs)",
        "teaser", "teaser",
        "Teasers shift the line across the two most common margin numbers (3 and 7), so the "
        "true cover rate rises faster than the price does. Priced here at the standard "
        "-110 two-team teaser price, with -120/-130 sensitivity on the correlation page.",
        rows,
        notes="Teaser pricing is book-specific. The analysis reports the price sensitivity "
              "explicitly; see Flagged for Review.")

    return S


# --------------------------------------------------------------------------- #
# metrics & gates
# --------------------------------------------------------------------------- #
def metrics(bets: pd.DataFrame, teaser_fixed_odds: float | None = None):
    if bets.empty:
        return None
    b = bets.copy()
    b = b[b.odds.notna()]
    if teaser_fixed_odds is not None:
        b["odds"] = teaser_fixed_odds
    b["units"] = [profit(o, w, p) for o, w, p in zip(b.odds, b.won, b.push)]
    b["paid"] = ~b.push
    sel = b[b.paid]
    n = int(len(sel))
    if n == 0:
        return None
    wins = int(sel.won.sum())
    breakeven = float(np.mean([nc.american_to_prob(o) for o in sel.odds]))
    return {
        "bets": n, "wins": wins, "losses": int(n - wins), "pushes": int((~b.paid).sum()),
        "hit_rate": MD(wins / n), "breakeven_rate": MD(breakeven),
        "roi": MD(sel.units.mean()), "units": MD(b.units.sum(), 2),
        "avg_odds": MD(sel.odds.mean(), 1),
        "wilson_lo": MD(nc.wilson(wins, n)[0]), "wilson_hi": MD(nc.wilson(wins, n)[1]),
        "p_value": MD(nc.binom_p_greater(wins, n, breakeven), 5),
        "t_stat": MD(nc.t_stat(sel.units.to_numpy()), 3),
        "boot_ci": [MD(x) for x in nc.bootstrap_ci(sel.units.to_numpy(), 2000)],
        "max_drawdown": MD(nc.max_drawdown(sel.units.to_numpy()), 2),
        "positive_seasons": int(sum(1 for _, s in sel.groupby("season") if s.units.mean() > 0)),
        "n_seasons": int(sel.season.nunique()),
        "per_season": {str(int(k)): MD(v, 3) for k, v in sel.groupby("season").units.mean().items()},
        "bet_counts_by_season": {str(int(k)): int(v) for k, v in sel.groupby("season").size().items()},
        "_units_series": sel.units.to_numpy(),
        "_weekly": sel.groupby(["season", "week"]).units.mean(),
        "_season_units": sel.groupby("season").units.sum(),
        "max_season_units": MD(sel.groupby("season").units.sum().max(), 2),
        "_bets_frame": sel,
    }


def evaluate_strategy(meta, bets, teaser_fixed_odds=None):
    b = pd.DataFrame(bets)
    if b.empty:
        return None
    fixed = TEASER_PRICE if meta["category"] == "teaser" else None
    full = metrics(b, fixed)
    if full is None:
        return None
    disc = metrics(b[b.season <= nc.DISCOVERY_END], fixed)
    val = metrics(b[b.season > nc.DISCOVERY_END], fixed)
    # price shock
    shock_rows = b.copy()
    if fixed is None:
        shock_rows["odds"] = haircut(shock_rows.odds)
    else:
        shock_rows["odds"] = fixed - PRICE_SHOCK
    shock = metrics(shock_rows, None)
    entry = dict(meta)
    for k in ("_units_series", "_weekly", "_season_units", "_bets_frame"):
        entry[k] = full.pop(k)
    entry["full"] = full
    for side in (disc, val):
        if side:
            for k in ("_units_series", "_weekly", "_season_units", "_bets_frame"):
                side.pop(k, None)
    entry["discovery"] = disc
    entry["validation"] = val
    entry["price_shock_roi"] = MD(shock["roi"]) if shock else None
    entry["teaser_price"] = fixed
    return entry


def apply_gates(results, reality_p):
    for r in results:
        v = r.get("validation")
        f = r["full"]
        g = {}
        g["G1_sample"] = bool(v and v["bets"] >= MIN_BETS_G1)
        # significance is judged on the FULL sample (maximum power) and must also
        # survive Benjamini-Hochberg across the whole programme (45 tests).
        g["G2_significance"] = bool(f["p_value"] is not None and f["p_value"] < 0.05
                                   and r.get("q_value") is not None and r["q_value"] < 0.10)
        g["G3_consistency"] = bool(
            r.get("discovery") and r["discovery"]["roi"] is not None
            and v and v["roi"] is not None
            and r["discovery"]["roi"] > 0 and v["roi"] > 0
            and (v["positive_seasons"] / max(v["n_seasons"], 1)) >= 0.55)
        g["G4_price_shock"] = bool(r.get("price_shock_roi") is not None
                                   and r["price_shock_roi"] > 0 and v and v["roi"] > 0)
        g["G5_drawdown"] = bool(
            v and v["max_drawdown"] <= 20.0
            and v["max_season_units"] is not None and v["units"] > 0
            and v["max_season_units"] <= 0.40 * v["units"])
        g["G6_reality_check"] = bool(reality_p.get(r["key"]) is not None
                                     and reality_p[r["key"]] < 0.10)
        g["G7_coverage"] = bool(v and v["n_seasons"] > 0
                                and v["bets"] / v["n_seasons"] >= 25)
        r["gates"] = g
        r["gates_passed"] = int(sum(g.values()))
        r["gates_total"] = len(g)
        r["eligible"] = all(g.values())
        r["failed_gates"] = [k for k, v_ in g.items() if not v_]


def reality_check(results, n_boot=3000, seed=11):
    """White-style max-statistic bootstrap over a shared week index."""
    val = [r for r in results if r.get("validation") and len(r["_weekly"]) > 0]
    if not val:
        return {}
    idx = sorted(set().union(*[set(r["_weekly"].index) for r in val]))
    idx_pos = {k: i for i, k in enumerate(idx)}
    M = np.full((len(val), len(idx)), np.nan)
    for i, r in enumerate(val):
        for k, v in r["_weekly"].items():
            M[i, idx_pos[k]] = v
    obs = np.array([np.nan_to_num(M[i]).mean() for i in range(len(val))])
    rng = np.random.default_rng(seed)
    centered = M - np.nanmean(M, axis=1, keepdims=True)
    # fill NaNs with 0 for resampling only (a week with no bet has no return)
    centered = np.nan_to_num(centered, nan=0.0)
    n_weeks = M.shape[1]
    block = 4
    max_null = np.empty(n_boot)
    for b in range(n_boot):
        picks, cur = [], 0
        while cur < n_weeks:
            start = rng.integers(0, n_weeks)
            take = min(block, n_weeks - cur)
            picks.extend([(start + j) % n_weeks for j in range(take)])
            cur += take
        samp = centered[:, picks]
        max_null[b] = np.max(samp.mean(axis=1))
    out = {}
    for i, r in enumerate(val):
        out[r["key"]] = float((max_null >= obs[i]).mean())
    return out


def main():
    g = nc.load_games()
    g = g[g.season >= 2006]
    tg = nc.team_games(g)
    g = nc.attach_team_features(g, tg)
    p = pd.read_csv(nc.DERIVED / "predictions.csv")
    g = g.merge(p[["game_id", "pred_margin", "pred_total"]], on="game_id", how="left")
    g["roof"] = g["roof"].fillna("")
    g["odds_complete"] = g[["home_spread_odds", "away_spread_odds",
                            "over_odds", "under_odds"]].notna().all(axis=1)
    g = g.sort_values(["season", "week", "gameday"]).reset_index(drop=True)
    # opening-line join (2021 only in the source extract)
    opens = pd.read_csv(nc.RAW / "initial_lines.csv")
    osp = opens[(opens.type == "SPREAD") & (opens.side.isin(g.home_team.unique()))]
    otot = opens[opens.type == "TOTAL"]
    omap, tmap = {}, {}
    for _, r in osp.iterrows():
        omap.setdefault(r.about, {})[r.side] = r.line
    for _, r in otot.iterrows():
        tmap.setdefault(r.about, r.line)
    g["open_spread"] = [omap.get(gid, {}).get(home) for gid, home in zip(g.game_id, g.home_team)]
    g["open_total"] = [tmap.get(gid) for gid in g.game_id]
    g["off_market"] = g.open_spread.notna() & g.spread_line.notna()

    S = build_bets(g)
    results = []
    for key, meta in S.items():
        entry = evaluate_strategy({k: v for k, v in meta.items() if k != "rows"}, meta["rows"])
        if entry:
            results.append(entry)

    # Multiple-testing family = the WHOLE research programme: every signal test and
    # every strategy test. That is the honest family size when both layers are
    # reported from the same data.
    sig_path = nc.DERIVED / "signals.json"
    sig_ps = []
    if sig_path.exists():
        sig_ps = [x["full"]["p_value"] for x in json.loads(sig_path.read_text())["signals"]
                  if x["full"].get("p_value") is not None]
    strat_ps = [r["full"]["p_value"] if r["full"].get("p_value") is not None else 1.0
                for r in results]
    all_ps = sig_ps + strat_ps
    q_all = nc.bh_qvalues(all_ps)
    q_strat = q_all[len(sig_ps):]
    for r, qq in zip(results, q_strat):
        r["q_value"] = MD(qq, 5)
    payload_family = {"n_signal_tests": len(sig_ps), "n_strategy_tests": len(strat_ps),
                      "family_size": len(all_ps)}

    rp = reality_check(results)
    apply_gates(results, rp)
    for r in results:
        r["reality_check_p"] = MD(rp.get(r["key"]), 4)

    # leaderboard scoring: only gate-passing strategies are ranked
    for r in results:
        v = r.get("validation") or {}
        roi = v.get("roi") or 0.0
        score = 50.0 + 250.0 * max(min(roi, 0.20), -0.20)
        score += 15.0 * (1.0 if (v.get("p_value") or 1) < 0.05 else 0.0)
        score += 15.0 * (v.get("positive_seasons", 0) / max(v.get("n_seasons", 1), 1))
        score += 10.0 * min((v.get("bets", 0) / 300.0), 1.0)
        score += 10.0 * (r["gates_passed"] / r["gates_total"])
        r["score"] = MD(score, 2)

    ranked = sorted([r for r in results if r["eligible"]], key=lambda r: -r["score"])
    unranked = sorted([r for r in results if not r["eligible"]],
                      key=lambda r: -(r["score"] or 0))
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
        r["tier"] = "Gold" if r["gates_passed"] == r["gates_total"] else (
            "Silver" if r["gates_passed"] == r["gates_total"] - 1 else "Bronze")
    for r in unranked:
        r["rank"] = None
        r["tier"] = "Unranked"

    payload = {
        "windows": {"discovery": "2006-2015", "validation": "2016-2026"},
        "n_strategies": len(results),
        "n_eligible": len(ranked),
        "multiple_testing_family": payload_family,
        "gates": {
            "G1_sample": f"n >= {MIN_BETS_G1} settled bets in the validation window",
            "G2_significance": "full-sample p < 0.05 vs the vig-aware break-even AND Benjamini-Hochberg q < 0.10 across the whole programme (27 signals + 18 strategies)",
            "G3_consistency": "discovery ROI > 0, validation ROI > 0, >= 55% of validation seasons positive",
            "G4_price_shock": "validation ROI stays > 0 when every recorded price is 5 cents worse",
            "G5_drawdown": "validation max drawdown <= 20u and no season > 40% of validation profit",
            "G6_reality_check": "max-statistic block-bootstrap p < 0.10 (best-of-N correction)",
            "G7_coverage": ">= 25 bets per season on average in the validation window",
        },
        "reward_schedule": [
            {"tier": "Gold", "condition": "all 7 gates", "pool_share": 0.60},
            {"tier": "Silver", "condition": "6 of 7 gates", "pool_share": 0.30},
            {"tier": "Bronze", "condition": "5 of 7 gates", "pool_share": 0.10},
            {"tier": "Unranked", "condition": "4 or fewer gates", "pool_share": 0.0},
        ],
        "leaderboard": ranked + unranked,
    }
    OUT.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    print(f"strategies={len(results)} eligible={len(ranked)}")
    for r in (ranked + unranked):
        v = r.get("validation") or {}
        print(f"{r['key']:26s} n={r['full']['bets']:5d} roi={r['full']['roi']:+.4f} "
              f"val_roi={(v.get('roi') if v.get('roi') is not None else float('nan')):+.4f} "
              f"p={(v.get('p_value') if v.get('p_value') is not None else 1):.4f} "
              f"gates={r['gates_passed']}/7 rc={r['reality_check_p']} score={r['score']} "
              f"fail={','.join(x.split('_')[0] for x in r['failed_gates'])}")


if __name__ == "__main__":
    main()
