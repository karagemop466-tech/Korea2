#!/usr/bin/env python3
"""Correlation values for singles, parlays and player-prop combinations.

Everything here is estimated from settled outcomes in the verified extracts:
the statistic is the Pearson phi coefficient between two binary leg outcomes,
which is what a same-game parlay actually needs (the legs are Bernoulli).

Outputs data/derived/correlations.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nflcore as nc

OUT = nc.DERIVED / "correlations.json"
MD = lambda x, n=4: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


def phi(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def phi_ci(r, n, z=1.96):
    if not np.isfinite(r) or n < 5:
        return (float("nan"), float("nan"))
    f = np.arctanh(r)
    se = 1 / math.sqrt(n - 3)
    return (float(np.tanh(f - z * se)), float(np.tanh(f + z * se)))


def chi2_p(r, n):
    if not np.isfinite(r) or n < 5:
        return float("nan")
    from scipy.stats import chi2
    stat = n * r * r
    return float(chi2.sf(stat, 1))


def pair(name, leg_a, leg_b, n_note=""):
    m = np.isfinite(leg_a) & np.isfinite(leg_b)
    a, b = np.asarray(leg_a)[m], np.asarray(leg_b)[m]
    n = int(len(a))
    if n < 30:
        return None
    r = phi(a, b)
    lo, hi = phi_ci(r, n)
    pa, pb = float(a.mean()), float(b.mean())
    return {
        "pair": name, "n": n, "phi": MD(r, 3), "ci_lo": MD(lo, 3), "ci_hi": MD(hi, 3),
        "p_value": MD(chi2_p(r, n), 6),
        "p_a": MD(pa), "p_b": MD(pb),
        "p_both_independent": MD(pa * pb), "p_both_actual": MD(float((a * b).mean())),
        "lift_pct": MD((float((a * b).mean()) / (pa * pb) - 1) * 100, 1) if pa * pb > 0 else None,
        "note": n_note,
    }


def copula_joint(p1, p2, rho):
    """Gaussian copula joint probability with normal marginals."""
    if rho == 0:
        return p1 * p2
    x = norm.ppf(min(max(p1, 1e-9), 1 - 1e-9))
    y = norm.ppf(min(max(p2, 1e-9), 1 - 1e-9))
    from scipy.stats import multivariate_normal
    return float(multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]]).cdf([x, y]))


def build_game_pairs(g):
    """Binary leg outcomes from the closing numbers."""
    cover_home = ((g.home_margin + g.home_line) > 0).astype(float)
    over = ((g.total - g.total_line) > 0).astype(float)
    home_ml = (g.home_margin > 0).astype(float)
    away_ml = (g.home_margin < 0).astype(float)
    cover_home[g.home_margin + g.home_line == 0] = np.nan
    over[g.total == g.total_line] = np.nan
    home_ml[g.home_margin == 0] = np.nan
    fav_home = g.home_line < 0
    fav_cover = np.where(fav_home, cover_home, 1 - cover_home)
    out = []
    out.append(pair("Home covers (ATS) x Over", cover_home, over, "Same game, closing numbers"))
    out.append(pair("Home wins ML x Home covers ATS", home_ml, cover_home, "Same game"))
    out.append(pair("Away wins ML x Under", away_ml, 1 - over, "Same game"))
    out.append(pair("Home wins ML x Over", home_ml, over, "Same game"))
    out.append(pair("Favourite covers ATS x Over", fav_cover, over, "Same game"))
    return [x for x in out if x]


def cross_game_independence(g, rng_seed=3):
    """Average pairwise phi between ATS outcomes of DIFFERENT games in the same week."""
    rng = np.random.default_rng(rng_seed)
    vals = []
    for (season, week), s in g.groupby(["season", "week"]):
        if len(s) < 6:
            continue
        x = np.array(((s.home_margin + s.home_line) > 0).astype(float))
        x[s.home_margin.to_numpy() + s.home_line.to_numpy() == 0] = np.nan
        for _ in range(12):
            i, j = rng.choice(len(x), 2, replace=False)
            if np.isfinite(x[i]) and np.isfinite(x[j]):
                vals.append((x[i], x[j]))
    if len(vals) < 50:
        return None
    a = np.array([v[0] for v in vals])
    b = np.array([v[1] for v in vals])
    r = phi(a, b)
    lo, hi = phi_ci(r, len(a))
    return {"pair": "ATS result of game A x ATS result of game B (same week)",
            "n": len(a), "phi": MD(r, 3), "ci_lo": MD(lo, 3), "ci_hi": MD(hi, 3),
            "p_value": MD(chi2_p(r, len(a)), 6),
            "note": "Cross-game legs are the independence assumption behind standard parlays"}


def build_prop_pairs(g):
    path = nc.DERIVED / "prop_lines.csv"
    if not path.exists():
        return []
    props = pd.read_csv(path)
    # implied team total = (total_line + spread_line)/2 -- DERIVED, not a market quote
    gm = g[["season", "week", "home_team", "away_team", "home_line", "total_line",
            "home_score", "away_score"]].copy()
    # implied team total is DERIVED arithmetic from the two market numbers:
    #   home implied = (total_line + spread_line) / 2, with home_line = -spread_line
    gm["impl_home"] = (gm["total_line"] + (-gm["home_line"])) / 2
    gm["impl_away"] = gm["total_line"] - gm["impl_home"]
    long = []
    for r in gm.itertuples():
        long.append({"season": r.season, "week": r.week, "team": r.home_team,
                     "opp": r.away_team, "impl_total": r.impl_home, "team_score": r.home_score})
        long.append({"season": r.season, "week": r.week, "team": r.away_team,
                     "opp": r.home_team, "impl_total": r.impl_away, "team_score": r.away_score})
    tl = pd.DataFrame(long)
    tl = tl[tl.impl_total.notna() & tl.team_score.notna()]
    tl["team_over"] = (tl.team_score > tl.impl_total).astype(float)
    tl.loc[tl.team_score == tl.impl_total, "team_over"] = np.nan

    p = props.merge(tl, left_on=["season", "week", "recent_team"],
                    right_on=["season", "week", "team"], how="inner")
    p["over"] = (p.actual > p.our_line).astype(float)
    p.loc[p.actual == p.our_line, "over"] = np.nan
    label = {"passing_yards": "QB passing yards over our line x team total over",
             "rushing_yards": "RB rushing yards over our line x team total over",
             "receiving_yards": "Receiver receiving yards over our line x team total over",
             "receptions": "Receiver receptions over our line x team total over"}
    out = []
    for mkt, lbl in label.items():
        s = p[p.market == mkt]
        r = pair(lbl, s.over.to_numpy(), s.team_over.to_numpy(),
                 "2023-2024 player-weeks joined to the game's implied team total")
        if r:
            out.append(r)
    # QB passing yards x his own WR1 receiving yards (same team, same game)
    qb = p[(p.market == "passing_yards")][["season", "week", "recent_team", "over"]].copy()
    wr = p[(p.market == "receiving_yards")].groupby(["season", "week", "recent_team"]).agg(
        wr_over=("over", "max"), n_wr=("over", "size")).reset_index()
    j = qb.merge(wr, on=["season", "week", "recent_team"])
    r = pair("QB passing yards over x top receiver's receiving yards over (same team)",
             j.over.to_numpy(), j.wr_over.to_numpy(),
             "Same team-game; strong positive correlation expected")
    if r:
        out.append(r)
    return out


def key_numbers(g):
    m = g.home_margin.abs().astype(int).value_counts().sort_index()
    t = g.total.dropna().astype(int).value_counts().sort_index()
    rows_m = [{"value": int(k), "count": int(v),
               "pct": MD(100 * v / m.sum(), 2)} for k, v in m.items() if k <= 20]
    rows_t = [{"value": int(k), "count": int(v),
               "pct": MD(100 * v / t.sum(), 2)} for k, v in t.items() if 30 <= k <= 60]
    push_spread = {}
    for line in [-14, -10, -7, -6.5, -3, -2.5, 0, 2.5, 3, 6.5, 7, 10, 14]:
        sel = g[g.home_line == -line]
        if len(sel) >= 30:
            push_spread[str(line)] = {"n": int(len(sel)),
                                      "push_rate": MD((sel.home_margin + sel.home_line == 0).mean(), 4)}
    return {"margins": rows_m, "totals": rows_t, "push_rates_by_line": push_spread}


def main():
    g = nc.load_games()
    g = g[(g.season >= 2006) & g.spread_line.notna() & g.total_line.notna()]
    g["spread_line"] = g.spread_line
    pairs = build_game_pairs(g)
    cross = cross_game_independence(g)
    prop_pairs = build_prop_pairs(g)

    # parlay pricing implications, using the strongest |phi| we measured
    all_pairs = [p for p in (pairs + prop_pairs + ([cross] if cross else [])) if p]
    strongest = max([p for p in all_pairs if p.get("note", "") != "Cross-game legs"],
                    key=lambda p: abs(p["phi"]))
    pricing = []
    for rho in [-0.30, -0.15, 0.0, 0.15, 0.30, 0.55]:
        for p1 in [0.5, 0.55]:
            p2 = p1
            joint = copula_joint(p1, p2, rho)
            fair_dec = 1 / joint if joint > 0 else None
            pricing.append({
                "rho": rho, "leg_prob": p1,
                "independence_prob": MD(p1 * p2), "copula_prob": MD(joint),
                "prob_error_pct": MD((joint / (p1 * p2) - 1) * 100, 2),
                "fair_decimal": MD(fair_dec, 3) if fair_dec else None,
                "fair_american": int(round((fair_dec - 1) * 100)) if fair_dec and fair_dec >= 2
                else (int(round(-100 / (fair_dec - 1))) if fair_dec else None),
            })

    payload = {
        "method": ("Pearson phi between binary leg outcomes. Pushes are dropped because a push "
                   "settles the leg at 0 profit and is not a Bernoulli trial. 95% CI from the "
                   "Fisher z transform; p-value from n*phi^2 ~ chi-square(1)."),
        "n_games": int(len(g)),
        "game_pairs": pairs,
        "cross_game": cross,
        "prop_pairs": prop_pairs,
        "strongest_pair": strongest,
        "pricing_table": pricing,
        "key_numbers": key_numbers(g),
        "significance_threshold": "|phi| > 0.054 is significant at p<0.05 for n=3400",
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    for p in pairs + prop_pairs + ([cross] if cross else []):
        print(f"{p['pair'][:62]:62s} n={p['n']:5d} phi={p['phi']:+.3f} "
              f"[{p['ci_lo']:+.3f},{p['ci_hi']:+.3f}] p={p['p_value']:.2g} lift={p.get('lift_pct')}")


if __name__ == "__main__":
    main()
