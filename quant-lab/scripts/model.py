#!/usr/bin/env python3
"""
model.py — line origination.

Design (all walk-forward; no future information ever enters a prediction):

    home_points = mu + HFA + OFF[home] + DEF[away]
    away_points = mu        + OFF[away] + DEF[home]

* OFF[t] = points per game a team's offence adds above league average.
* DEF[t] = points per game a team's defence concedes above league average (positive = leaky).
* Both are ridge-shrunk toward 0 so a 1-game sample cannot create a wild rating.
* Evidence is exponentially decayed by age (default half-life 45 days) and the previous
  season is carried in with a weight < 1, which is what makes week 1 usable.

Derived lines:
    originated_spread_home = predicted home margin           (+ => home favoured)
    originated_total       = predicted home + away points
    originated_home_ml    = fair American odds from P(home win) with residual sigma

Sigma (margin error) is estimated from the model's own out-of-sample residuals, so the
win probability is calibrated to observed error rather than to a textbook constant.

Every published number is a deterministic function of data/processed/games.json.
"""
import json, math, os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")

# ----------------------------------------------------------------------------- helpers
def american_to_decimal(a):
    a = float(a)
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / -a)


def decimal_to_american(d):
    if d >= 2.0:
        return round((d - 1.0) * 100)
    return round(-100.0 / (d - 1.0))


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def parse_day(s):
    y, m, d = (int(x) for x in s.split("-"))
    return y * 372 + m * 31 + d   # monotone day index; only differences matter


class Ratings:
    """Weighted ridge ratings for a set of completed games."""

    def __init__(self, half_life_days=45.0, prior_season_weight=0.35, ridge=6.0):
        self.hl = half_life_days
        self.psw = prior_season_weight
        self.ridge = ridge

    def fit(self, train, ref_day, ref_season, teams):
        self.teams = teams
        idx = {t: i for i, t in enumerate(teams)}
        nT = len(teams)
        rows, ys, ws = [], [], []
        hfa_rows, off_h, def_a, off_a, def_h = [], [], [], [], []
        for g in train:
            age = max(ref_day - parse_day(g["gameday"]), 0)
            w = math.exp(-math.log(2) * age / self.hl)
            if g["season"] < ref_season:
                w *= self.psw
            if w < 1e-4:
                continue
            # home row
            rows.append((1, idx[g["home"]], idx[g["away"]]))
            hfa_rows.append(1.0)
            ys.append(g["home_score"]); ws.append(w)
            # away row
            rows.append((0, idx[g["away"]], idx[g["home"]]))
            hfa_rows.append(0.0)
            ys.append(g["away_score"]); ws.append(w)
        n = len(ys)
        X = np.zeros((n, 2 + 2 * nT))
        X[:, 0] = 1.0
        for i, (is_home, off, dfn) in enumerate(rows):
            X[i, 1] = hfa_rows[i]
            X[i, 2 + off] = 1.0
            X[i, 2 + nT + dfn] = 1.0
        y = np.array(ys, dtype=float)
        w = np.array(ws, dtype=float)
        sw = np.sqrt(w)
        Xw = X * sw[:, None]
        yw = y * sw
        A = Xw.T @ Xw
        pen = np.full(X.shape[1], self.ridge)
        pen[0] = 1e-6   # intercept unpenalised
        pen[1] = 1e-6   # HFA unpenalised
        A += np.diag(pen)
        b = Xw.T @ yw
        theta = np.linalg.solve(A, b)
        self.mu = theta[0]
        self.hfa = theta[1]
        off = theta[2:2 + nT]
        dfn = theta[2 + nT:2 + 2 * nT]
        self.off = {t: float(off[i]) for t, i in idx.items()}
        self.dfn = {t: float(dfn[i]) for t, i in idx.items()}
        self.idx = idx
        return self

    def predict(self, home, away):
        h = self.mu + self.hfa + self.off[home] + self.dfn[away]
        a = self.mu + self.off[away] + self.dfn[home]
        return h, a


def fit_predict_walkforward(games, half_life=45.0, psw=0.35, ridge=6.0):
    """Return one prediction per completed game with a market line, using only earlier games."""
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    out = []
    by_key = {}
    for g in games:
        by_key.setdefault((g["season"], g["week"]), []).append(g)
    errs = []          # out-of-sample margin errors, used for sigma
    for (season, week) in sorted(by_key):
        wk = sorted(by_key[(season, week)], key=lambda x: (x["gameday"], x.get("gametime") or "00:00"))
        ref_day = parse_day(wk[0]["gameday"])
        train = [g for g in games if parse_day(g["gameday"]) < ref_day]
        if len(train) < 200:
            continue
        m = Ratings(half_life, psw, ridge).fit(train, ref_day, season, teams)
        # estimate margin sigma from the model's own recent out-of-sample errors
        sigma = 13.8
        if len(errs) >= 60:
            sigma = float(np.std(errs[-400:], ddof=1))
        for g in wk:
            hp, ap = m.predict(g["home"], g["away"])
            pred_margin = hp - ap
            pred_total = hp + ap
            p_home = norm_cdf(pred_margin / sigma)
            errs.append(g["home_margin"] - pred_margin)
            out.append({
                "game_id": g["game_id"], "season": season, "week": week, "gameday": g["gameday"],
                "home": g["home"], "away": g["away"],
                "home_score": g["home_score"], "away_score": g["away_score"],
                "home_margin": g["home_margin"], "total_points": g["total_points"],
                "market": g["market"],
                "model_margin": round(pred_margin, 2),
                "model_total": round(pred_total, 2),
                "model_home_pts": round(hp, 2),
                "model_away_pts": round(ap, 2),
                "p_home": round(p_home, 4),
                "sigma": round(sigma, 2),
                "ratings": {"off_home": round(m.off[g["home"]], 2), "off_away": round(m.off[g["away"]], 2),
                            "def_home": round(m.dfn[g["home"]], 2), "def_away": round(m.dfn[g["away"]], 2)},
            })
    return out


def sigma_summary(preds):
    e = [p["home_margin"] - p["model_margin"] for p in preds]
    return {"n": len(e), "mae": round(float(np.mean(np.abs(e))), 3), "rmse": round(float(np.sqrt(np.mean(np.square(e)))), 3),
            "sigma": round(float(np.std(e, ddof=1)), 3)}


def originate_board(games, all_games, season, weeks, params):
    """Originated lines for future weeks: fit on everything known, predict the board."""
    teams = sorted({g["home"] for g in all_games} | {g["away"] for g in all_games})
    last_played = max(all_games, key=lambda g: parse_day(g["gameday"]))
    ref_day = parse_day(last_played["gameday"])
    m = Ratings(params["half_life"], params["psw"], params["ridge"]).fit(all_games, ref_day, season, teams)
    board = []
    for g in games:
        if g["season"] != season or g["week"] not in weeks:
            continue
        hp, ap = m.predict(g["home"], g["away"])
        board.append({
            "game_id": g["game_id"], "week": g["week"], "gameday": g["gameday"], "gametime": g.get("gametime"),
            "home": g["home"], "away": g["away"],
            "orig_spread_home": round(hp - ap, 2),
            "orig_total": round(hp + ap, 2),
            "orig_home_pts": round(hp, 2), "orig_away_pts": round(ap, 2),
            "market": g["market"],
            "off_home": round(m.off[g["home"]], 2), "off_away": round(m.off[g["away"]], 2),
            "def_home": round(m.dfn[g["home"]], 2), "def_away": round(m.dfn[g["away"]], 2),
        })
    return board, m


def main():
    games = json.load(open(os.path.join(PROC, "games.json")))
    reg = [g for g in games if g["game_type"] == "REG"]
    with_market = [g for g in reg if g["market"]["spread_home"] is not None and g["market"]["total"] is not None]

    # ---- hyper-parameter search on the RESEARCH window only (2002-2015) -------------
    research = [g for g in with_market if g["season"] <= 2015]
    grid = []
    for hl in (30.0, 45.0, 60.0, 90.0):
        for psw in (0.2, 0.35, 0.5):
            for ridge in (2.0, 6.0, 12.0):
                preds = fit_predict_walkforward(research, hl, psw, ridge)
                if len(preds) < 500:
                    continue
                e = np.abs([p["home_margin"] - p["model_margin"] for p in preds])
                et = np.abs([p["total_points"] - p["model_total"] for p in preds])
                grid.append({"half_life": hl, "psw": psw, "ridge": ridge,
                             "mae_margin": round(float(e.mean()), 4), "mae_total": round(float(et.mean()), 4),
                             "n": len(preds)})
    grid.sort(key=lambda r: r["mae_margin"] + r["mae_total"])
    best = grid[0]
    print("best params (2002-2015 research window):", best)
    params = {"half_life": best["half_life"], "psw": best["psw"], "ridge": best["ridge"]}

    # ---- full walk-forward on every season with a market line -----------------------
    preds = fit_predict_walkforward(with_market, **params)
    print("walk-forward predictions:", len(preds))
    print("residuals:", sigma_summary(preds))

    # market benchmark errors (how good is the closing line?) — context for the model
    mk = [p for p in preds if p["market"]["spread_home"] is not None]
    mae_mkt = float(np.mean([abs(p["home_margin"] - p["market"]["spread_home"]) for p in mk]))
    mae_mod = float(np.mean([abs(p["home_margin"] - p["model_margin"]) for p in mk]))
    mae_mkt_t = float(np.mean([abs(p["total_points"] - p["market"]["total"]) for p in mk]))
    mae_mod_t = float(np.mean([abs(p["total_points"] - p["model_total"]) for p in mk]))

    # ---- board for future weeks ----------------------------------------------------
    upcoming = json.load(open(os.path.join(PROC, "upcoming.json")))
    board, _ = originate_board(upcoming, reg, 2026, (9, 10), params)
    print("board games:", len(board))

    json.dump(preds, open(os.path.join(PROC, "predictions.json"), "w"), separators=(",", ":"))
    json.dump({"params": params, "grid": grid[:12], "grid_size": len(grid),
               "sigma": sigma_summary(preds),
               "mae_market_spread": round(mae_mkt, 3), "mae_model_spread": round(mae_mod, 3),
               "mae_market_total": round(mae_mkt_t, 3), "mae_model_total": round(mae_mod_t, 3),
               "n": len(mk)},
              open(os.path.join(PROC, "model_meta.json"), "w"), indent=1)
    json.dump(board, open(os.path.join(PROC, "board.json"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
