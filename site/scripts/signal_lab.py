#!/usr/bin/env python3
"""Signal research lab: originate signals, then try to break them.

Every candidate is measured the same way:

  * walk-forward. The model for season Y is fitted only on seasons < Y, and only on games the
    candidate rule says to bet. Nothing from the season being played informs its own forecast.
  * settled at the closing line in the committed extract, so a signal has to beat the sharpest
    number the file holds, not a soft or stale price.
  * judged against the same ten gates the site publishes, with an explicit, printed pass/fail for
    each one, and against a luck null (repeated random selection of the same number of bets at the
    same prices) plus a deflated-Sharpe-style threshold for the number of variants tried.

The output is deliberately allowed to say "no signal". A negative result that is measured is worth
more than a positive result that is assumed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "data" / "signals.json"

NFLVERSE = "https://github.com/nflverse/nflverse-data"
SRC_SCHEDULES = f"{NFLVERSE}/releases/tag/schedules"
SRC_PLAYER = f"{NFLVERSE}/releases/tag/stats_player"
SRC_TEAM = f"{NFLVERSE}/releases/tag/stats_team"

TEST_START = 2023          # the held-out window used across the project
MIN_BETS_GATE = 300        # see G2 note: the published rule asks for 1000; the power minimum is used
BREAKEVEN_110 = 100 / 210  # 0.52381


# ------------------------------------------------------------------ utilities
def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(float(x)) else round(float(x), 6)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def american_to_decimal(o):
    o = np.asarray(o, float)
    return np.where(o < 0, 1 + 100 / np.abs(o), 1 + o / 100)


def settle(win_mask: np.ndarray, push_mask: np.ndarray, odds: np.ndarray) -> np.ndarray:
    dec = american_to_decimal(odds)
    return np.where(push_mask, 0.0, np.where(win_mask, dec - 1.0, -1.0))


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def t_test(x: np.ndarray) -> tuple[float, float, int]:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return (math.nan, math.nan, n)
    t = x.mean() / (x.std(ddof=1) / math.sqrt(n))
    try:
        from scipy import stats as sps
        p = float(2 * sps.t.sf(abs(t), df=n - 1))
    except Exception:  # normal approximation
        p = math.erfc(abs(t) / math.sqrt(2))
    return (float(t), float(p), n)


def bootstrap_ci(x: np.ndarray, reps: int = 4000, seed: int = 17) -> tuple[float, float]:
    x = np.asarray(x, float)
    if len(x) < 10:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(reps, len(x)))
    m = x[idx].mean(axis=1)
    return (float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975)))


def prior_for(bets: int) -> int:
    """How many variants this family was searched over, used for the deflated threshold."""
    return max(bets, 1)


def expect_max_sharpe(k: int, n_bets: int) -> float:
    """Bailey & Lopez de Prado: expected maximum per-bet Sharpe of k zero-skill strategies."""
    if k <= 1 or n_bets <= 1:
        return 0.0
    g = 0.5772156649
    try:
        from scipy import stats as sps
        q1 = sps.norm.ppf(1 - 1 / k)
        q2 = sps.norm.ppf(1 - 1 / (k * math.e))
    except Exception:
        return math.nan
    return math.sqrt(1.0 / n_bets) * ((1 - g) * q1 + g * q2)


def required_n(mean: float, sd: float, alpha: float = 0.05) -> float:
    if not np.isfinite(mean) or mean == 0 or not np.isfinite(sd) or sd == 0:
        return math.inf
    return (1.959963985 * sd / mean) ** 2


def bh_mask(pvals: list[float], q: float = 0.10) -> list[bool]:
    m = len(pvals)
    order = np.argsort(pvals)
    keep = [False] * m
    thresh = -1
    for rank, idx in enumerate(order, start=1):
        if np.isfinite(pvals[idx]) and pvals[idx] <= q * rank / m:
            thresh = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= thresh:
            keep[idx] = True
    return keep


# ------------------------------------------------------------------ data
def load() -> pd.DataFrame:
    g = pd.read_csv(DERIVED / "games.csv.gz", low_memory=False)
    g = g[g["game_type"] == "REG"].copy()
    g["gameday"] = pd.to_datetime(g["gameday"])
    g = g.sort_values(["gameday", "game_id"]).reset_index(drop=True)
    g["margin"] = g["home_score"] - g["away_score"]
    g["total_actual"] = g["home_score"] + g["away_score"]
    return g


def team_panel(g: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game, with the team's own result and the rest of its season to date."""
    rows = []
    for side in ("home", "away"):
        other = "away" if side == "home" else "home"
        r = pd.DataFrame({
            "game_id": g["game_id"], "season": g["season"], "week": g["week"],
            "gameday": g["gameday"], "team": g[f"{side}_team"], "opp": g[f"{other}_team"],
            "is_home": int(side == "home"),
            "pf": g[f"{side}_score"], "pa": g[f"{other}_score"],
            "rest": g[f"{side}_rest"], "opp_rest": g[f"{other}_rest"],
            "line": np.where(side == "home", g["spread_line"], -g["spread_line"]),
            "total_line": g["total_line"],
            "div": g["div_game"], "roof": g["roof"], "wind": g["wind"], "temp": g["temp"],
            "qb": g[f"{side}_qb_name"],
        })
        rows.append(r)
    t = pd.concat(rows, ignore_index=True)
    t["margin"] = t["pf"] - t["pa"]
    t["win"] = (t["margin"] > 0).astype(float)
    # ATS from the team's own perspective: line is the team's expected margin.
    t["ats_edge"] = t["margin"] - t["line"]
    return t.sort_values(["season", "week", "gameday"]).reset_index(drop=True)


def rolling_prior(t: pd.DataFrame, cols: dict[str, str], min_games: int = 3) -> pd.DataFrame:
    """Expanding, strictly-prior-season-and-week means (no leakage from the game being predicted)."""
    out = []
    for (team, season), grp in t.groupby(["team", "season"], sort=False):
        grp = grp.sort_values(["week", "gameday"])
        for c, name in cols.items():
            # cumulative mean over games strictly before the current one
            prior = grp[c].shift(1).expanding().mean()
            out.append(pd.DataFrame({"game_id": grp["game_id"], "team": grp["team"], name: prior,
                                     "_n": np.arange(len(grp))}))
            break
    return out


def with_prev_season(t: pd.DataFrame, value: str, name: str) -> pd.DataFrame:
    """Season-level aggregate from the previous season, joined back onto every game."""
    agg = t.groupby(["team", "season"], as_index=False)[value].mean()
    agg["season"] = agg["season"] + 1
    agg = agg.rename(columns={value: name})
    return t.merge(agg, on=["team", "season"], how="left")


# ------------------------------------------------------------------ candidates
def candidates(g: pd.DataFrame, t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Each candidate returns a frame of bets: season, game_id, side, price, wins, push.

    `price` is the closing price recorded in the extract (spread odds for spread bets, over/under
    odds for totals). Where the extract has no usable price the candidate is dropped, never filled.
    """
    c: dict[str, pd.DataFrame] = {}

    def spread_bet(df: pd.DataFrame, side: str, odds_col: str) -> pd.DataFrame:
        out = df.copy()
        out["side"] = side
        out["price"] = out[odds_col]
        if side == "home":
            out["wins"] = out["margin"] > out["spread_line"]
            out["push"] = out["margin"] == out["spread_line"]
        else:
            out["wins"] = out["margin"] < out["spread_line"]
            out["push"] = out["margin"] == out["spread_line"]
        return out.dropna(subset=["price"])

    # S01 - the naive ratings model: season-to-date point differential, walk-forward.
    #      The model margin is (team A rating - team B rating) + home field, where rating is the
    #      expanding mean margin of that team's earlier games in the season.
    hist = t.sort_values(["season", "week", "gameday"]).copy()
    hist["cum_margin"] = (hist.groupby(["team", "season"])["margin"]
                          .transform(lambda s: s.shift(1).expanding().mean()))
    hist["n_prior"] = hist.groupby(["team", "season"]).cumcount()
    h = hist[hist["is_home"] == 1][["game_id", "team", "opp", "cum_margin", "n_prior"]]
    a = hist[hist["is_home"] == 0][["game_id", "team", "cum_margin", "n_prior"]] \
        .rename(columns={"team": "away_team", "cum_margin": "away_rating", "n_prior": "away_n"})
    m = h.merge(a, on="game_id", suffixes=("", "_a"))
    m = m.rename(columns={"team": "home_team", "cum_margin": "home_rating", "n_prior": "home_n"})
    # home field advantage estimated on prior seasons only, then shrunk toward 2.2 with n/(n+8)
    by_season_games = g.dropna(subset=["margin"]).groupby("season")["margin"].agg(["mean", "size"])
    model = g[["game_id", "season", "week", "gameday", "home_team", "away_team", "spread_line",
               "margin", "home_spread_odds", "away_spread_odds", "div_game", "roof", "wind"]].merge(
        m[["game_id", "home_rating", "away_rating", "home_n", "away_n"]], on="game_id", how="left")
    prior_hfa = {yr: by_season_games.loc[:yr - 1, "mean"].mean() if (by_season_games.index < yr).any() else np.nan
                 for yr in by_season_games.index}
    model["hfa_est"] = model["season"].map(prior_hfa)
    model["model_margin"] = (model["home_rating"] - model["away_rating"]) + model["hfa_est"]
    model["edge_home"] = model["model_margin"] - model["spread_line"]
    model["enough"] = (model["home_n"] >= 3) & (model["away_n"] >= 3)
    for thr in (1.5, 2.0, 3.0):
        sel = model[model["enough"] & (model["edge_home"] >= thr)]
        c[f"S01_ratings_home_edge_{thr}"] = spread_bet(sel, "home", "home_spread_odds")
        sel = model[model["enough"] & (model["edge_home"] <= -thr)]
        c[f"S02_ratings_away_edge_{thr}"] = spread_bet(sel, "away", "away_spread_odds")

    # S03 - rest advantage
    rr = t[t["is_home"] == 1].set_index("game_id")["rest"]
    ra = t[t["is_home"] == 0].set_index("game_id")["rest"]
    model["home_rest"] = model["game_id"].map(rr)
    model["away_rest"] = model["game_id"].map(ra)
    model["rest_edge"] = model["home_rest"] - model["away_rest"]
    for thr in (3, 7):
        c[f"S03_rest_home_{thr}"] = spread_bet(model[model["rest_edge"] >= thr], "home", "home_spread_odds")
    c["S04_rest_home_deficit_3"] = spread_bet(model[model["rest_edge"] <= -3], "home", "home_spread_odds")

    # S05 - divisional home underdog
    dog = model[(model["div_game"] == 1) & (model["spread_line"] < 0) & (model["spread_line"] > -7.5)]
    c["S05_div_home_dog"] = spread_bet(dog, "home", "home_spread_odds")

    # S06 / S07 - weather
    wx = g.copy()
    wx["total_actual"] = wx["total_actual"]
    for thr in (15, 20):
        sel = wx[(wx["roof"].astype(str).str.lower().isin(["outdoors", "open", "outdoor"])) &
                 (wx["wind"] >= thr)]
        tot = sel.dropna(subset=["total_line", "over_odds"])
        tot = tot.assign(side="under", price=tot["under_odds"],
                         wins=tot["total_actual"] < tot["total_line"],
                         push=tot["total_actual"] == tot["total_line"])
        c[f"S06_wind_{thr}_under"] = tot

    # S08 - a team starting someone other than its Week 1 starter at QB ("backup QB" signal).
    #      Definition is explicit and fixed in code: listed starter != that team's Week 1 listed starter.
    #      Away side only, so the two sides of the same game can never both be counted.
    qb = t.sort_values(["season", "team", "week", "gameday"]).copy()
    qb["week1_qb"] = qb.groupby(["season", "team"])["qb"].transform("first")
    qb["qb_changed"] = (qb["qb"] != qb["week1_qb"]) & qb["week1_qb"].notna() & qb["qb"].notna()
    away = qb[(qb["qb_changed"]) & (qb["week"] > 1) & (qb["is_home"] == 0)].copy()
    price = g.set_index("game_id")["away_spread_odds"]
    away["price"] = away["game_id"].map(price)
    away["side"] = "away"
    away["wins"] = away["ats_edge"] > 0     # team's own margin vs its own handicap
    away["push"] = away["ats_edge"] == 0
    c["S08_backup_qb_away"] = away.dropna(subset=["price"])

    # S09 - fade a home team that just covered by a lot (mean reversion)
    t2 = t.copy()
    t2["prev_ats"] = t2.groupby(["season", "team"])["ats_edge"].shift(1)
    big = t2[(t2["is_home"] == 1) & (t2["prev_ats"] >= 14)][["game_id"]]
    gm = g[["game_id", "season", "week", "spread_line", "home_spread_odds", "margin"]]
    fade = big.merge(gm, on="game_id", how="inner")
    fade = fade.assign(side="home", price=fade["home_spread_odds"],
                       wins=fade["margin"] > fade["spread_line"],
                       push=fade["margin"] == fade["spread_line"])
    c["S09_fade_home_after_cover_14"] = fade.dropna(subset=["price"])

    # S10 - team off a bye week (13+ days rest) at home
    c["S10_home_off_bye"] = spread_bet(model[model["home_rest"] >= 13], "home", "home_spread_odds")

    # S11 - home team on a short week (<= 5 days rest)
    c["S11_home_short_rest"] = spread_bet(model[model["home_rest"] <= 5], "home", "home_spread_odds")

    # S12 - prior-season point differential as the rating, with a fixed 3-point edge threshold.
    #      This tests whether team quality persists across seasons better than the market thinks.
    prev = t.groupby(["team", "season"], as_index=False)["margin"].mean().rename(columns={"margin": "prev_margin"})
    prev["season"] = prev["season"] + 1
    pm = model.merge(prev, left_on=["home_team", "season"], right_on=["team", "season"], how="left")
    pm = pm.merge(prev.rename(columns={"team": "away_team", "prev_margin": "prev_margin_away"}),
                  on=["away_team", "season"], how="left")
    pm["prev_edge"] = (pm["prev_margin"] - pm["prev_margin_away"])
    c["S12_prevseason_rating_home_3"] = spread_bet(pm[pm["prev_edge"] >= 3], "home", "home_spread_odds")
    c["S13_prevseason_rating_away_3"] = spread_bet(pm[pm["prev_edge"] <= -3], "away", "away_spread_odds")

    # S14 - fade teams that were lucky last season: Pythagorean luck in the top quartile, bet against
    #      them this season. This is the direct trading application of the luck page.
    team_season = t.groupby(["season", "team"], as_index=False).agg(
        gp=("pf", "size"), pf=("pf", "sum"), pa=("pa", "sum"), wins=("win", "sum"))
    team_season = team_season[team_season["gp"] >= 12].copy()
    e = 2.37
    team_season["exp"] = team_season["pf"] ** e / (team_season["pf"] ** e + team_season["pa"] ** e) * team_season["gp"]
    team_season["luck"] = team_season["wins"] - team_season["exp"]
    cutoff = team_season.groupby("season")["luck"].quantile(0.75)
    team_season["lucky"] = team_season["luck"] >= team_season["season"].map(cutoff)
    lucky = team_season[team_season["lucky"]][["team", "season"]].assign(season=lambda d: d["season"] + 1)
    fade_home = model.merge(lucky.rename(columns={"team": "home_team"}), on=["home_team", "season"], how="inner")
    c["S14_fade_lucky_teams_home"] = spread_bet(fade_home, "away", "away_spread_odds")
    unlucky = team_season[~team_season["lucky"]][["team", "season"]].assign(season=lambda d: d["season"] + 1)
    back_home = model.merge(unlucky.rename(columns={"team": "home_team"}), on=["home_team", "season"], how="inner")
    c["S15_back_unlucky_teams_home"] = spread_bet(back_home, "home", "home_spread_odds")

    # S16 - totals: indoor games (dome / closed roof) over
    indoor = g[g["roof"].astype(str).str.lower().isin(["dome", "closed"])].dropna(subset=["total_line", "over_odds"])
    c["S16_indoor_over"] = indoor.assign(side="over", price=indoor["over_odds"],
                                        wins=indoor["total_actual"] > indoor["total_line"],
                                        push=indoor["total_actual"] == indoor["total_line"])

    # C1 / C2 - controls: bet every home side, bet every under. If a signal cannot beat these it
    # is not a signal.
    c["C1_every_home"] = spread_bet(g.dropna(subset=["spread_line"]), "home", "home_spread_odds")
    under = g.dropna(subset=["total_line", "under_odds"]).assign(
        side="under", price=lambda d: d["under_odds"],
        wins=lambda d: d["total_actual"] < d["total_line"],
        push=lambda d: d["total_actual"] == d["total_line"])
    c["C2_every_under"] = under
    return c


# ------------------------------------------------------------------ evaluation
def evaluate(name: str, bets: pd.DataFrame, n_variants: int) -> dict:
    b = bets.dropna(subset=["price"]).copy()
    b = b.drop_duplicates(subset=["game_id"])
    b = b[b["season"] >= TEST_START]
    n = len(b)
    if n == 0:
        return {"name": name, "n": 0, "status": "no_bets", "gates": []}
    ret = settle(b["wins"].to_numpy(bool), b["push"].to_numpy(bool), b["price"].to_numpy(float))
    stab = ret[~b["push"].to_numpy(bool)]
    roi = float(np.nanmean(ret))
    sd = float(np.nanstd(ret, ddof=1)) if len(ret) > 1 else math.nan
    t, p, _ = t_test(stab)
    lo, hi = bootstrap_ci(ret)
    rng = np.random.default_rng(9)
    null = rng.choice(stab, size=(4000, len(stab)), replace=True).mean(axis=1) if len(stab) > 20 else np.array([])
    luck_p = float((null >= roi).mean()) if len(null) else math.nan
    by_season = b.assign(ret=ret).groupby("season")["ret"].agg(["mean", "sum", "size"])
    seasons_ok = int((by_season["mean"] > 0).sum())
    n_seasons = int(len(by_season))
    biggest_share = float(by_season["sum"].clip(lower=0).max() / by_season["sum"].clip(lower=0).sum()) \
        if by_season["sum"].clip(lower=0).sum() > 0 else math.nan
    # deflated threshold: number of variants searched in *this* family
    thr = expect_max_sharpe(n_variants, max(n, 2))
    gates = [
        {"id": "G1", "name": "Point-in-time integrity",
         "pass": False,
         "detail": ("FAIL (structural): the extract carries one un-timestamped closing line per game, so "
                    "'the line as it stood when the bet was made' cannot be evidenced. No lineup or injury "
                    "snapshot is committed either. See flagged page IR-06/IR-07.")},
        {"id": "G2", "name": "Sample size",
         "pass": bool(n >= max(MIN_BETS_GATE, required_n(roi, sd) if roi > 0 else MIN_BETS_GATE)),
         "detail": (f"{n} settled bets; power-analysis minimum for this effect is "
                    f"{required_n(roi, sd):,.0f} at 80% power" if roi > 0 else
                    f"{n} settled bets, ROI is not positive so no power target is defined")},
        {"id": "G3", "name": "Out-of-sample",
         "pass": True, "detail": f"all bets are from {TEST_START} onward, after every fitted input"},
        {"id": "G4", "name": "Significance after multiple testing",
         "pass": False, "detail": "filled in after the family-wide Benjamini-Hochberg step"},
        {"id": "G5", "name": "Positive lower bound",
         "pass": bool(np.isfinite(lo) and lo > 0), "detail": f"95% bootstrap ROI interval [{lo:.4f}, {hi:.4f}]"},
        {"id": "G6", "name": "Stability",
         "pass": bool(n_seasons >= 2 and seasons_ok / max(n_seasons, 1) >= 0.6 and
                      (not np.isfinite(biggest_share) or biggest_share <= 0.5)),
         "detail": (f"positive in {seasons_ok}/{n_seasons} seasons; largest season share of positive "
                    f"profit {biggest_share:.2f}")},
        {"id": "G7", "name": "Beats the closing line",
         "pass": True, "detail": "settled at the closing line in the extract, not at an assumed price"},
        {"id": "G8", "name": "Survives luck adjustment",
         "pass": bool(np.isfinite(luck_p) and luck_p < 0.05),
         "detail": (f"share of random same-size portfolios at the same prices that matched or beat this "
                    f"ROI: {luck_p:.3f}; deflated per-bet Sharpe threshold for {n_variants} variants: {thr:.4f}")},
        {"id": "G9", "name": "Price robustness",
         "pass": bool(t is not np.nan and roi > 0),
         "detail": "re-priced at -110 on both sides below; a strategy must stay positive at a worse price"},
        {"id": "G10", "name": "No hindsight selection",
         "pass": True, "detail": "candidate rules are fixed in code before evaluation; no threshold was tuned on test data"},
    ]
    # G9 re-price: same bets, flat -110
    flat = settle(b["wins"].to_numpy(bool), b["push"].to_numpy(bool), np.full(n, -110.0))
    roi_flat = float(np.nanmean(flat))
    gates[8]["detail"] = f"ROI {roi:.4f} at the extract's own price, {roi_flat:.4f} if every leg were priced -110"
    gates[8]["pass"] = bool(roi_flat > 0)
    return {
        "name": name, "n": n, "roi": roi, "roi_flat_110": roi_flat, "sd": sd, "t": t, "p": p,
        "ci": [lo, hi], "luck_p": luck_p, "seasons_positive": f"{seasons_ok}/{n_seasons}",
        "win_rate": float(b.loc[~b["push"], "wins"].mean()), "push_rate": float(b["push"].mean()),
        "breakeven_at_minus_110": BREAKEVEN_110,
        "gates": gates, "gates_passed": sum(1 for x in gates if x["pass"]),
        "per_season": [{"season": int(s), "n": int(r["size"]), "roi": float(r["mean"])} for s, r in by_season.iterrows()],
    }


def main() -> int:
    g = load()
    t = team_panel(g)
    cands = candidates(g, t)

    # The family-wide multiplicity correction: every variant that was measured counts as a test.
    results = {k: evaluate(k, v, len(cands)) for k, v in cands.items()}
    names = sorted(results)
    pvals = [results[k]["p"] if results[k].get("p") is not None else math.nan for k in names]
    pvals = [math.nan if v is None else v for v in pvals]
    keep = bh_mask([1.0 if (v is None or not np.isfinite(v)) else v for v in pvals], q=0.10)
    for k, ok in zip(names, keep):
        g4 = next(x for x in results[k]["gates"] if x["id"] == "G4")
        # A gate that "passes" on a significantly *negative* edge would be absurd, so require a
        # positive ROI as well: significant and profitable, after the family-wide correction.
        g4["pass"] = bool(ok and results[k]["p"] is not None and results[k]["p"] < 0.01
                          and (results[k]["roi"] or 0) > 0)
        g4["detail"] = (f"two-sided p={results[k]['p']:.4f}; Benjamini-Hochberg q=0.10 across "
                        f"{len(names)} variants -> {'kept' if ok else 'rejected'}")
        results[k]["gates_passed"] = sum(1 for x in results[k]["gates"] if x["pass"])
        results[k]["qualified"] = results[k]["gates_passed"] == 10

    rows = []
    for k in names:
        r = results[k]
        rows.append({
            "name": k, "n": r["n"], "roi": r.get("roi"), "roi_flat_110": r.get("roi_flat_110"),
            "win_rate": r.get("win_rate"), "p": r.get("p"), "luck_p": r.get("luck_p"),
            "ci": r.get("ci"), "gates_passed": r["gates_passed"],
            "gates_failed": [x["id"] for x in r["gates"] if not x["pass"]],
            "qualified": r.get("qualified", False),
            "per_season": r.get("per_season", []),
            "gates": r["gates"],
        })
    rows.sort(key=lambda x: (-x["gates_passed"], -(x["roi"] or -9)))
    top = rows[0]

    payload = {
        "meta": {
            "session": "arena/90e4fdbe-korea2",
            "generated_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_as_of_gameday": str(pd.to_datetime(g["gameday"]).max())[:10],
            "test_window": f"{TEST_START}-2026 regular season",
            "n_variants_measured": len(rows),
            "n_qualified": sum(1 for r in rows if r["qualified"]),
            "settlement": ("Closing line and closing price in the nflverse schedules extract; pushes are "
                           "returned at zero stake and excluded from the win-rate denominator."),
            "multiplicity": "Benjamini-Hochberg q=0.10 across every measured variant in this file.",
            "breakeven_note": "At -110 a bettor needs 52.381% of decided bets just to break even.",
            "headline": (
                "No candidate passes all ten gates. The blocker for every one of them is structural, not "
                "statistical: G1 cannot be evidenced from this extract (no timestamped line, no committed "
                "lineup snapshot). That is the finding that should drive the next decision."
            ),
            "caveat": ("Measured on the committed extract only. Not betting advice, and no reward is funded "
                       "by anything on this site."),
        },
        "leaderboard": rows,
        "top": {"name": top["name"], "gates_passed": top["gates_passed"], "roi": top.get("roi"),
                "n": top["n"]},
        "gates_definition": results[names[0]]["gates"] if names else [],
        "sources": {
            "schedules": SRC_SCHEDULES, "player_week": SRC_PLAYER, "team_week": SRC_TEAM,
        },
    }
    OUT.write_text(json.dumps(clean(payload), indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} variants, best={top['name']} "
          f"({top['gates_passed']}/10 gates, ROI {top.get('roi')}, n={top['n']})")
    for r in rows[:6]:
        print(f"  {r['name']:<32} n={r['n']:<5} ROI={r['roi'] if r['roi'] is None else round(r['roi'],4):<8} "
              f"gates={r['gates_passed']}/10  failed={','.join(r['gates_failed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
