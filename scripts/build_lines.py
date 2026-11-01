#!/usr/bin/env python3
"""Line origination: build our own spread / total / moneyline, and grade it.

Outputs data/derived/lines.json  (consumed by docs/lines.html).

Convention note (verified empirically, see data_integrity.json):
  nflverse `spread_line` is POSITIVE when the HOME team is favoured, i.e. it is
  the market's expected home margin. The standard betting notation for the same
  game is home_line = -spread_line (negative = home favoured). This project uses
  home_line for settlement and spread_line for the market's expected margin.
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

OUT = nc.DERIVED / "lines.json"
SIGMA = 13.6  # empirical sd of NFL game margins; refitted below from residuals


def md(x, n=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), n)


def load_eval():
    g = nc.load_games()
    p = pd.read_csv(nc.DERIVED / "predictions.csv")
    m = g.merge(p[["game_id", "pred_margin", "pred_total", "pred_home_score",
                   "pred_away_score"]], on="game_id", how="left")
    m = m[m.pred_margin.notna()].copy()
    # market-implied expected numbers
    m["mkt_margin"] = m["spread_line"]              # positive => home favoured
    m["mkt_total"] = m["total_line"]
    return m


def calibration_by_season(m):
    rows = []
    for season, s in m.groupby("season"):
        s = s.dropna(subset=["spread_line", "total_line"])
        if len(s) < 40:
            continue
        rows.append({
            "season": int(season),
            "games": int(len(s)),
            "model_mae_margin": md((s.pred_margin - s.home_margin).abs().mean()),
            "market_mae_margin": md((s.spread_line - s.home_margin).abs().mean()),
            "model_mae_total": md((s.pred_total - s.total).abs().mean()),
            "market_mae_total": md((s.total_line - s.total).abs().mean()),
            "model_bias_margin": md((s.pred_margin - s.home_margin).mean()),
            "model_bias_total": md((s.pred_total - s.total).mean()),
            "corr_model_market_margin": md(s.pred_margin.corr(s.spread_line), 4),
            "corr_model_market_total": md(s.pred_total.corr(s.total_line), 4),
        })
    return rows


def edge_curves(m):
    """ATS / totals performance as the required model-vs-market edge grows."""
    out = {"spread": [], "total": []}
    d = m.dropna(subset=["spread_line", "home_spread_odds", "away_spread_odds"]).copy()
    d["edge_home"] = d.pred_margin - d.spread_line          # >0 => model prefers home
    d["bet_home"] = (d.edge_home > 0) == (d.home_margin + d.home_line > 0) * 0 - 0  # placeholder
    for thr in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
        sel = d[(d.edge_home.abs() >= thr) & (d.home_margin + d.home_line != 0)]
        if len(sel) == 0:
            continue
        side_home = sel.edge_home > 0
        won = ((sel.home_margin + sel.home_line) > 0) == side_home
        odds = np.where(side_home, sel.home_spread_odds, sel.away_spread_odds)
        units = np.where(won, [nc.american_to_decimal(o) - 1 for o in odds], -1.0)
        out["spread"].append({
            "threshold_pts": thr, "bets": int(len(sel)),
            "hit_rate": md(float(won.mean()), 4),
            "roi": md(float(np.mean(units)), 4),
            "avg_odds": md(float(np.mean(odds)), 1),
            "wilson_lo": md(nc.wilson(int(won.sum()), len(sel))[0], 4),
            "wilson_hi": md(nc.wilson(int(won.sum()), len(sel))[1], 4),
            "p_value": md(nc.binom_p_greater(int(won.sum()), len(sel), 0.5238), 4),
        })

    t = m.dropna(subset=["total_line", "over_odds", "under_odds"]).copy()
    t["edge_over"] = t.pred_total - t.total_line
    for thr in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
        sel = t[(t.edge_over.abs() >= thr) & (t.total != t.total_line)]
        if len(sel) == 0:
            continue
        side_over = sel.edge_over > 0
        won = ((sel.total - sel.total_line) > 0) == side_over
        odds = np.where(side_over, sel.over_odds, sel.under_odds)
        units = np.where(won, [nc.american_to_decimal(o) - 1 for o in odds], -1.0)
        out["total"].append({
            "threshold_pts": thr, "bets": int(len(sel)),
            "hit_rate": md(float(won.mean()), 4),
            "roi": md(float(np.mean(units)), 4),
            "avg_odds": md(float(np.mean(odds)), 1),
            "wilson_lo": md(nc.wilson(int(won.sum()), len(sel))[0], 4),
            "wilson_hi": md(nc.wilson(int(won.sum()), len(sel))[1], 4),
            "p_value": md(nc.binom_p_greater(int(won.sum()), len(sel), 0.5238), 4),
        })
    return out


def moneyline_calibration(m):
    d = m.dropna(subset=["home_moneyline", "away_moneyline", "spread_line"]).copy()
    d["p_home"] = norm.cdf(d.pred_margin / SIGMA)
    d["p_mkt"] = d.home_moneyline.map(nc.american_to_prob)
    d["p_mkt"] = d.p_mkt / (d.p_mkt + d.away_moneyline.map(nc.american_to_prob))
    d["home_win"] = (d.home_margin > 0).astype(int)
    d["tie"] = (d.home_margin == 0).astype(int)
    d["bin"] = pd.cut(d.p_home, bins=[0, .2, .3, .4, .5, .6, .7, .8, 1.0])
    rows = []
    for b, s in d.groupby("bin", observed=True):
        rows.append({"bucket": str(b), "n": int(len(s)),
                     "pred_prob": md(s.p_home.mean(), 4),
                     "market_prob": md(s.p_mkt.mean(), 4),
                     "actual_home_win": md(s.home_win.mean(), 4)})
    # proper scores on non-push games
    dd = d[d.tie == 0]
    brier_model = float(((dd.p_home - dd.home_win) ** 2).mean())
    brier_mkt = float(((dd.p_mkt - dd.home_win) ** 2).mean())
    ll_model = float(-np.mean(dd.home_win * np.log(dd.p_home.clip(1e-6, 1 - 1e-6))
                              + (1 - dd.home_win) * np.log((1 - dd.p_home).clip(1e-6, 1 - 1e-6))))
    ll_mkt = float(-np.mean(dd.home_win * np.log(dd.p_mkt.clip(1e-6, 1 - 1e-6))
                            + (1 - dd.home_win) * np.log((1 - dd.p_mkt).clip(1e-6, 1 - 1e-6))))
    # ML betting at thresholds
    bets = []
    d["edge_home"] = d.p_home - d.p_mkt
    for thr in [0.02, 0.03, 0.05, 0.08]:
        sel = d[(d.edge_home.abs() >= thr) & (d.tie == 0)]
        if not len(sel):
            continue
        side_home = sel.edge_home > 0
        won = (sel.home_margin > 0) == side_home
        odds = np.where(side_home, sel.home_moneyline, sel.away_moneyline)
        units = np.where(won, [nc.american_to_decimal(o) - 1 for o in odds], -1.0)
        bets.append({"threshold_prob": thr, "bets": int(len(sel)),
                     "hit_rate": md(float(won.mean()), 4),
                     "roi": md(float(np.mean(units)), 4),
                     "avg_odds": md(float(np.mean(odds)), 1)})
    return {"buckets": rows, "brier_model": md(brier_model, 5),
            "brier_market": md(brier_mkt, 5), "logloss_model": md(ll_model, 5),
            "logloss_market": md(ll_mkt, 5),
            "games_scored": int(len(d)), "bets": bets}


def current_slate():
    """Originated lines for games that have not been played yet."""
    g_played = nc.load_games()
    und = nc.load_unplayed()
    if und.empty:
        return {"rows": [], "asof": None}
    r = nc.current_ratings(g_played)
    rows = []
    for _, u in und.iterrows():
        rd = float((u.home_rest if pd.notna(u.home_rest) else 7) -
                   (u.away_rest if pd.notna(u.away_rest) else 7))
        rd = max(min(rd, 14), -14)
        ph, pa = nc.predict_with(r, u.home_team, u.away_team, rd)
        margin = ph - pa
        total = ph + pa
        p_home = float(norm.cdf(margin / SIGMA))
        our_line = -round(margin * 2) / 2      # standard notation, nearest 0.5
        our_total = round(total * 2) / 2
        has_mkt = pd.notna(u.spread_line)
        rows.append({
            "game_id": u.game_id, "gameday": str(u.gameday)[:10],
            "week": int(u.week) if pd.notna(u.week) else None,
            "away": u.away_team, "home": u.home_team,
            "our_spread": our_line, "our_total": our_total,
            "our_home_ml": nc.moneyline_odds(p_home),
            "our_away_ml": nc.moneyline_odds(1 - p_home),
            "our_home_win_prob": md(p_home, 4),
            "market_spread": md(u.spread_line, 1) if has_mkt else None,
            "market_total": md(u.total_line, 1) if has_mkt else None,
            "market_home_ml": md(u.home_moneyline, 0) if pd.notna(u.home_moneyline) else None,
            "market_away_ml": md(u.away_moneyline, 0) if pd.notna(u.away_moneyline) else None,
            "edge_home_pts": md(our_line - (-u.spread_line), 2) if has_mkt else None,
            "edge_total_pts": md(our_total - u.total_line, 2) if pd.notna(u.total_line) else None,
            "verified": bool(has_mkt),
        })
    return {"rows": rows, "asof": str(r["asof"])[:10],
            "hfa": md(r["hfa"], 2), "rest_coef": md(r["rest_coef"], 3),
            "ratings": [{"team": t, "off": md(r["off"][t], 2), "def": md(r["def"][t], 2),
                         "net": md(r["off"][t] - r["def"][t], 2)} for t in r["teams"]]}


def main():
    m = load_eval()
    resid = (m.pred_margin - m.home_margin).dropna()
    payload = {
        "sigma_resid": md(resid.std(), 3),
        "sigma_used": SIGMA,
        "n_games_predicted": int(len(m)),
        "season_min": int(m.season.min()), "season_max": int(m.season.max()),
        "overall": {
            "model_mae_margin": md((m.pred_margin - m.home_margin).abs().mean()),
            "market_mae_margin": md((m.spread_line - m.home_margin).abs().mean()),
            "model_mae_total": md((m.pred_total - m.total).abs().mean()),
            "market_mae_total": md((m.total_line - m.total).abs().mean()),
            "corr_model_market_margin": md(m.pred_margin.corr(m.spread_line), 4),
            "corr_model_market_total": md(m.pred_total.corr(m.total_line), 4),
        },
        "by_season": calibration_by_season(m),
        "edge_curves": edge_curves(m),
        "moneyline": moneyline_calibration(m),
        "slate": current_slate(),
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: payload[k] for k in ("overall", "sigma_resid")}, indent=2))
    print("season rows", len(payload["by_season"]))
    print("slate rows", len(payload["slate"]["rows"]),
          "with market", sum(1 for r in payload["slate"]["rows"] if r["verified"]))
    print(json.dumps(payload["edge_curves"], indent=1)[:700])
    print(json.dumps(payload["moneyline"]["bets"], indent=1)[:600])


if __name__ == "__main__":
    main()
