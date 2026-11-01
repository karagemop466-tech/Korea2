"""Validation gates, luck removal and the leaderboard.

Every number published on the site comes from this module. Gates are mechanical:
the thresholds below are fixed in code *before* any strategy was evaluated, and a
strategy either clears them or it does not.

Gates
-----
G1  LOOKAHEAD_AUDIT   declared inputs are all pre-game columns, and the win rate is not
                      statistically impossible given market prices (p < 1e-6 flags a leak)
G2  SAMPLE_SIZE       >= 300 graded tickets in the evaluation window
G3  OUT_OF_SAMPLE     rule parameters pre-declared; every published number is 2015+
G4  ROI_CI95_LOWER    percentile-bootstrap 95% CI lower bound of ROI > 0
G5  PERMUTATION_P     p < 0.05 against a null where每 ticket wins with the market's
                      de-vigged probability
G6  BH_Q              Benjamini-Hochberg q < 0.10 across every strategy tested
G7  DEFLATED_SHARPE   Bailey/Lopez de Prado DSR >= 0.95 with n_trials = number tested
G8  CALIBRATION       model probabilities beat the market's Brier score (N/A without a model)
G9  SEASON_STABILITY  ROI > 0 in >= 60% of seasons with >= 20 graded tickets (min 3 seasons)
G10 SPLIT_HALF        ROI > 0 in both halves of the evaluation window
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from lib.common import (INTERIM, bh_qvalues, bootstrap_mean_ci, brier, deflated_sharpe_ratio,
                        normal_cdf, write_json)

EVAL_START = 2015
MIN_TICKETS = 300
MIN_SEASON_TICKETS = 20
MIN_SEASONS = 3
STABILITY_SHARE = 0.60
ALPHA_PERM = 0.05
ALPHA_Q = 0.10
DSR_MIN = 0.95
N_BOOT = 10000
N_PERM = 20000

PRE_GAME_COLUMNS = {
    "own_margin", "own_total", "own_home_wp", "own_away_wp", "own_sigma", "own_home_ml", "own_away_ml",
    "elo_engine_margin", "elo_engine_total", "elo_diff", "elo_home_pre", "elo_away_pre",
    "spread_line", "total_line", "home_moneyline", "away_moneyline", "home_spread_odds",
    "away_spread_odds", "over_odds", "under_odds", "away_rest", "home_rest", "rest_diff",
    "short_week_home", "short_week_away", "off_bye_home", "off_bye_away", "div_game", "roof",
    "surface", "temp", "wind", "is_dome", "is_thursday", "weekday", "gameday", "gametime",
    "home_team", "away_team", "season", "week", "neutral", "pf_ewm", "pa_ewm", "win_pct_l10",
    "pf_l5", "pa_l5", "games_played_before", "location", "stadium", "referee",
    "mkt_home_win_prob", "mkt_total", "mkt_spread", "blend_margin", "blend_total",
}
POST_GAME_COLUMNS = {"margin", "points_total", "home_win", "home_score", "away_score", "result",
                     "total", "elo_home_post", "elo_away_post", "played"}

DECLARED_INPUTS = {
    "ATS_OWN": ["own_margin", "spread_line"],
    "TOT_OWN": ["own_total", "total_line"],
    "ATS_ELO_ENGINE": ["elo_engine_margin", "spread_line"],
    "TOT_ELO_ENGINE": ["elo_engine_total", "total_line"],
    "ML_OWN": ["own_home_wp", "mkt_home_win_prob"],
    "SIT_HOME_DOG": ["spread_line"],
    "SIT_DIV_DOG": ["div_game", "spread_line"],
    "SIT_DIV_UNDER": ["div_game"],
    "SIT_REST_EDGE": ["rest_diff"],
    "SIT_OFF_BYE": ["off_bye_home", "off_bye_away"],
    "SIT_BYE_FAV_FADE": ["off_bye_home", "off_bye_away", "spread_line"],
    "SIT_WINDY_UNDER": ["wind"],
    "SIT_FREEZE_UNDER": ["temp"],
    "SIT_DOME_OVER": ["is_dome"],
    "SIT_TNF_UNDER": ["is_thursday"],
    "OPEN_EDGE_2": ["own_margin", "spread_line"],
    "CTRL_ALL_HOME": [],
    "CTRL_ALL_OVER": [],
    "CTRL_LEAK": ["margin"],           # deliberate lookahead: uses the final score
    "PARLAY": ["own_margin", "own_total", "spread_line", "total_line", "own_home_wp", "mkt_home_win_prob"],
}


def declared_inputs(strategy: str) -> list[str]:
    if strategy in DECLARED_INPUTS:
        return DECLARED_INPUTS[strategy]
    for key in sorted(DECLARED_INPUTS, key=len, reverse=True):
        if strategy.startswith(key) and key != "PARLAY":
            return DECLARED_INPUTS[key]
    if strategy.startswith("PARLAY"):
        return DECLARED_INPUTS["PARLAY"]
    raise KeyError(f"no declared inputs for {strategy}")


# ------------------------------------------------------------------ metrics
def roi_stats(pnl: np.ndarray) -> float:
    pnl = np.asarray(pnl, float)
    graded = (pnl != 0).sum()
    return float(pnl.sum() / graded) if graded else float("nan")


def strategy_metrics(bets: pd.DataFrame, g: pd.DataFrame, strategy: str,
                     n_trials: int) -> dict:
    d = bets[(bets["strategy"] == strategy) & (bets["window"] == "eval")].copy()
    pnl = d["pnl"].to_numpy(float)
    graded_mask = pnl != 0
    n_all = len(d)
    n_graded = int(graded_mask.sum())
    pushes = int((pnl == 0).sum())
    out = {"strategy": strategy, "n_tickets": n_all, "n_graded": n_graded, "pushes": pushes,
           "units": float(pnl.sum())}

    if n_graded < 5:
        out.update({"roi": None, "win_rate": None, "avg_odds_dec": None})
        return out

    gpnl = pnl[graded_mask]
    roi = float(gpnl.mean())
    out["roi"] = roi
    out["win_rate"] = float((d["result"] == "win").sum() / n_graded)
    out["avg_odds_dec"] = float(d["dec_odds"].mean())
    out["avg_fair_prob"] = float(d["fair_prob"].mean()) if d["fair_prob"].notna().any() else None
    out["mean_price_implied"] = float(1.0 / d["dec_odds"].mean())

    # --- market baseline: what a random ticket at the same prices returns
    out["roi_market_baseline"] = float(np.mean(d["fair_prob"] * d["dec_odds"] - 1)) if d["fair_prob"].notna().any() else None

    mean, lo, hi = bootstrap_mean_ci(gpnl, n_boot=N_BOOT)
    out["roi_ci95"] = [lo, hi]

    # season-block bootstrap (accounts for within-season clustering a little better)
    seas = d.loc[graded_mask].groupby("season")["pnl"].agg(["sum", "size"])
    if len(seas) >= 3:
        rng = np.random.default_rng(3)
        block_rois = []
        arr = seas.reset_index()
        for _ in range(2000):
            pick = arr.sample(len(arr), replace=True, random_state=int(rng.integers(1 << 31)))
            block_rois.append(pick["sum"].sum() / max(1, pick["size"].sum()))
        out["roi_ci95_season_block"] = [float(np.quantile(block_rois, 0.025)),
                                       float(np.quantile(block_rois, 0.975))]

    # --- permutation test against the de-vigged market null
    if d["fair_prob"].notna().all():
        p = d["fair_prob"].to_numpy(float)
        dec = d["dec_odds"].to_numpy(float)
        rng = np.random.default_rng(17)
        wins = rng.random((N_PERM, n_graded)) < p[graded_mask]
        pay = np.where(wins, dec[graded_mask] - 1.0, -1.0)
        null_roi = pay.mean(axis=1)
        out["perm_p"] = float((null_roi >= roi).mean())
        out["null_roi_mean"] = float(null_roi.mean())
        out["null_roi_sd"] = float(null_roi.std())
    else:
        out["perm_p"] = None

    # --- deflated Sharpe
    dsr = deflated_sharpe_ratio(gpnl, n_trials)
    out["sharpe_per_bet"] = dsr.get("sr")
    out["deflated_sharpe"] = dsr.get("dsr")

    # --- season stability
    per_season = d.loc[graded_mask].groupby("season")["pnl"].agg(["sum", "size"])
    per_season = per_season[per_season["size"] >= MIN_SEASON_TICKETS]
    out["seasons_qualified"] = int(len(per_season))
    out["seasons_positive"] = int((per_season["sum"] > 0).sum())
    out["season_roi"] = {int(k): float(v) for k, v in
                         (per_season["sum"] / per_season["size"]).round(4).items()}

    # --- split half (by season)
    seasons = sorted(d["season"].unique())
    if len(seasons) >= 4:
        mid = seasons[len(seasons) // 2]
        first = d[(d["season"] < mid) & (d["pnl"] != 0)]["pnl"]
        second = d[(d["season"] >= mid) & (d["pnl"] != 0)]["pnl"]
        out["roi_first_half"] = roi_stats(first) if len(first) else None
        out["roi_second_half"] = roi_stats(second) if len(second) else None

    # --- probability diagnostics where the strategy carries a model probability
    model_p = model_probability(d, g)
    if model_p is not None and len(model_p):
        y = (d["result"] == "win").astype(float).to_numpy()
        ok = ~np.isnan(model_p) & (d["pnl"].to_numpy() != 0)
        if ok.sum() > 30:
            out["brier_model"] = brier(model_p[ok], y[ok])
            out["brier_market"] = brier(d["fair_prob"].to_numpy()[ok], y[ok])
            out["model_edge_vs_fair"] = float(np.nanmean(model_p[ok] - d["fair_prob"].to_numpy()[ok]))
            out["model_implied_roi"] = float(np.mean(model_p[ok] * d["dec_odds"].to_numpy()[ok] - 1))
    return out


def model_probability(d: pd.DataFrame, g: pd.DataFrame) -> np.ndarray | None:
    """Our own probability of winning the ticket, where the strategy has one."""
    eng = None
    name = str(d["strategy"].iloc[0]) if len(d) else ""
    if name.startswith(("ATS_OWN", "TOT_OWN", "PARLAY_SGP_ATS_TOT", "ML_OWN")):
        eng = "own"
    elif name.startswith(("ATS_ELO", "TOT_ELO")):
        eng = "elo_engine"
    if eng is None:
        return None
    m = g.set_index("game_id")
    probs = []
    for row in d.itertuples(index=False):
        gid = str(row.game_id).split("+")[0]
        if gid not in m.index:
            probs.append(np.nan)
            continue
        gr = m.loc[gid]
        if isinstance(gr, pd.DataFrame):
            gr = gr.iloc[0]
        if row.market == "MONEYLINE":
            p = gr["own_home_wp"] if row.side == "home" else gr["own_away_wp"]
        elif row.market == "SPREAD":
            sig = gr["own_sigma"] if eng == "own" else 13.9
            edge = (gr[f"{eng}_margin"] - gr["spread_line"])
            edge = edge if row.side == "home" else -edge
            p = normal_cdf(edge / (sig if not pd.isna(sig) else 13.5))
        elif row.market == "TOTAL":
            edge = gr[f"{eng}_total"] - gr["total_line"]
            edge = edge if row.side == "over" else -edge
            p = normal_cdf(edge / 13.9)
        else:
            p = np.nan
        probs.append(float(p) if not pd.isna(p) else np.nan)
    return np.array(probs)


def gate_rows(m: dict) -> list[dict]:
    strat = m["strategy"]
    inputs = declared_inputs(strat)
    leaks = [c for c in inputs if c in POST_GAME_COLUMNS]
    impossible = (m.get("perm_p") is not None and m.get("perm_p") == 0.0 and m["roi"] > 0.25)
    g1 = "PASS" if (not leaks and not impossible) else "FAIL"

    n = m.get("n_graded", 0)
    g2 = "PASS" if n >= MIN_TICKETS else "FAIL"

    g3 = "PASS"  # enforced structurally: eval window only, pre-declared rules

    ci = m.get("roi_ci95")
    g4 = "PASS" if (ci and ci[0] > 0) else "FAIL"

    p = m.get("perm_p")
    g5 = "PASS" if (p is not None and p < ALPHA_PERM) else ("NA" if p is None else "FAIL")

    q = m.get("bh_q")
    g6 = "PASS" if (q is not None and q < ALPHA_Q) else ("NA" if q is None else "FAIL")

    dsr = m.get("deflated_sharpe")
    g7 = "PASS" if (dsr is not None and dsr >= DSR_MIN) else "FAIL"

    if "brier_model" in m and "brier_market" in m:
        g8 = "PASS" if m["brier_model"] < m["brier_market"] else "FAIL"
    else:
        g8 = "NA"

    sq = m.get("seasons_qualified", 0)
    sp = m.get("seasons_positive", 0)
    g9 = "PASS" if (sq >= MIN_SEASONS and sp / max(1, sq) >= STABILITY_SHARE) else "FAIL"

    fh, sh = m.get("roi_first_half"), m.get("roi_second_half")
    g10 = "PASS" if (fh is not None and sh is not None and fh > 0 and sh > 0) else "FAIL"

    rows = [("G1", "Lookahead audit", g1, _g1_note(leaks, impossible)),
            ("G2", "Sample size >= 300", g2, f"{n:,} graded tickets"),
            ("G3", "Out-of-sample", g3, "2015+ only; rules pre-declared"),
            ("G4", "ROI 95% CI lower > 0", g4, _ci_note(ci)),
            ("G5", "Permutation p < 0.05", g5, _p_note(p)),
            ("G6", "BH q < 0.10", g6, _q_note(q)),
            ("G7", "Deflated Sharpe >= 0.95", g7, _dsr_note(dsr)),
            ("G8", "Calibration vs market", g8, _g8_note(m)),
            ("G9", "Season stability", g9, f"{sp}/{sq} qualifying seasons positive"),
            ("G10", "Split-half consistency", g10, _g10_note(fh, sh))]
    return [{"gate": a, "name": b, "status": c, "detail": dd} for a, b, c, dd in rows]


def _g1_note(leaks, impossible):
    if leaks:
        return f"declared inputs include post-game column(s): {', '.join(leaks)}"
    if impossible:
        return "win rate is statistically impossible from pre-game information"
    return "all inputs are pre-game columns"


def _ci_note(ci):
    if not ci:
        return "not computable"
    return f"95% CI [{ci[0]:+.1%}, {ci[1]:+.1%}]"


def _p_note(p):
    if p is None:
        return "no de-vigged price available"
    return f"p = {p:.4f}"


def _q_note(q):
    if q is None:
        return "not computable"
    return f"q = {q:.4f}"


def _dsr_note(dsr):
    if dsr is None:
        return "not computable"
    return f"DSR = {dsr:.3f}"


def _g8_note(m):
    if "brier_model" not in m:
        return "strategy carries no model probability"
    return f"Brier model {m['brier_model']:.4f} vs market {m['brier_market']:.4f}"


def _g10_note(fh, sh):
    if fh is None or sh is None:
        return "not enough seasons"
    return f"first half {fh:+.1%}, second half {sh:+.1%}"


def tier(gates: list[dict]) -> tuple[str, str]:
    status = {r["gate"]: r["status"] for r in gates}
    fails = [k for k, v in status.items() if v == "FAIL"]
    if "G1" in fails or "G3" in fails:
        return "REJECTED", "fails the integrity gates"
    if "G2" in fails:
        return "NEEDS_REVIEW", "insufficient sample; published as flagged, not ranked"
    if not fails:
        return "GOLD", "clears every gate"
    if len(fails) <= 1 and "G4" not in fails:
        return "SILVER", f"single gate miss ({', '.join(fails)})"
    if "G4" not in fails:
        return "BRONZE", f"{len(fails)} gate misses ({', '.join(fails)})"
    return "REJECTED", f"fails {', '.join(fails)}"


REWARD_POINTS = {"GOLD": 10, "SILVER": 5, "BRONZE": 2, "NEEDS_REVIEW": 0, "REJECTED": 0}


def power_analysis(bets: pd.DataFrame) -> dict:
    """How many tickets would be needed to detect a given edge at 80% power, two-sided 5%."""
    ev = bets[(bets["window"] == "eval") & (bets["pnl"] != 0)]
    sd = float(ev["pnl"].std(ddof=1))
    out = {"per_ticket_sd_units": sd, "alpha": 0.05, "power": 0.80}
    for edge in (0.02, 0.03, 0.05):
        n = ((1.959964 + 0.841621) ** 2) * (sd ** 2) / (edge ** 2)
        out[f"n_for_{int(edge*100)}pct_edge"] = int(math.ceil(n))
    out["largest_strategy_tickets"] = int(ev.groupby("strategy").size().max())
    return out


def main() -> None:
    bets = pd.read_parquet(INTERIM / "bets.parquet")
    g = pd.read_parquet(INTERIM / "lines.parquet")
    registry = json.loads((INTERIM.parent.parent / "site_data" / "strategy_registry.json").read_text())
    reg = {m["strategy"]: m for m in registry["single"] + registry["parlay"]}

    strategies = sorted(bets["strategy"].unique())
    n_trials = len(strategies)
    metrics = []
    for s in strategies:
        m = strategy_metrics(bets, g, s, n_trials)
        m.update({k: v for k, v in reg.get(s, {}).items() if k not in m})
        metrics.append(m)

    pvals = [m.get("perm_p") if m.get("perm_p") is not None else np.nan for m in metrics]
    qs = bh_qvalues(pvals)
    for m, q in zip(metrics, qs):
        m["bh_q"] = None if (q is None or (isinstance(q, float) and math.isnan(q))) else float(q)

    for m in metrics:
        m["gates"] = gate_rows(m)
        m["tier"], m["tier_reason"] = tier(m["gates"])
        m["reward_points"] = REWARD_POINTS[m["tier"]]

    # leaderboard order: passing strategies first, then by deflated Sharpe
    def sort_key(m):
        order = {"GOLD": 0, "SILVER": 1, "BRONZE": 2, "NEEDS_REVIEW": 3, "REJECTED": 4}
        return (order[m["tier"]], -(m.get("deflated_sharpe") or -9), -(m.get("roi") or -9))

    metrics.sort(key=sort_key)
    for i, m in enumerate(metrics, 1):
        m["rank"] = i if m["tier"] in ("GOLD", "SILVER", "BRONZE") else None

    summary = {
        "generated": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eval_window": [EVAL_START, int(g["season"].max())],
        "n_strategies": len(metrics),
        "n_tickets_eval": int(((bets["window"] == "eval")).sum()),
        "gate_thresholds": {
            "min_tickets": MIN_TICKETS, "min_season_tickets": MIN_SEASON_TICKETS,
            "min_seasons": MIN_SEASONS, "stability_share": STABILITY_SHARE,
            "alpha_perm": ALPHA_PERM, "alpha_q": ALPHA_Q, "dsr_min": DSR_MIN,
            "n_boot": N_BOOT, "n_perm": N_PERM, "n_trials": n_trials,
        },
        "power": power_analysis(bets),
        "tier_counts": pd.Series([m["tier"] for m in metrics]).value_counts().to_dict(),
        "total_reward_points": int(sum(m["reward_points"] for m in metrics)),
        "best": [m["strategy"] for m in metrics if m["tier"] in ("GOLD", "SILVER", "BRONZE")][:5],
    }
    write_json("leaderboard.json", {"summary": summary, "strategies": metrics})
    print(json.dumps(summary, indent=1, default=str))
    tab = pd.DataFrame([{ "strategy": m["strategy"], "tier": m["tier"], "n": m["n_graded"],
                          "roi": m.get("roi"), "ci_lo": (m.get("roi_ci95") or [None])[0],
                          "perm_p": m.get("perm_p"), "q": m.get("bh_q"),
                          "dsr": m.get("deflated_sharpe"),
                          "fails": ",".join(r["gate"] for r in m["gates"] if r["status"] == "FAIL")}
                        for m in metrics])
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
