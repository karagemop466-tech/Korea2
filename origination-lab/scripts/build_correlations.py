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
    """Gaussian copula joint probability with normal marginals.

    ``rho`` is the LATENT normal correlation, not the observed binary phi
    coefficient. For equal 50% legs the two are related by
    phi = 2*asin(rho)/pi (see rho_from_phi); for unequal marginals the latent
    value must be calibrated numerically (rho_calibrated).
    """
    if rho == 0:
        return p1 * p2
    x = norm.ppf(min(max(p1, 1e-9), 1 - 1e-9))
    y = norm.ppf(min(max(p2, 1e-9), 1 - 1e-9))
    from scipy.stats import multivariate_normal
    return float(multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]]).cdf([x, y]))


def rho_from_phi(phi_val: float) -> float:
    """Exact at equal 50% marginals: phi = 2*asin(rho)/pi  =>  rho = sin(pi*phi/2)."""
    return float(math.sin(math.pi * float(phi_val) / 2))


def rho_for_joint(p1: float, p2: float, joint: float) -> float:
    """Latent rho that reproduces an OBSERVED joint probability (issue #32.4).

    copula_joint is strictly increasing in rho, so bisection is exact enough to
    1e-6. Used to translate a measured P(A and B) into the latent parameter the
    published pricing table consumes.
    """
    if not (0 < p1 < 1 and 0 < p2 < 1) or not (0 <= joint <= min(p1, p2)):
        return float("nan")
    lo, hi = -0.999, 0.999
    for _ in range(80):
        mid = (lo + hi) / 2
        if copula_joint(p1, p2, mid) < joint:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2)


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


def cross_game_independence(g, n_boot=2000, rng_seed=3):
    """Within-week pairwise association between ATS outcomes of DIFFERENT games.

    Issue #32.3 fix: every distinct pair inside a week is used (the old version
    drew 12 random pairs per week, reusing games), and the interval comes from a
    WEEK-CLUSTERED bootstrap that resamples whole weeks. The old Fisher interval
    treated all pairs as independent observations, which they are not; a
    near-zero result is consistent with, but does not establish, joint
    independence of a multi-leg ticket.
    """
    rng = np.random.default_rng(rng_seed)
    weeks = []
    for (season, week), s in g.groupby(["season", "week"]):
        margin = s.home_margin.to_numpy() + s.home_line.to_numpy()
        x = (margin > 0).astype(float)
        x[margin == 0] = np.nan
        if int(np.isfinite(x).sum()) < 6:
            continue
        idx = np.where(np.isfinite(x))[0]
        if len(idx) < 6:
            continue
        pa, pb = [], []
        for ii in range(len(idx)):
            for jj in range(ii + 1, len(idx)):
                pa.append(x[idx[ii]])
                pb.append(x[idx[jj]])
        if pa:
            weeks.append((np.array(pa), np.array(pb)))
    if not weeks:
        return None
    a = np.concatenate([w[0] for w in weeks])
    b = np.concatenate([w[1] for w in weeks])
    r = phi(a, b)
    boots = []
    nw = len(weeks)
    for _ in range(n_boot):
        pick = rng.integers(0, nw, nw)
        aa = np.concatenate([weeks[i][0] for i in pick])
        bb = np.concatenate([weeks[i][1] for i in pick])
        boots.append(phi(aa, bb))
    boots = np.array([v for v in boots if np.isfinite(v)])
    lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if len(boots) else (float("nan"), float("nan"))
    boot_p = float(2 * min((boots <= 0).mean(), (boots >= 0).mean())) if len(boots) else float("nan")
    return {"pair": "ATS result of game A x ATS result of game B (same week)",
            "n": int(len(a)), "n_weeks": int(nw),
            "phi": MD(r, 3), "ci_lo": MD(lo, 3), "ci_hi": MD(hi, 3),
            "ci_method": f"week-clustered bootstrap, {n_boot} week resamples",
            "p_value": MD(min(1.0, boot_p), 4),
            "note": ("Within-week pairwise association. Near zero is consistent with, but "
                     "does not establish, joint independence of a multi-leg ticket: pairwise "
                     "independence does not imply joint independence. The interval resamples "
                     "whole weeks, so it does not treat pairs from one week as independent.")}



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
    # QB passing yards x at least one receiver on the team going over the line.
    # Issue #32.2 fix: the aggregation is max() over the team's receivers, i.e. an
    # "at least one receiver went over" event. It is NOT the over of a receiver
    # identified before kickoff, so the label now says what the calculation is.
    qb = p[(p.market == "passing_yards")][["season", "week", "recent_team", "over"]].copy()
    wr = p[(p.market == "receiving_yards")].groupby(["season", "week", "recent_team"]).agg(
        wr_over=("over", "max"), n_wr=("over", "size")).reset_index()
    j = qb.merge(wr, on=["season", "week", "recent_team"])
    r = pair("QB passing yards over x at least one receiver on the team over (same team-game)",
             j.over.to_numpy(), j.wr_over.to_numpy(),
             "Any-receiver event: max() over the team's receiver legs, NOT a pregame-identified "
             "top receiver. Label and calculation now agree; no pregame selection is implied.")
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
    # Issue #32.1 fix: home_line == line, published under str(line). The key now
    # carries the same sign as the selection (home_line < 0 = home favourite), so
    # a favourite line shows favourite-line push rates and an underdog line shows
    # underdog-line push rates.
    for line in [-14, -10, -7, -6.5, -3, -2.5, 0, 2.5, 3, 6.5, 7, 10, 14]:
        sel = g[g.home_line == line]
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
    strongest = max([p for p in all_pairs if p is not cross and "same week" not in p["pair"]],
                    key=lambda p: abs(p["phi"]))
    # Issue #32.4: translate every measured joint probability into the LATENT
    # normal correlation the copula pricing table needs, so the table is never
    # mistaken for an arithmetic consequence of the binary phi.
    copula_calibration = []
    for p_ in all_pairs:
        if p_ is cross or p_.get("phi") is None or not p_.get("p_both_actual"):
            continue
        pa, pb = p_["p_a"], p_["p_b"]
        rho = rho_for_joint(pa, pb, p_["p_both_actual"])
        copula_calibration.append({
            "pair": p_["pair"], "n": p_["n"], "phi": p_["phi"],
            "p_a": MD(pa), "p_b": MD(pb),
            "p_both_independent": MD(pa * pb), "p_both_actual": p_["p_both_actual"],
            "latent_rho_calibrated": MD(rho, 4),
            "copula_joint_at_calibrated_rho": MD(copula_joint(pa, pb, rho), 4) if np.isfinite(rho) else None,
        })
    pricing = []
    for rho in [-0.30, -0.15, 0.0, 0.15, 0.30, 0.55]:
        # each row is a hypothetical LATENT-correlation scenario, not a measured phi
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
        "pricing_table_kind": ("Hypothetical latent-rho scenarios for equal legs. rho is a latent "
                               "Gaussian correlation, NOT the observed binary phi; use "
                               "copula_calibration to price a measured pair."),
        "copula_calibration": copula_calibration,
        "copula_phi_identity": ("For equal 50% legs the Gaussian copula gives "
                                "phi = 2*asin(rho)/pi, so a measured phi of 0.55 maps to latent "
                                "rho = sin(pi*0.55/2) = 0.7604 and a joint probability of 0.3875, "
                                "not 0.3427 (which is copula_joint(0.5, 0.5, 0.55))."),
        "key_numbers": key_numbers(g),
        "significance_threshold": "|phi| > 0.054 is significant at p<0.05 for n=3400",
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    for p in pairs + prop_pairs + ([cross] if cross else []):
        print(f"{p['pair'][:62]:62s} n={p['n']:5d} phi={p['phi']:+.3f} "
              f"[{p['ci_lo']:+.3f},{p['ci_hi']:+.3f}] p={p['p_value']:.2g} lift={p.get('lift_pct')}")


if __name__ == "__main__":
    main()
