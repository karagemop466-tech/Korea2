"""Market baseline: how efficient is the closing NFL line, and what does a
random bet earn? Everything here is measured against the closing price that is
actually stored in the data.

Price policy (issue #19): rows whose price for the bet being measured is
missing are EXCLUDED from that measurement, never imputed at -110, and the
number excluded is disclosed next to the result. Point-level statistics that
need no price (calibration, line bias) keep every settled row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (DERIVED, jdump, load_games, implied_prob, bet_return,
                    summarise_returns, t_stat, p_from_t, bh_fdr, american_to_decimal)

ERA = {"1999-2009", "2010-2019", "2020-2026"}


def era(season: int) -> str:
    if season <= 2009:
        return "1999-2009"
    if season <= 2019:
        return "2010-2019"
    return "2020-2026"


def prep() -> pd.DataFrame:
    g = load_games()
    num = ["result", "total", "spread_line", "total_line", "home_spread_odds",
           "away_spread_odds", "over_odds", "under_odds", "home_moneyline",
           "away_moneyline", "home_score", "away_score", "home_rest", "away_rest",
           "temp", "wind"]
    for c in num:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g.game_type == "REG") & g.result.notna()].copy()
    g["settled"] = True
    # VERIFIED convention (see results/market.json -> convention_check):
    # spread_line is from the HOME team's perspective and is POSITIVE when the
    # home team is the favourite. Home covers when result - spread_line > 0.
    g["home_margin_cover"] = g.result - g.spread_line          # >0 home covered
    g["away_margin_cover"] = -g.result + g.spread_line
    g["over_margin"] = g.total - g.total_line
    g["era"] = g.season.map(era)
    # Issue #19 fix: NO imputation. Prices stay NaN when the feed has none and
    # every price-based measurement below excludes those rows and says how many.
    g["home_odds"] = g.home_spread_odds
    g["away_odds"] = g.away_spread_odds
    g["over_price"] = g.over_odds
    g["under_price"] = g.under_odds
    g["home_is_dog"] = g.spread_line < 0
    g["home_is_fav"] = g.spread_line > 0
    g["spread_abs"] = g.spread_line.abs()
    return g


def side_series(df: pd.DataFrame, side: str):
    """Return (win, push, odds, n_excluded) for a bet on `side`.

    Rows with no stored price for that side, or no decidable margin, are
    excluded rather than settled at an assumed price.
    """
    if side == "home":
        m, odds = df.home_margin_cover, df.home_odds
    else:
        m, odds = df.away_margin_cover, df.away_odds
    ok = m.notna() & odds.notna()
    m, odds = m[ok], odds[ok]
    return (m > 0).to_numpy(), (m == 0).to_numpy(), odds.to_numpy(), int((~ok).sum())


def total_side(df: pd.DataFrame, side: str):
    if side == "over":
        m, odds = df.over_margin, df.over_price
    else:
        m, odds = -df.over_margin, df.under_price
    ok = m.notna() & odds.notna()
    m, odds = m[ok], odds[ok]
    return (m > 0).to_numpy(), (m == 0).to_numpy(), odds.to_numpy(), int((~ok).sum())


def ols_slope(x: pd.Series, y: pd.Series) -> dict:
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 30:
        return {}
    X, Y = d.iloc[:, 0].to_numpy(float), d.iloc[:, 1].to_numpy(float)
    b, a = np.polyfit(X, Y, 1)
    pred = a + b * X
    ss_res = float(((Y - pred) ** 2).sum())
    ss_tot = float(((Y - Y.mean()) ** 2).sum())
    resid = Y - pred
    se_b = float(np.sqrt(resid.var(ddof=2) / ((X - X.mean()) ** 2).sum()))
    return {
        "n": int(len(d)), "slope": float(b), "intercept": float(a),
        "r2": 1 - ss_res / ss_tot, "rmse": float(np.sqrt(ss_res / len(d))),
        "slope_se": se_b,
        "slope_t": float((b - 1.0) / se_b) if se_b else None,   # test slope = 1 (unbiased)
        "corr": float(np.corrcoef(X, Y)[0, 1]),
    }


def main():
    out: dict = {}
    g = prep()

    # ---- 1. sign-convention proof (so the site can show the check) -----------
    conv = g.dropna(subset=["spread_line"])
    ml = conv.dropna(subset=["home_moneyline"])
    out["convention_check"] = {
        "corr_spreadline_vs_home_margin": float(conv.spread_line.corr(conv.result)),
        "mean_home_margin_when_spread_ge_3": float(conv[conv.spread_line >= 3].result.mean()),
        "n_spread_ge_3": int((conv.spread_line >= 3).sum()),
        "mean_home_margin_when_spread_le_minus3": float(conv[conv.spread_line <= -3].result.mean()),
        "n_spread_le_minus3": int((conv.spread_line <= -3).sum()),
        "share_home_ml_negative_when_spread_gt_2": float((ml[ml.spread_line > 2].home_moneyline < 0).mean()),
        "n_ml_check_pos": int((ml.spread_line > 2).sum()),
        "share_home_ml_negative_when_spread_lt_minus2": float((ml[ml.spread_line < -2].home_moneyline < 0).mean()),
        "n_ml_check_neg": int((ml.spread_line < -2).sum()),
        "note": ("Verified empirically and against the same file's moneylines: "
                 "spread_line is positive when the HOME team is the favourite. "
                 "The home team covers when result - spread_line > 0. The commonly "
                 "quoted 'negative means home favourite' reading of this field is "
                 "wrong for this dataset and is flagged on the review page."),
    }

    # ---- 2. calibration: does the closing line predict the result? ----------
    out["calibration"] = {}
    for key, sub in [("all", g)] + [(e, g[g.era == e]) for e in sorted(set(g.era))]:
        out["calibration"][f"spread_{key}"] = ols_slope(sub.spread_line, sub.result)
        out["calibration"][f"total_{key}"] = ols_slope(sub.total_line, sub.total)

    # ---- 2b. is the closing line unbiased? ---------------------------------
    # mean(result - spread_line) is the average points the home team beat (+) or
    # missed (-) its own closing line by. Zero means an unbiased line.
    err = (g.result - g.spread_line)
    n = int(err.notna().sum())
    bias = summarise_returns(err.to_numpy(), "home line error")
    out["line_bias"] = {
        "mean_points": float(err.mean()), "n": n,
        "t": t_stat(err.to_numpy()), "p": p_from_t(t_stat(err.to_numpy()), n),
        "ci_lo": bias.get("ci_lo"), "ci_hi": bias.get("ci_hi"),
        "interpretation": ("negative = the home team beat its closing line less often "
                           "than the line implied; i.e. the closing line sits high on "
                           "home teams in this file."),
        "by_era": {e: {"n": int(len(s_)), "mean_points": float((s_.result - s_.spread_line).mean())}
                   for e, s_ in g.groupby("era")},
    }
    tot_err = (g.total - g.total_line)
    out["line_bias"]["spread_median_points"] = float(err.median())
    out["line_bias"]["total_mean_points"] = float(tot_err.mean())
    out["line_bias"]["total_median_points"] = float(tot_err.median())
    out["line_bias"]["total_t"] = t_stat(tot_err.to_numpy())
    out["line_bias"]["total_p"] = p_from_t(t_stat(tot_err.to_numpy()), int(tot_err.notna().sum()))
    out["line_bias"]["over_hit_rate"] = float((g.over_margin > 0).mean())
    out["line_bias"]["over_hit_rate_nonpush"] = float(
        (g.over_margin > 0).sum() / max(1, int((g.over_margin != 0).sum())))
    out["line_bias"]["total_note"] = (
        "Totals are right-skewed: the average total beats the number by ~0.7 points "
        "but the over still cashes less than half the time, so the mean is not "
        "evidence of a soft total. Only the hit rate is actionable.")

    # ---- 3. what a blind bet earns (the vig wall) --------------------------
    blind = {}
    for side in ["home", "away"]:
        w, p, o, nx = side_series(g, side)
        blind[side] = summarise_returns(bet_return(w, p, o), f"blind {side}")
        blind[side]["win_rate"] = float(w.mean())
        blind[side]["push_rate"] = float(p.mean())
        blind[side]["n_excluded_missing_price"] = nx
    for side in ["over", "under"]:
        w, p, o, nx = total_side(g, side)
        blind[side] = summarise_returns(bet_return(w, p, o), f"blind {side}")
        blind[side]["win_rate"] = float(w.mean())
        blind[side]["push_rate"] = float(p.mean())
        blind[side]["n_excluded_missing_price"] = nx
    out["blind"] = blind

    # ---- 4. implied overround (is the price really -110?) -------------------
    d = g.dropna(subset=["home_spread_odds", "away_spread_odds"])
    over = (implied_prob(d.home_spread_odds) + implied_prob(d.away_spread_odds) - 1)
    dt_ = g.dropna(subset=["over_odds", "under_odds"])
    over_t = (implied_prob(dt_.over_odds) + implied_prob(dt_.under_odds) - 1)
    out["overround"] = {
        "spread_n": int(len(d)), "spread_mean": float(over.mean()),
        "total_n": int(len(dt_)), "total_mean": float(over_t.mean()),
    }

    # ---- 5. home field advantage over time ---------------------------------
    hfa = g.groupby("season").agg(n=("result", "size"), mean_margin=("result", "mean")).reset_index()
    hfa["mean_margin"] = hfa.mean_margin.round(2)
    out["hfa"] = {
        "by_season": hfa.to_dict("records"),
        "all": {"n": int(len(g)), "mean": float(g.result.mean())},
    }
    out["hfa"]["era"] = ({
        e: {"n": int(len(g[g.era == e])), "mean": float(g[g.era == e].result.mean())}
        for e in sorted(set(g.era))
    })

    # ---- 6. pre-registered bias tests (things the public believes) ---------
    tests = {}

    def add(name, desc, mask, side, kind="ats"):
        sub = g[mask]
        if len(sub) < 60:
            return
        if kind == "ats":
            w, p, o, nx = side_series(sub, side)
        else:
            w, p, o, nx = total_side(sub, side)
        if len(w) < 60:
            return
        ret = bet_return(w, p, o)
        s = summarise_returns(ret, name)
        s.update({"desc": desc, "market": kind, "side": side, "n": int(len(w)),
                  "n_selected": int(len(sub)), "n_excluded_missing_price": nx,
                  "hit_rate": float(w.mean()), "push_rate": float(p.mean()),
                  "avg_price": float(np.nanmean(o))})
        tests[name] = s

    # Sign convention (proven in convention_check): spread_line > 0 means the
    # HOME team is the favourite, so the ROAD favourite is spread_line < 0.
    # Issue #19 fix: the away_fav masks previously selected positive spreads,
    # which are road underdogs, not road favourites.
    add("home_dog", "Bet the home team whenever it is an underdog", g.home_is_dog, "home")
    add("home_big_dog", "Bet home underdogs of a touchdown or more", g.spread_line <= -7, "home")
    add("away_fav", "Bet the road favourite", g.spread_line < 0, "away")
    add("away_fav_7", "Bet road favourites laying 7+", g.spread_line <= -7, "away")
    add("div_dog", "Bet the home underdog in divisional games", (g.div_game == 1) & g.home_is_dog, "home")
    add("rest_advantage", "Bet the team with 3+ extra rest days",
        (g.home_rest - g.away_rest) >= 3, "home")
    add("rest_disadvantage", "Bet the team with 3+ fewer rest days",
        (g.away_rest - g.home_rest) >= 3, "home")
    add("tnf_home", "Bet the home team on Thursday", g.weekday == "Thursday", "home")
    add("wind15_under", "Bet under when wind >= 15 mph", g.wind >= 15, "under", "total")
    add("dome_over", "Bet over in domes", g.roof.isin(["dome", "closed"]), "over", "total")
    add("div_under", "Bet under in divisional games", g.div_game == 1, "under", "total")
    add("cold_under", "Bet under when temperature <= 32F", g.temp <= 32, "under", "total")

    pv = [t["p"] if t.get("p") is not None else 1.0 for t in tests.values()]
    keep = bh_fdr(pv, q=0.10)
    for (k, t), k_ in zip(tests.items(), keep):
        t["fdr_q10_pass"] = bool(k_)
    out["bias_tests"] = tests
    out["fdr"] = {"method": "Benjamini-Hochberg", "q": 0.10, "n_tests": len(tests),
                  "n_pass": int(sum(keep))}

    # ---- 7. line accuracy by era (for the site table) ----------------------
    out["by_era"] = {}
    for e in sorted(set(g.era)):
        sub = g[g.era == e]
        if not len(sub):
            continue
        fav_home = sub.spread_line > 0
        fav_won = np.where(fav_home, sub.result > 0, sub.result < 0)
        ties = sub.result == 0
        out["by_era"][e] = {
            "n": int(len(sub)),
            "favourite_win_rate": float(fav_won[~ties.to_numpy()].mean()),
            "tie_rate": float(ties.mean()),
            "mean_total": float(sub.total.mean()),
            "mean_abs_spread": float(sub.spread_abs.mean()),
        }

    # ---- 8. current season snapshot ---------------------------------------
    cur = g[g.season == 2026]
    out["season_2026"] = {
        "games_with_result": int(len(cur)),
        "through_week": int(cur.week.max()),
        "last_gameday": str(cur[cur.result.notna()].gameday.max()),
        "ats_home_covers": int((cur.home_margin_cover > 0).sum()),
        "ats_home_nonpush": int((cur.home_margin_cover != 0).sum()),
        "overs": int((cur.over_margin > 0).sum()),
        "total_nonpush": int((cur.over_margin != 0).sum()),
    }
    jdump(out, DERIVED.parents[1] / "results" / "market.json")
    print("market.json written")
    for k, v in out["calibration"].items():
        if v:
            print(f"  {k:16s} n={v['n']:5d} slope={v['slope']:.3f} r2={v['r2']:.3f} rmse={v['rmse']:.2f}")
    print("  blind home ROI", round(blind["home"]["roi"], 4), "n", blind["home"]["n"])
    print("  blind over ROI", round(blind["over"]["roi"], 4))
    print("  overround spread", round(out["overround"]["spread_mean"], 4))


if __name__ == "__main__":
    main()
