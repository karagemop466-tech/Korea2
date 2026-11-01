"""Strategy engine.

Every strategy is defined once, on information that is available before kickoff,
and then settled against the closing price stored in the data. Strategies are
evaluated walk-forward per season and pushed through the validation gates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (RESULTS, bet_return, implied_prob, american_to_decimal, jdump,
                    load_games, load_team_week, summarise_returns, t_stat, p_from_t,
                    bh_fdr, permutation_p, required_n, bootstrap_ci)

FIRST_EVAL_SEASON = 2018          # first season with an out-of-sample model forecast
TRAIN_MIN_SEASON = 2015
HOLDOUT_SEASONS = [2025, 2026]    # touched exactly once, at the end


# ---------------------------------------------------------------------------
# team ratings, point-in-time
# ---------------------------------------------------------------------------
def build_ratings(tw: pd.DataFrame) -> pd.DataFrame:
    """Offensive / defensive EPA per play per team-week, using only prior weeks."""
    tw = tw[tw.season_type == "REG"].copy()
    tw["plays"] = tw.attempts.fillna(0) + tw.carries.fillna(0) + tw.sacks_suffered.fillna(0)
    tw["epa"] = tw.passing_epa.fillna(0) + tw.rushing_epa.fillna(0)
    tw = tw[tw.plays >= 20]
    tw["off_epa_pp"] = tw.epa / tw.plays

    off = tw[["season", "week", "team", "game_id", "opponent_team", "off_epa_pp"]].copy()
    # defensive rating of a team in a game = the opponent's offensive output in it
    defr = off.rename(columns={"team": "opponent_team", "opponent_team": "team",
                               "off_epa_pp": "def_epa_pp_allowed"})
    merged = off.merge(defr[["game_id", "team", "def_epa_pp_allowed"]],
                       on=["game_id", "team"], how="left")

    merged = merged.sort_values(["team", "season", "week"])
    merged["off_form"] = (merged.groupby("team", group_keys=False)["off_epa_pp"]
                          .apply(lambda s: s.shift(1).rolling(8, min_periods=3).mean()))
    merged["def_form"] = (merged.groupby("team", group_keys=False)["def_epa_pp_allowed"]
                          .apply(lambda s: s.shift(1).rolling(8, min_periods=3).mean()))
    merged["off_form_season"] = (merged.groupby(["team", "season"], group_keys=False)["off_epa_pp"]
                                 .apply(lambda s: s.shift(1).expanding().mean()))
    merged["def_form_season"] = (merged.groupby(["team", "season"], group_keys=False)["def_epa_pp_allowed"]
                                 .apply(lambda s: s.shift(1).expanding().mean()))
    cols = ["season", "week", "team", "off_form", "def_form",
            "off_form_season", "def_form_season"]
    return merged[cols]


# ---------------------------------------------------------------------------
# market frame
# ---------------------------------------------------------------------------
def build_games() -> pd.DataFrame:
    g = load_games()
    num = ["result", "total", "spread_line", "total_line", "home_spread_odds",
           "away_spread_odds", "over_odds", "under_odds", "home_rest", "away_rest",
           "temp", "wind", "home_moneyline", "away_moneyline"]
    for c in num:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g.game_type == "REG") & g.result.notna() & g.spread_line.notna()].copy()
    g["home_cover_margin"] = g.result - g.spread_line
    g["away_cover_margin"] = -g.result + g.spread_line
    g["over_margin"] = g.total - g.total_line
    g["home_odds"] = g.home_spread_odds.fillna(-110.0)
    g["away_odds"] = g.away_spread_odds.fillna(-110.0)
    g["over_price"] = g.over_odds.fillna(-110.0)
    g["under_price"] = g.under_odds.fillna(-110.0)
    return g.sort_values(["season", "week", "gameday"]).reset_index(drop=True)


def attach_features(g: pd.DataFrame) -> pd.DataFrame:
    r = build_ratings(load_team_week())
    home = r.rename(columns={"team": "home_team", "off_form": "h_off", "def_form": "h_def",
                             "off_form_season": "h_off_s", "def_form_season": "h_def_s"})
    away = r.rename(columns={"team": "away_team", "off_form": "a_off", "def_form": "a_def",
                             "off_form_season": "a_off_s", "def_form_season": "a_def_s"})
    g = g.merge(home, on=["season", "week", "home_team"], how="left")
    g = g.merge(away, on=["season", "week", "away_team"], how="left")
    g["rest_diff"] = g.home_rest - g.away_rest
    g["hfa_prior"] = 2.0
    return g


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------
def fit_forecast(train: pd.DataFrame) -> dict:
    d = train.dropna(subset=["h_off", "h_def", "a_off", "a_def"])
    if len(d) < 200:
        return {}
    X = np.column_stack([
        np.ones(len(d)),
        (d.h_off - d.a_def).to_numpy(float),
        (d.a_off - d.h_def).to_numpy(float),
        d.rest_diff.fillna(0).to_numpy(float),
        d.div_game.fillna(0).to_numpy(float),
    ])
    y = d.result.to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sigma = float(resid.std(ddof=5))
    return {"beta": beta.tolist(), "sigma": sigma, "n_train": int(len(d)),
            "r2": float(1 - resid.var() / y.var())}


def predict(df: pd.DataFrame, model: dict) -> pd.Series:
    b = model["beta"]
    X = np.column_stack([
        np.ones(len(df)),
        (df.h_off - df.a_def).to_numpy(float),
        (df.a_off - df.h_def).to_numpy(float),
        df.rest_diff.fillna(0).to_numpy(float),
        df.div_game.fillna(0).to_numpy(float),
    ])
    return pd.Series(X @ np.array(b), index=df.index)


def walk_forward(g: pd.DataFrame) -> pd.DataFrame:
    """Season-by-season refit; each season is predicted with earlier seasons only."""
    from math import erf, sqrt

    out = []
    for season in sorted(g.season.unique()):
        hist = g[(g.season < season) & (g.season >= TRAIN_MIN_SEASON)]
        cur = g[g.season == season]
        if len(hist.dropna(subset=["h_off"])) < 300 or not len(cur):
            continue
        model = fit_forecast(hist)
        if not model:
            continue
        cur = cur.copy()
        cur["model_margin"] = predict(cur, model)
        cur["model_sigma"] = model["sigma"]
        z = (cur.model_margin - cur.spread_line) / model["sigma"]
        cur["p_home_cover"] = z.apply(lambda v: 0.5 * (1 + erf(v / sqrt(2))) if pd.notna(v) else np.nan)
        cur["train_n"] = model["n_train"]
        cur["train_r2"] = model["r2"]
        out.append(cur)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ---------------------------------------------------------------------------
# strategy definitions
# ---------------------------------------------------------------------------
def settle(df: pd.DataFrame, side: str, market: str = "ats") -> dict:
    if market == "ats":
        margin = df.home_cover_margin if side == "home" else df.away_cover_margin
        odds = df.home_odds if side == "home" else df.away_odds
    else:
        margin = df.over_margin if side == "over" else -df.over_margin
        odds = df.over_price if side == "over" else df.under_price
    win = (margin > 0).to_numpy()
    push = (margin == 0).to_numpy()
    ret = bet_return(win, push, odds.to_numpy())
    return {"win": win, "push": push, "ret": ret, "odds": odds.to_numpy()}


def strategy_defs(g: pd.DataFrame) -> dict:
    """Each entry returns the subset of games the strategy bets, plus the side."""
    defs = {}

    defs["S1_away_blanket"] = {
        "name": "S1 · Blanket away",
        "family": "single",
        "thesis": "Fade the home team on the road-team cover rate gap observed in the data.",
        "kinds": [("away", "ats", g)],
    }

    defs["S2_rest_spot"] = {
        "name": "S2 · Rest-differential spot",
        "family": "single",
        "thesis": "Bet the team with at least three extra rest days.",
        "kinds": [
            ("home", "ats", g[g.rest_diff >= 3]),
            ("away", "ats", g[g.rest_diff <= -3]),
        ],
    }

    defs["S3_weather_under"] = {
        "name": "S3 · Weather under",
        "family": "single",
        "thesis": "Bet under when the recorded wind is 15 mph or more.",
        "kinds": [("under", "total", g[g.wind >= 15])],
    }

    defs["S4_div_home_dog"] = {
        "name": "S4 · Divisional home dog",
        "family": "single",
        "thesis": "Bet the home underdog inside the division.",
        "kinds": [("home", "ats", g[(g.div_game == 1) & (g.spread_line < 0)])],
    }

    defs["S5_model_edge"] = {
        "name": "S5 · Model edge vs close",
        "family": "single",
        "thesis": ("Bet the side when the walk-forward rating model disagrees with the "
                   "closing line by at least 2 points and the model probability clears "
                   "the price by 2 percentage points."),
        "kinds": [],
    }
    if "p_home_cover" in g.columns:
        d = g.dropna(subset=["p_home_cover"]).copy()
        d["edge_home"] = d.p_home_cover - implied_prob(d.home_odds)
        d["edge_away"] = (1 - d.p_home_cover) - implied_prob(d.away_odds)
        d["abs_gap"] = (d.model_margin - d.spread_line).abs()
        defs["S5_model_edge"]["kinds"] = [
            ("home", "ats", d[(d.abs_gap >= 2.0) & (d.edge_home >= 0.02)]),
            ("away", "ats", d[(d.abs_gap >= 2.0) & (d.edge_away >= 0.02)]),
        ]
    return defs


def binom_p(wins: int, losses: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial test against a fair coin (no SciPy needed)."""
    from math import comb
    n = wins + losses
    if n == 0:
        return float("nan")
    # normal approximation with continuity correction (n is large in practice)
    from math import sqrt, erf
    z = (min(wins, losses) + 0.5 - n * p0) / sqrt(n * p0 * (1 - p0))
    return float(min(1.0, 2 * 0.5 * (1 + erf(z / sqrt(2)))))


def evaluate(defn: dict, label_returns: np.ndarray) -> dict:
    parts = []
    for side, market, sub in defn["kinds"]:
        if not len(sub):
            continue
        s = settle(sub, side, market)
        parts.append({"side": side, "market": market, "n": int(len(sub)),
                      "win": s["win"], "push": s["push"], "ret": s["ret"],
                      "hit": float(s["win"].mean()),
                      "push_rate": float(s["push"].mean()),
                      "avg_price": float(np.nanmean(s["odds"]))})
    if not parts:
        return {"n": 0}
    ret = np.concatenate([p["ret"] for p in parts])
    wins = sum(p["win"].sum() for p in parts)
    pushes = sum(p["push"].sum() for p in parts)
    n = int(len(ret))
    summary = summarise_returns(ret, defn["name"])
    nonpush = int(n - pushes)
    summary.update({
        "family": defn["family"], "thesis": defn["thesis"],
        "hit_rate": float(wins / n), "push_rate": float(pushes / n),
        "hit_rate_nonpush": float(wins / max(1, nonpush)),
        "binom_p": binom_p(int(wins), int(nonpush - wins)),
        "legs": [{k: v for k, v in p.items() if k not in ("win", "push", "ret")} for p in parts],
        "perm_p": permutation_p(ret, label_returns),
        "splits": {},
    })
    periods = {"develop_2018_2022": (2018, 2022), "validate_2023_2024": (2023, 2024),
               "holdout_2025_2026": (2025, 2026), "pre_2018": (0, 2017)}
    for pname, (lo, hi) in periods.items():
        rr = []
        for side, market, sub in defn["kinds"]:
            if not len(sub):
                continue
            ss = sub[(sub.season >= lo) & (sub.season <= hi)]
            if len(ss):
                rr.append(settle(ss, side, market)["ret"])
        if rr:
            r2 = np.concatenate(rr)
            summary["splits"][pname] = {
                "n": int(len(r2)), "roi": float(r2.mean()),
                "t": t_stat(r2), "p": p_from_t(t_stat(r2), len(r2)),
            }
    return summary


def main() -> dict:
    g = attach_features(build_games())
    wf = walk_forward(g)
    g = g.merge(wf[["game_id", "model_margin", "p_home_cover", "model_sigma"]],
                on="game_id", how="left") if len(wf) else g
    if len(wf):
        r2 = wf.groupby("season").train_r2.first().to_dict()
    else:
        r2 = {}

    # universe of every settle-able game at the same prices (the luck null)
    all_ret = np.concatenate([
        settle(g, "home")["ret"], settle(g, "away")["ret"],
        settle(g, "over", "total")["ret"], settle(g, "under", "total")["ret"],
    ])

    defs = strategy_defs(g)
    results = {}
    for key, defn in defs.items():
        results[key] = evaluate(defn, all_ret)

    # ---- model discrimination vs the market ---------------------------------
    cmp = {}
    if len(wf):
        d = wf.dropna(subset=["p_home_cover"]).copy()
        if len(d):
            y = (d.home_cover_margin > 0).astype(int)
            mask = (d.home_cover_margin != 0).to_numpy()
            d, y = d[mask], y[mask]
            pm = implied_prob(d.home_odds.to_numpy())
            pm = pm / (pm + (1 - implied_prob(d.away_odds.to_numpy())))
            eps = 1e-6
            ll_model = float(-np.mean(y * np.log(np.clip(d.p_home_cover, eps, 1 - eps)) +
                                      (1 - y) * np.log(np.clip(1 - d.p_home_cover, eps, 1 - eps))))
            ll_mkt = float(-np.mean(y * np.log(np.clip(pm, eps, 1 - eps)) +
                                    (1 - y) * np.log(np.clip(1 - pm, eps, 1 - eps))))
            bs_model = float(np.mean((d.p_home_cover - y) ** 2))
            bs_mkt = float(np.mean((pm - y) ** 2))
            acc = float(((d.p_home_cover > 0.5) == y.astype(bool)).mean())
            hit = float((d.p_home_cover > pm).eq(y.astype(bool)).mean())
            cmp = {
                "n": int(len(d)),
                "logloss_model": ll_model, "logloss_market": ll_mkt,
                "brier_model": bs_model, "brier_market": bs_mkt,
                "brier_skill_vs_market": 1 - bs_model / bs_mkt,
                "market_brier_skill_vs_coinflip": 1 - bs_mkt / 0.25,
                "accuracy": acc,
                "model_vs_market_r2": float(np.corrcoef(d.model_margin, d.spread_line)[0, 1] ** 2),
                "sigma": float(d.model_sigma.iloc[0]),
                "season_r2": {int(k): float(v) for k, v in r2.items()},
            }
    # ---- parlay construction ------------------------------------------------
    parlays = build_parlays(g, results)
    # ---- gates --------------------------------------------------------------
    gates = apply_gates(results, cmp)
    jdump({"strategies": results, "model": cmp, "parlays": parlays, "gates": gates},
          RESULTS / "strategies.json")
    print("strategies.json written")
    for k, v in results.items():
        if v.get("n"):
            print(f"  {k:20s} n={v['n']:5d} hit={v['hit_rate']*100:5.1f}% roi={v['roi']*100:+6.2f}% "
                  f"t={v['t']:+5.2f} p={v['p']:.3f} perm={v.get('perm_p')}")
    if cmp:
        print("  model vs market:", {k: (round(v, 4) if isinstance(v, float) else v)
                                     for k, v in cmp.items() if k != "season_r2"})
    return {"strategies": results, "model": cmp, "parlays": parlays, "gates": gates}


def build_parlays(g: pd.DataFrame, results: dict) -> dict:
    """Compare naive independence pricing of multi-leg tickets with what happened."""
    out = {}
    if "p_home_cover" not in g.columns:
        return out
    d = g.dropna(subset=["p_home_cover", "model_margin"]).copy()
    if not len(d):
        return out
    d["gap"] = (d.model_margin - d.spread_line).abs()
    rows = []
    for (season, week), grp in d.groupby(["season", "week"]):
        if len(grp) < 3:
            continue
        top = grp.nlargest(3, "gap")
        side_home = (top.model_margin > top.spread_line).to_numpy()
        p_leg = np.where(side_home, top.p_home_cover, 1 - top.p_home_cover)
        odds = np.where(side_home, top.home_odds, top.away_odds)
        won = np.where(side_home, top.home_cover_margin > 0, top.away_cover_margin > 0)
        push = np.where(side_home, top.home_cover_margin == 0, top.away_cover_margin == 0)
        dec = american_to_decimal(odds)
        # a push leg reduces the ticket to a two-leg parlay
        n_live = int((~push).sum())
        if push.any():
            dec_live = dec[~push]
            realised_odds = float(np.prod(dec_live)) if n_live >= 2 else (float(dec_live[0]) if n_live == 1 else 1.0)
            ticket_won = bool(won[~push].all()) if n_live else True
        else:
            realised_odds = float(np.prod(dec))
            ticket_won = bool(won.all())
        rows.append({
            "season": int(season), "week": int(week),
            "naive_p": float(np.prod(p_leg)),
            "quoted_p_naive_hold": float(np.prod(dec)),
            "implied_by_naive": float(1.0 / np.prod(dec)),
            "realised_odds": realised_odds,
            "won": ticket_won,
            "mean_gap": float(top.gap.mean()),
        })
    if not rows:
        return out
    df = pd.DataFrame(rows)
    ret = np.where(df.won, df.realised_odds - 1.0, -1.0)
    out["parlay3_model"] = {
        "n_tickets": int(len(df)),
        "mean_naive_p": float(df.naive_p.mean()),
        "hit_rate": float(df.won.mean()),
        "roi": float(ret.mean()),
        "t": t_stat(ret), "p": p_from_t(t_stat(ret), len(ret)),
        "mean_mean_gap": float(df.mean_gap.mean()),
        "expected_hits_if_independent": float(df.naive_p.sum()),
        "actual_hits": int(df.won.sum()),
        "note": ("Naive pricing multiplies the three leg probabilities. The ticket count "
                 "is the number of weeks where the model had three qualifying legs."),
    }
    # how far naive parlay pricing sits from a fair book
    out["parlay_hold"] = {
        "mean_leg_implied_sum": float(df.quoted_p_naive_hold.mean()),
        "note": "sum of the three decimal prices; >1 is the theoretical margin a book earns",
    }

    # independent-game check: is week-to-week ATS noise really independent?
    if len(g) > 200:
        hm = g.home_cover_margin.dropna()
        wk = g.groupby(["season", "week"]).home_cover_margin.mean()
        out["cross_game_independence"] = {
            "n": int(len(hm)), "autocorr_lag1": float(hm.autocorr(1)),
            "week_mean_autocorr_lag1": float(wk.autocorr(1)),
        }
    return out


def apply_gates(results: dict, cmp: dict) -> dict:
    """Six explicit, pre-registered gates. A strategy is only 'ranked' if all pass."""
    gates = {}
    pvals = []
    keys = []
    for k, v in results.items():
        if v.get("n"):
            pvals.append(v.get("p") or 1.0)
            keys.append(k)
    fdr = bh_fdr(pvals, q=0.10) if pvals else []

    for i, k in enumerate(keys):
        v = results[k]
        n = v["n"]
        roi = v["roi"]
        ci_lo = v.get("ci_lo") or -1
        req = v.get("req_n") or float("inf")
        # holdout: same sign on the most recent two seasons
        g_ = []
        g_.append({"gate": "G1 Sample size", "pass": n >= 300,
                   "value": f"n = {n}", "rule": "n >= 300 settled bets"})
        g_.append({"gate": "G2 Significance", "pass": bool(v.get("p") is not None and v["p"] < 0.05),
                   "value": f"p = {v['p']:.3f}" if v.get("p") is not None else "n/a",
                   "rule": "two-sided p < 0.05"})
        g_.append({"gate": "G3 Multiple testing", "pass": bool(fdr[i]) if fdr else False,
                   "value": "survives BH-FDR" if (fdr and fdr[i]) else "fails BH-FDR",
                   "rule": "Benjamini-Hochberg q = 0.10 across all strategies"})
        g_.append({"gate": "G4 Positive after vig", "pass": bool(roi > 0 and ci_lo > 0),
                   "value": f"ROI {roi*100:+.2f}%, 95% CI low {ci_lo*100:+.2f}%",
                   "rule": "ROI > 0 and bootstrap CI excludes 0"})
        g_.append({"gate": "G5 Luck", "pass": bool(v.get("perm_p") is not None and v["perm_p"] < 0.05),
                   "value": f"permutation p = {v['perm_p']:.3f}" if v.get("perm_p") is not None else "n/a",
                   "rule": "random portfolios of the same size beat it < 5% of the time"})
        g_.append({"gate": "G6 Track-record length", "pass": bool(n >= req),
                   "value": (f"needs n >= {int(np.ceil(req)):,}" if np.isfinite(req) else "n/a"),
                   "rule": "n at least the sample needed for the observed effect to be significant"})
        passes = sum(x["pass"] for x in g_)
        gates[k] = {
            "name": v.get("label", k), "gates": g_, "passed": passes, "of": len(g_),
            "status": "RANKED" if passes == len(g_) else "NOT RANKED",
        }
    ranked = [k for k, v in gates.items() if v["status"] == "RANKED"]
    return {"by_strategy": gates, "ranked": ranked,
            "fdr": {"q": 0.10, "n_tests": len(keys), "n_pass": int(sum(fdr)) if fdr else 0}}


if __name__ == "__main__":
    main()
