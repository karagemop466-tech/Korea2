"""Correlation engine.

Three separate questions, three separate answers:

1. Market correlations - do cover outcomes and over/under outcomes move together?
   (This is what makes a same-game parlay more or less valuable than the product of
   its legs.)
2. Strategy correlations - do two strategies make the same bet in different clothes?
   (Portfolio risk; also a guard against a leaderboard padded with clones.)
3. Leg correlations inside our own parlays - measured on realised leg outcomes.

Prop-level (player) correlations live in props.json and are computed in props.py.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from lib.common import INTERIM, write_json

BOOT = 2000


def phi(a: np.ndarray, b: np.ndarray) -> tuple[float, list[float]]:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = ~np.isnan(a) & ~np.isnan(b)
    a, b = a[ok], b[ok]
    if len(a) < 50:
        return float("nan"), [float("nan")] * 2
    r = float(np.corrcoef(a, b)[0, 1])
    rng = np.random.default_rng(41)
    vals = [np.corrcoef(a[i], b[i])[0, 1]
            for i in (rng.integers(0, len(a), len(a)) for _ in range(BOOT))]
    return r, [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))]


def market_correlations(g: pd.DataFrame) -> dict:
    d = g[g["played"] & g["spread_line"].notna() & g["total_line"].notna()].copy()
    d["cover"] = np.where(d["margin"] == d["spread_line"], np.nan, (d["margin"] > d["spread_line"]).astype(float))
    d["over"] = np.where(d["points_total"] == d["total_line"], np.nan, (d["points_total"] > d["total_line"]).astype(float))
    d["margin_resid"] = d["margin"] - d["spread_line"]
    d["total_resid"] = d["points_total"] - d["total_line"]

    overall = {}
    r, ci = phi(d["margin_resid"], d["total_resid"])
    overall["corr_margin_resid_total_resid"] = {"r": r, "ci95": ci, "n": int(len(d))}
    r, ci = phi(d["cover"], d["over"])
    overall["corr_cover_over"] = {"r": r, "ci95": ci, "n": int((~d["cover"].isna() & ~d["over"].isna()).sum())}
    sub = d.dropna(subset=["cover", "over"])
    p_cover = float(sub["cover"].mean())
    p_over = float(sub["over"].mean())
    p_both = float(((sub["cover"] == 1) & (sub["over"] == 1)).mean())
    overall["joint_table"] = {
        "p_home_cover": p_cover, "p_over": p_over,
        "p_home_cover_and_over_empirical": p_both,
        "p_home_cover_and_over_independent": p_cover * p_over,
        "pct_error": 100 * (p_both - p_cover * p_over) / (p_cover * p_over),
        "p_home_cover_and_under_empirical": float(((sub["cover"] == 1) & (sub["over"] == 0)).mean()),
        "p_away_cover_and_over_empirical": float(((sub["cover"] == 0) & (sub["over"] == 1)).mean()),
        "p_away_cover_and_under_empirical": float(((sub["cover"] == 0) & (sub["over"] == 0)).mean()),
        "n": int(len(sub)),
    }

    # by era
    by_era = []
    for label, lo, hi in (("1999-2009", 1999, 2009), ("2010-2017", 2010, 2017),
                          ("2018-2026", 2018, 2026), ("2015-2026 (evaluation)", 2015, 2026)):
        s = d[(d["season"] >= lo) & (d["season"] <= hi)]
        r, ci = phi(s["margin_resid"], s["total_resid"])
        rr, cci = phi(s["cover"], s["over"])
        by_era.append({"window": label, "n": int(len(s)),
                       "corr_margin_resid_total_resid": r,
                       "corr_cover_over": rr, "ci95": cci})

    # by total size (game script matters more in low totals)
    buckets = []
    for label, lo, hi in (("total <= 40", 0, 40), ("40 < total <= 47", 40, 47),
                          ("47 < total <= 52", 47, 52), ("total > 52", 52, 100)):
        s = d[(d["total_line"] > lo) & (d["total_line"] <= hi)]
        r, ci = phi(s["cover"], s["over"])
        buckets.append({"bucket": label, "n": int(len(s)), "corr_cover_over": r, "ci95": ci})

    # SGP pricing consequence at a standard -110/-110 book
    pj = overall["joint_table"]
    def american_from_prob(p):
        return round(-100 * p / (1 - p)) if p > 0.5 else round(100 * (1 - p) / p)
    sgp = []
    for name, p_emp in (("home cover + over", pj["p_home_cover_and_over_empirical"]),
                        ("home cover + under", pj["p_home_cover_and_under_empirical"]),
                        ("away cover + over", pj["p_away_cover_and_over_empirical"]),
                        ("away cover + under", pj["p_away_cover_and_under_empirical"])):
        p_ind = 0.25
        sgp.append({"combo": name, "p_empirical": p_emp, "p_independent": p_ind,
                    "fair_odds_empirical": american_from_prob(p_emp),
                    "fair_odds_independent": american_from_prob(p_ind),
                    "independent_price_error_pct": 100 * (p_ind - p_emp) / p_emp})
    return {"overall": overall, "by_era": by_era, "by_total_bucket": buckets,
            "sgp_price_effect": sgp}


def strategy_correlations(bets: pd.DataFrame, max_strategies: int = 14) -> dict:
    d = bets[bets["window"] == "eval"].copy()
    counts = d.groupby("strategy").size().sort_values(ascending=False)
    keep = list(counts.head(max_strategies).index)
    weekly = (d[d["strategy"].isin(keep)]
              .groupby(["season", "week", "strategy"])["pnl"].sum().unstack("strategy").fillna(0.0))
    corr = weekly.corr().round(3)
    pairs = []
    for a, b in itertools.combinations(keep, 2):
        if a in corr.index and b in corr.columns:
            pairs.append({"a": a, "b": b, "corr": float(corr.loc[a, b])})
    pairs.sort(key=lambda x: -abs(x["corr"]))

    # Equal-weight portfolio of the real strategies only. The controls are excluded on purpose:
    # CTRL_LEAK is a deliberate lookahead leak (+94% on 3,054 tickets) and including it would make
    # the portfolio look profitable for a reason that has nothing to do with skill.
    real = d[~d["strategy"].str.startswith("CTRL_")]
    port = real.groupby(["season", "week"])["pnl"].sum()
    n_tickets = int(len(real))
    port_roi = float(port.sum() / max(1, n_tickets))
    with_controls = d.groupby(["season", "week"])["pnl"].sum()
    return {"strategies": keep, "matrix": corr.to_dict(),
            "top_pairs": pairs[:15],
            "mean_pairwise_corr": float(np.mean([abs(p["corr"]) for p in pairs])) if pairs else None,
            "portfolio": {"n_weeks": int(len(port)), "units": float(port.sum()),
                          "roi_per_ticket": port_roi, "n_tickets": n_tickets,
                          "units_including_controls": float(with_controls.sum()),
                          "n_weeks_including_controls": int(len(with_controls))}}


def parlay_leg_correlations(bets: pd.DataFrame) -> dict:
    out = {}
    sgp = bets[(bets["strategy"] == "PARLAY_SGP_ATS_TOT") & (bets["window"] == "eval")]
    if len(sgp):
        win = (sgp["result"] == "win").astype(float)
        exp_ind = float(sgp["fair_prob"].mean())
        out["sgp"] = {"n": int(len(sgp)), "win_rate": float(win.mean()),
                      "independent_implied": exp_ind,
                      "gap_pp": 100 * (float(win.mean()) - exp_ind)}
    for name in ("PARLAY2_ATS", "PARLAY3_ATS", "PARLAY2_ML_DOG"):
        p = bets[(bets["strategy"] == name) & (bets["window"] == "eval")]
        if len(p):
            out[name] = {"n": int(len(p)), "win_rate": float((p["result"] == "win").mean()),
                         "independent_implied": float(p["fair_prob"].mean())}
    return out


def main() -> None:
    g = pd.read_parquet(INTERIM / "lines.parquet")
    bets = pd.read_parquet(INTERIM / "bets.parquet")
    mk = market_correlations(g)
    sc = strategy_correlations(bets)
    pl = parlay_leg_correlations(bets)
    write_json("correlation.json", {
        "generated": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "market": mk, "strategy": sc, "parlay_legs": pl,
    })
    print("market correlations:")
    print(f"  margin resid vs total resid r={mk['overall']['corr_margin_resid_total_resid']['r']:+.4f}")
    print(f"  cover vs over             r={mk['overall']['corr_cover_over']['r']:+.4f}")
    for row in mk["by_total_bucket"]:
        print(f"  {row['bucket']:<16} cover/over r={row['corr_cover_over']:+.4f} n={row['n']:,}")
    print("\nSGP price effect:")
    for row in mk["sgp_price_effect"]:
        print(f"  {row['combo']:<20} p_emp={row['p_empirical']:.4f} p_ind=0.25 "
              f"fair_emp={row['fair_odds_empirical']:+d} fair_ind=+300 err={row['independent_price_error_pct']:+.1f}%")
    print(f"\nstrategy mean |pairwise corr| = {sc['mean_pairwise_corr']:.3f}")
    print("top strategy pairs:", [(p['a'], p['b'], round(p['corr'],3)) for p in sc['top_pairs'][:5]])
    print("parlay legs:", pl)


if __name__ == "__main__":
    main()
