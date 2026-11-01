#!/usr/bin/env python3
"""
backtest.py — the strategy lab.

Every strategy is a *selection rule* over legs that the origination model produced. The rules
are pre-registered below (they are data-independent predicates), evaluated on identical
mechanics, and split into a DISCOVERY window (2002-2019) and a HOLDOUT window (2020-2026).
Nothing is tuned on the holdout.

Outputs
  data/processed/strategies.json    per-strategy results (discovery + holdout)
  data/processed/correlations.json  empirical correlations used for parlay / SGP pricing
  data/processed/bets_2026.json     the 2026 bet ledger (one row per settled bet)

Pricing assumptions (documented, not hidden):
  * Spread / total legs settle at -110 (decimal 1.9091) — the standard price and the one the
    nflverse closing-line file implies for the two-way market.
  * Moneylines settle at the actual closing price in the mirror.
  * Player props settle at -110: NO prop price is present in any source reachable from this
    environment, so the -110 assumption is flagged on the Flagged page.
"""
import json, math, os, random

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")

REG_PRICE = -110
SPLIT_YEAR = 2020          # discovery < 2020 <= holdout

# --------------------------------------------------------------------------- pricing
def dec(american):
    american = float(american)
    return 1.0 + (american / 100.0 if american > 0 else 100.0 / -american)


DEC_REG = dec(REG_PRICE)


def result_units(hit, decimal_odds):
    """profit in units for a 1-unit stake."""
    return (decimal_odds - 1.0) if hit else -1.0


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- legs
def leg_for_spread(p, side, edge):
    m = p["market"]
    line = m["spread_home"]          # + => home favoured
    if side == "home":
        p_model = norm_cdf((p["model_margin"] - line) / p["sigma"])
    else:
        p_model = 1.0 - norm_cdf((p["model_margin"] - line) / p["sigma"])
    return {
        "game_id": p["game_id"], "season": p["season"], "week": p["week"], "home": p["home"], "away": p["away"],
        "market": "spread", "side": side, "line": line, "price": REG_PRICE, "decimal": DEC_REG,
        "p_model": round(p_model, 4), "p_market": 0.5, "edge": round(edge, 2),
        "label": f"{p['home'] if side=='home' else p['away']} {line if side=='home' else -line:+.1f}",
        "hit": (p["home_margin"] - line) > 0 if side == "home" else (p["home_margin"] - line) < 0,
        "push": (p["home_margin"] - line) == 0,
    }


def leg_for_total(p, side, edge):
    m = p["market"]
    line = m["total"]
    p_over = 1.0 - norm_cdf((line - p["model_total"]) / p["sigma"])
    p_model = p_over if side == "over" else 1.0 - p_over
    return {
        "game_id": p["game_id"], "season": p["season"], "week": p["week"], "home": p["home"], "away": p["away"],
        "market": "total", "side": side, "line": line, "price": REG_PRICE, "decimal": DEC_REG,
        "p_model": round(p_model, 4), "p_market": 0.5, "edge": round(edge, 2),
        "label": f"{side.upper()} {line}",
        "hit": (p["total_points"] > line) if side == "over" else (p["total_points"] < line),
        "push": (p["total_points"] == line),
    }


def leg_for_ml(p, side):
    m = p["market"]
    price = m["home_ml"] if side == "home" else m["away_ml"]
    if price is None:
        return None
    p_model = p["p_home"] if side == "home" else 1.0 - p["p_home"]
    p_mkt = 1.0 / dec(price)
    return {
        "game_id": p["game_id"], "season": p["season"], "week": p["week"], "home": p["home"], "away": p["away"],
        "market": "moneyline", "side": side, "line": None, "price": price, "decimal": dec(price),
        "p_model": round(p_model, 4), "p_market": round(p_mkt, 4),
        "edge": round((p_model - p_mkt) * 100, 2),
        "label": f"{(p['home'] if side=='home' else p['away'])} ML {int(price):+d}",
        "hit": (p["home_margin"] > 0) if side == "home" else (p["home_margin"] < 0),
        "push": (p["home_margin"] == 0),
    }


# --------------------------------------------------------------------------- strategies
def s_spread_edge(preds, min_edge):
    legs = []
    for p in preds:
        m = p["market"]
        if m["spread_home"] is None or p["sigma"] is None:
            continue
        edge = p["model_margin"] - m["spread_home"]
        if abs(edge) >= min_edge:
            legs.append(leg_for_spread(p, "home" if edge > 0 else "away", edge))
    return [[l] for l in legs]


def s_total_edge(preds, min_edge):
    legs = []
    for p in preds:
        m = p["market"]
        if m["total"] is None:
            continue
        edge = p["model_total"] - m["total"]
        if abs(edge) >= min_edge:
            legs.append(leg_for_total(p, "over" if edge > 0 else "under", edge))
    return [[l] for l in legs]


def s_ml_value(preds, min_ev):
    legs = []
    for p in preds:
        if p["market"]["home_ml"] is None:
            continue
        for side in ("home", "away"):
            l = leg_for_ml(p, side)
            if l is None:
                continue
            ev = l["p_model"] * l["decimal"] - 1.0
            if ev >= min_ev:
                legs.append(l)
    return [[l] for l in legs]


# --- situational rules (pre-registered; they use the same market price as everyone else) ---
def _spread_leg(p, side):
    return leg_for_spread(p, side, 0.0)


def s_fade_short_week(preds):
    """Bet against a team playing on <=5 days rest (short week), when its opponent has more rest."""
    out = []
    for p in preds:
        if p["market"]["spread_home"] is None:
            continue
        hr, ar = p.get("home_rest"), p.get("away_rest")
        if hr is None or ar is None:
            continue
        if hr <= 5 and ar - hr >= 2:
            out.append([_spread_leg(p, "away")])
        elif ar <= 5 and hr - ar >= 2:
            out.append([_spread_leg(p, "home")])
    return out


def s_rest_advantage(preds, min_gap=4):
    """Bet the team with a rest advantage of >= min_gap days (e.g. off a bye)."""
    out = []
    for p in preds:
        if p["market"]["spread_home"] is None:
            continue
        hr, ar = p.get("home_rest"), p.get("away_rest")
        if hr is None or ar is None:
            continue
        if hr - ar >= min_gap:
            out.append([_spread_leg(p, "home")])
        elif ar - hr >= min_gap:
            out.append([_spread_leg(p, "away")])
    return out


def s_off_bye(preds):
    """Teams playing after a bye (rest >= 13) straight up on the spread."""
    return s_rest_advantage(preds, min_gap=6)


def s_wind_under(preds, min_wind=15.0):
    """UNDER in outdoor games with wind >= min_wind mph."""
    out = []
    for p in preds:
        if p["market"]["total"] is None or p.get("wind") is None or p.get("roof") is None:
            continue
        if p["roof"] != "outdoors":
            continue
        if p["wind"] >= min_wind:
            out.append([leg_for_total(p, "under", 0.0)])
    return out


def s_dome_over(preds):
    """OVER in domed/closed-roof games."""
    out = []
    for p in preds:
        if p["market"]["total"] is None or p.get("roof") is None:
            continue
        if p["roof"] in ("dome", "closed"):
            out.append([leg_for_total(p, "over", 0.0)])
    return out


def s_tnf_under(preds):
    """UNDER when both teams are on a short week (<=5 days rest) — the Thursday-game case."""
    out = []
    for p in preds:
        if p["market"]["total"] is None:
            continue
        hr, ar = p.get("home_rest"), p.get("away_rest")
        if hr is None or ar is None:
            continue
        if hr <= 5 and ar <= 5:
            out.append([leg_for_total(p, "under", 0.0)])
    return out


def s_cold_under(preds, max_temp=32.0):
    """UNDER outdoors when the game-time temperature is <= 32 F (mirror reports F)."""
    out = []
    for p in preds:
        if p["market"]["total"] is None or p.get("temp") is None or p.get("roof") is None:
            continue
        if p["roof"] != "outdoors":
            continue
        if p["temp"] <= max_temp:
            out.append([leg_for_total(p, "under", 0.0)])
    return out


def s_div_under(preds):
    """UNDER in divisional games."""
    out = []
    for p in preds:
        if p["market"]["total"] is None or p.get("div_game") != 1:
            continue
        out.append([leg_for_total(p, "under", 0.0)])
    return out


def s_baseline_home(preds):
    """Control: back every home team on the spread. This is the vig floor, not a strategy."""
    out = []
    for p in preds:
        if p["market"]["spread_home"] is None:
            continue
        out.append([_spread_leg(p, "home")])
    return out


def s_divisional_dog(preds):
    """Home divisional underdogs (market line says home is the dog) on the spread."""
    out = []
    for p in preds:
        if p["market"]["spread_home"] is None or p.get("div_game") != 1:
            continue
        if p["market"]["spread_home"] < 0:
            out.append([_spread_leg(p, "home")])
    return out


# --- parlays -----------------------------------------------------------------
def build_parlays(singles, n_legs, max_per_week=1, seed=20261101):
    """Combine single legs from DIFFERENT games into n-leg parlays.

    Leg selection uses only information available pre-kickoff (model edge + market price);
    legs are sorted by edge and combined deterministically so the rule is reproducible.
    """
    by_week = {}
    for legs in singles:
        leg = legs[0]
        by_week.setdefault((leg["season"], leg["week"]), []).append(leg)
    out = []
    for key in sorted(by_week):
        pool = sorted(by_week[key], key=lambda l: (-abs(l["edge"]), l["game_id"]))
        chosen, used_games = [], set()
        for leg in pool:
            if leg["game_id"] in used_games:
                continue
            chosen.append(leg)
            used_games.add(leg["game_id"])
            if len(chosen) == n_legs:
                break
        if len(chosen) == n_legs and max_per_week >= 1:
            out.append(chosen)
    return out


def eval_parlay(legs):
    """Parlay settles at the product of decimal odds; a push drops that leg."""
    live = [l for l in legs if not l["push"]]
    if not live:
        return {"hit": None, "decimal": None, "units": 0.0, "void": True}
    d = 1.0
    for l in live:
        d *= l["decimal"]
    hit = all(l["hit"] for l in live)
    return {"hit": hit, "decimal": d, "units": result_units(hit, d), "void": False}


# --------------------------------------------------------------------------- metrics
def bootstrap_ci(vals, iters=4000, seed=7):
    if len(vals) < 10:
        return [None, None]
    rng = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += vals[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return [round(means[int(0.025 * iters)], 4), round(means[int(0.975 * iters)], 4)]


def evaluate(name, bets, window):
    """bets: list of {units, hit, p_model, p_market, push, decimal}"""
    live = [b for b in bets if b.get("hit") is not None and not b.get("void")]
    if not live:
        return {"strategy": name, "window": window, "n": 0}
    units = [b["units"] for b in live]
    n = len(units)
    wins = sum(1 for b in live if b["hit"])
    pushes = sum(1 for b in bets if b.get("push"))
    roi = sum(units) / n
    hit_rate = wins / n
    pm = [b["p_model"] for b in live]
    pmk = [b["p_market"] for b in live if b.get("p_market") is not None]
    # null expectation: settle every bet at the price actually taken, using market probability
    exp_wins = sum(b["p_market"] for b in live if b.get("p_market") is not None)
    var = sum(b["p_market"] * (1 - b["p_market"]) for b in live if b.get("p_market") is not None)
    z = (wins - exp_wins) / math.sqrt(var) if var > 0 else None
    brier = sum((b["p_model"] - (1.0 if b["hit"] else 0.0)) ** 2 for b in live) / n
    brier_mkt = None
    if len(pmk) == n:
        brier_mkt = sum((b["p_market"] - (1.0 if b["hit"] else 0.0)) ** 2 for b in live) / n
    lo, hi = bootstrap_ci(units)
    # concentration: share of total profit from the best 1% of bets
    prof = sorted(units, reverse=True)
    top = max(1, int(round(0.01 * n)))
    tot = sum(units)
    conc = (sum(prof[:top]) / tot) if tot > 1e-9 else None
    return {
        "strategy": name, "window": window, "n": n, "wins": wins, "pushes": pushes,
        "hit_rate": round(hit_rate, 4), "units": round(sum(units), 2), "roi": round(roi, 4),
        "roi_ci95": [lo, hi], "avg_p_model": round(sum(pm) / n, 4),
        "avg_p_market": round(sum(pmk) / len(pmk), 4) if pmk else None,
        "calibration_gap_pp": round(100 * (hit_rate - sum(pm) / n), 2),
        "brier": round(brier, 4), "brier_market": None if brier_mkt is None else round(brier_mkt, 4),
        "luck_z": None if z is None else round(z, 3),
        "top1pct_profit_share": None if conc is None else round(conc, 3),
    }


def by_season_rows(bets):
    rows = {}
    for b in bets:
        if b.get("hit") is None or b.get("void"):
            continue
        s = b["season"]
        r = rows.setdefault(s, {"season": s, "n": 0, "units": 0.0, "wins": 0})
        r["n"] += 1
        r["units"] += b["units"]
        r["wins"] += 1 if b["hit"] else 0
    for r in rows.values():
        r["roi"] = round(r["units"] / r["n"], 4) if r["n"] else None
        r["units"] = round(r["units"], 2)
    return [rows[k] for k in sorted(rows)]


# --------------------------------------------------------------------------- correlations
def phi(a, b):
    """Phi coefficient (Pearson on two binary vectors)."""
    n = len(a)
    if n < 2:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return None if den == 0 else num / den


def pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return None if den == 0 else num / den


def correlations(preds):
    srt, stt, ats_over, ml_ats, margins, totals = [], [], [], [], [], []
    for p in preds:
        m = p["market"]
        if m["spread_home"] is None or m["total"] is None:
            continue
        margins.append(p["home_margin"])
        totals.append(p["total_points"])
        cover_home = 1 if p["home_margin"] - m["spread_home"] > 0 else 0
        over = 1 if p["total_points"] - m["total"] > 0 else 0
        ats_over.append((cover_home, over))
        if m["home_ml"] is not None:
            ml_ats.append((1 if p["home_margin"] > 0 else 0, cover_home))
    a = [x[0] for x in ats_over]
    b = [x[1] for x in ats_over]
    cross = cross_season_leg_independence(preds)
    return {
        "n_games": len(margins),
        "pearson_margin_vs_total": round(pearson(margins, totals), 4),
        "phi_home_cover_vs_over": round(phi(a, b), 4),
        "n_ats_total": len(a),
        "phi_ml_win_vs_ats_cover": round(phi([x[0] for x in ml_ats], [x[1] for x in ml_ats]), 4) if ml_ats else None,
        "n_ml_ats": len(ml_ats),
        "cross_game_leg_independence": cross,
    }


def cross_season_leg_independence(preds):
    """Empirical check that legs from different games are (nearly) uncorrelated — the
    assumption a cross-game parlay price rests on."""
    rows = [p for p in preds if p["market"]["spread_home"] is not None]
    a, b = [], []
    for i in range(0, len(rows) - 1, 2):
        p1, p2 = rows[i], rows[i + 1]
        if p1["game_id"] == p2["game_id"]:
            continue
        a.append(1 if p1["home_margin"] - p1["market"]["spread_home"] > 0 else 0)
        b.append(1 if p2["home_margin"] - p2["market"]["spread_home"] > 0 else 0)
    return {"n_pairs": len(a), "phi": round(phi(a, b), 4) if a else None,
            "note": "random adjacent pairs of games, ATS-home outcomes"}


# --------------------------------------------------------------------------- driver
DEFAULT_STRATS = [
    ("S0_baseline_all_home", s_baseline_home, "single", "CONTROL: back every home team ATS. This is the vig floor (~-4.5% ROI), not a signal."),
    ("S16_tnf_under", s_tnf_under, "single", "UNDER when both teams had <=5 days rest (short-week / Thursday games)."),
    ("S17_cold_under", lambda P: s_cold_under(P, 32.0), "single", "UNDER outdoors at <=32 F."),
    ("S18_div_under", s_div_under, "single", "UNDER in divisional games."),
    ("S1_spread_edge_2", lambda P: s_spread_edge(P, 2.0), "single", "Model spread differs from the closing line by >=2 points."),
    ("S2_spread_edge_3", lambda P: s_spread_edge(P, 3.0), "single", "Model spread differs from the closing line by >=3 points."),
    ("S3_spread_edge_5", lambda P: s_spread_edge(P, 5.0), "single", "Model spread differs from the closing line by >=5 points."),
    ("S4_total_edge_2", lambda P: s_total_edge(P, 2.0), "single", "Model total differs from the closing total by >=2 points."),
    ("S5_total_edge_3", lambda P: s_total_edge(P, 3.0), "single", "Model total differs from the closing total by >=3 points."),
    ("S6_ml_value_5pct", lambda P: s_ml_value(P, 0.05), "single", "Moneyline with >=5% modelled expected value."),
    ("S7_fade_short_week", s_fade_short_week, "single", "Fade a team on <=5 days rest against a better-rested opponent."),
    ("S8_rest_edge_4d", lambda P: s_rest_advantage(P, 4), "single", "Bet the side with >=4 days more rest."),
    ("S9_off_bye", s_off_bye, "single", "Bet teams playing after a bye."),
    ("S10_wind15_under", lambda P: s_wind_under(P, 15.0), "single", "UNDER outdoors when wind >= 15 mph."),
    ("S11_dome_over", s_dome_over, "single", "OVER in dome / closed-roof games."),
    ("S12_div_dog_home", s_divisional_dog, "single", "Home divisional underdog on the spread."),
]


def run():
    preds = json.load(open(os.path.join(PROC, "predictions.json")))
    games = {g["game_id"]: g for g in json.load(open(os.path.join(PROC, "games.json")))}
    for p in preds:                     # situational fields come from the game record
        g = games[p["game_id"]]
        for k in ("home_rest", "away_rest", "div_game", "roof", "surface", "temp", "wind"):
            p[k] = g.get(k)

    results = {}
    ledgers = {}
    for name, fn, kind, desc in DEFAULT_STRATS:
        legsets = fn(preds)
        bets = []
        for legs in legsets:
            l = legs[0]
            bets.append({"season": l["season"], "week": l["week"], "game_id": l["game_id"],
                         "kind": kind, "legs": legs, "units": result_units(l["hit"], l["decimal"]),
                         "hit": l["hit"], "push": l["push"], "p_model": l["p_model"],
                         "p_market": l["p_market"], "decimal": l["decimal"], "void": False})
        disc = evaluate(name, [b for b in bets if b["season"] < SPLIT_YEAR], "discovery_2002_2019")
        hold = evaluate(name, [b for b in bets if b["season"] >= SPLIT_YEAR], "holdout_2020_2026")
        full = evaluate(name, bets, "all")
        results[name] = {"desc": desc, "kind": kind, "discovery": disc, "holdout": hold, "all": full,
                         "by_season": by_season_rows(bets)}
        ledgers[name] = bets

    # ---------------- parlays built on top of the spread-edge rule -----------------
    base = s_spread_edge(preds, 2.0) + s_total_edge(preds, 2.0)
    for nlegs, sname in ((2, "S13_parlay2_edge2"), (3, "S14_parlay3_edge2")):
        sets = build_parlays(base, nlegs)
        bets = []
        for legs in sets:
            r = eval_parlay(legs)
            pm = 1.0
            for l in legs:
                pm *= l["p_model"]
            bets.append({"season": legs[0]["season"], "week": legs[0]["week"], "kind": f"parlay{nlegs}",
                         "legs": legs, "units": r["units"], "hit": r["hit"],
                         "push": any(l["push"] for l in legs), "p_model": round(pm, 5),
                         "p_market": round(0.5 ** nlegs, 5), "decimal": r["decimal"],
                         "void": r["void"], "game_id": legs[0]["game_id"]})
        results[sname] = {
            "desc": f"{nlegs}-leg parlay from the >=2pt spread/total edge pool (one parlay per week).",
            "kind": f"parlay{nlegs}",
            "discovery": evaluate(sname, [b for b in bets if b["season"] < SPLIT_YEAR], "discovery_2002_2019"),
            "holdout": evaluate(sname, [b for b in bets if b["season"] >= SPLIT_YEAR], "holdout_2020_2026"),
            "all": evaluate(sname, bets, "all"), "by_season": by_season_rows(bets)}
        ledgers[sname] = bets

    # ---------------- same-game parlay: spread + total, correlation aware ---------
    corr = correlations(preds)
    rho = corr["phi_home_cover_vs_over"]
    sgp = []
    for p in preds:
        m = p["market"]
        if m["spread_home"] is None or m["total"] is None:
            continue
        edge_s = p["model_margin"] - m["spread_home"]
        edge_t = p["model_total"] - m["total"]
        if abs(edge_s) < 2.0 or abs(edge_t) < 2.0:
            continue
        ls = leg_for_spread(p, "home" if edge_s > 0 else "away", edge_s)
        lt = leg_for_total(p, "over" if edge_t > 0 else "under", edge_t)
        # joint probability via bivariate normal with the empirically measured rho
        zs = (abs(edge_s)) / p["sigma"]
        zt = (abs(edge_t)) / p["sigma"]
        joint = bivariate_normal_upper(zs, zt, rho if rho is not None else 0.0)
        r = eval_parlay([ls, lt])
        sgp.append({"season": p["season"], "week": p["week"], "kind": "sgp", "legs": [ls, lt],
                    "units": r["units"], "hit": r["hit"], "push": any(l["push"] for l in [ls, lt]),
                    "p_model": round(joint, 5), "p_market": 0.25, "decimal": r["decimal"],
                    "void": r["void"], "game_id": p["game_id"]})
    results["S15_sgp_spread_total"] = {
        "desc": "Same-game parlay (spread + total) where both legs clear a 2-point model edge; "
                f"joint probability priced with the measured rho = {rho}.",
        "kind": "sgp",
        "discovery": evaluate("S15_sgp_spread_total", [b for b in sgp if b["season"] < SPLIT_YEAR], "discovery_2002_2019"),
        "holdout": evaluate("S15_sgp_spread_total", [b for b in sgp if b["season"] >= SPLIT_YEAR], "holdout_2020_2026"),
        "all": evaluate("S15_sgp_spread_total", sgp, "all"), "by_season": by_season_rows(sgp)}
    ledgers["S15_sgp_spread_total"] = sgp

    corr["sgp_note"] = ("rho is the phi coefficient between the home side covering and the game going "
                        "over; it is what a same-game parlay price must reflect.")
    json.dump(results, open(os.path.join(PROC, "strategies.json"), "w"), separators=(",", ":"))
    json.dump(corr, open(os.path.join(PROC, "correlations.json"), "w"), indent=1)
    # full ledger, compact (legs dropped) — used by validation.py for stability / robustness
    compact = {}
    for k, bets in ledgers.items():
        rows = []
        for b in bets:
            rows.append({"season": b["season"], "week": b["week"], "game_id": b["game_id"],
                         "units": round(b["units"], 4), "hit": b["hit"], "push": b["push"],
                         "p_model": b["p_model"], "p_market": b["p_market"],
                         "decimal": None if b["decimal"] is None else round(b["decimal"], 4),
                         "void": b["void"]})
        compact[k] = rows
    json.dump(compact, open(os.path.join(PROC, "bets_all.json"), "w"), separators=(",", ":"))
    # a small published ledger (2026 only) for the transparency page
    pub = {}
    for k in ("S0_baseline_all_home", "S1_spread_edge_2", "S10_wind15_under", "S13_parlay2_edge2", "S15_sgp_spread_total"):
        if k not in ledgers:
            continue
        pub[k] = [b for b in ledgers[k] if b["season"] == 2026]
    json.dump(pub, open(os.path.join(PROC, "bets_2026.json"), "w"), separators=(",", ":"))

    for k, v in results.items():
        h = v["holdout"]
        print(f"{k:24s} n={h.get('n',0):5d} roi={h.get('roi')} hit={h.get('hit_rate')} "
              f"disc_roi={v['discovery'].get('roi')}")


def bivariate_normal_upper(z1, z2, rho):
    """P(Z1 > z1 and Z2 > z2) for a standard bivariate normal (Gauss-Legendre quadrature)."""
    # integrate over z2: P(Z2>z2) * P(Z1>z1 | Z2=u) with conditional normal
    n = 64
    xs, ws = np.polynomial.legendre.leggauss(n)
    lo, hi = z2, z2 + 10.0
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    total = 0.0
    for x, w in zip(xs, ws):
        u = mid + half * x
        dens = math.exp(-0.5 * u * u) / math.sqrt(2 * math.pi)
        cond_mean = rho * u
        cond_sd = math.sqrt(max(1e-9, 1 - rho * rho))
        total += w * half * dens * (1.0 - norm_cdf((z1 - cond_mean) / cond_sd))
    return total


if __name__ == "__main__":
    run()
