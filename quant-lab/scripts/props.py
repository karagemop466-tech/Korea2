#!/usr/bin/env python3
"""
props.py — player-prop line origination and player-leg correlation.

Input : data/official/players_2026.json  (transcribed from each player's official nfl.com page)
        data/processed/board.json        (originated team totals for the coming weeks)
Output: data/processed/props.json, data/processed/prop_corr.json, data/processed/prop_diag.json

Method (deliberately simple and auditable):
  projection      = recency-weighted mean of the player's games (half-life 2 games)
                    x opponent environment factor, where the factor is
                    (model's expected points for the player's team / league average) ** 0.5,
                    clipped to [0.80, 1.20].
  originated line = projection rounded to the nearest 0.5 (how prop markets quote yards).
  sigma           = the player's own sample standard deviation of per-game values.
  P(over)         = 1 - Phi((line - projection) / sigma).

No prop PRICE exists in any source reachable here, so every prop bet is settled at -110 and that
assumption is published on the Flagged page rather than hidden.
"""
import json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OFF = os.path.join(ROOT, "data", "official")


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pearson(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    if n < 3:
        return None
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return None if den == 0 else num / den


def corr_ci(r, n):
    """Fisher z 95% interval; returns None when n < 4."""
    if r is None or n < 4 or abs(r) >= 1:
        return None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return [round(math.tanh(lo), 3), round(math.tanh(hi), 3)]


def weighted_mean(vals, half_life=2.0):
    n = len(vals)
    ws = [0.5 ** ((n - 1 - i) / half_life) for i in range(n)]
    return sum(w * v for w, v in zip(ws, vals)) / sum(ws)


def bivariate_joint(p1_params, p2_params, r):
    """P(leg1 wins AND leg2 wins) with a bivariate normal and correlation r.
    p*_params = (mu, sigma, line, side) with side=+1 for over, -1 for under."""
    mu1, s1, l1, k1 = p1_params
    mu2, s2, l2, k2 = p2_params
    z1 = k1 * (l1 - mu1) / s1
    z2 = k2 * (l2 - mu2) / s2
    n = 64
    xs, ws = _leggauss(n)
    lo, hi = z2, z2 + 8.0
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    total = 0.0
    for x, w in zip(xs, ws):
        u = mid + half * x
        dens = math.exp(-0.5 * u * u) / math.sqrt(2 * math.pi)
        cm = r * u
        csd = math.sqrt(max(1e-9, 1 - r * r))
        total += w * half * dens * (1.0 - norm_cdf((z1 - cm) / csd))
    return total


def _leggauss(n):
    # Gauss-Legendre nodes/weights via Newton iteration on Legendre polynomials
    xs, ws = [], []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, 0.0
            for j in range(1, n + 1):
                p0, p1 = ((2 * j - 1) * x * p0 - (j - 1) * p1) / j, p0
            dp = n * (x * p0 - p1) / (x * x - 1)
            dx = -p0 / dp
            x += dx
            if abs(dx) < 1e-15:
                break
        xs.append(x)
        ws.append(2.0 / ((1 - x * x) * dp * dp))
    return xs, ws


def main():
    doc = json.load(open(os.path.join(OFF, "players_2026.json")))
    board = json.load(open(os.path.join(PROC, "board.json")))
    games = json.load(open(os.path.join(PROC, "games.json")))

    # league average points per team, 2026 regular season
    g26 = [g for g in games if g["season"] == 2026 and g["game_type"] == "REG"]
    league_ppg = sum(g["total_points"] for g in g26) / (2 * len(g26))

    board_by_team = {}
    for b in board:
        if b["week"] != 9:
            continue
        board_by_team[b["home"]] = {"opp": b["away"], "venue": "home", "exp_pts": b["orig_home_pts"],
                                    "line": b["orig_spread_home"], "total": b["orig_total"], "week": 9}
        board_by_team[b["away"]] = {"opp": b["home"], "venue": "away", "exp_pts": b["orig_away_pts"],
                                    "line": -b["orig_spread_home"], "total": b["orig_total"], "week": 9}

    props = []
    for p in doc["players"]:
        vals = [g["value"] for g in p["games"]]
        s = sd(vals)
        base = weighted_mean(vals)
        nxt = board_by_team.get(p["team"])
        if nxt is None:
            props.append({"player": p["name"], "team": p["team"], "market": p["market"],
                          "line": None, "note": "no week-9 game found in the mirror for this team",
                          "source_url": p["source_url"]})
            continue
        factor = (nxt["exp_pts"] / league_ppg) ** 0.5
        factor = min(max(factor, 0.80), 1.20)
        proj = base * factor
        line = round(proj * 2) / 2
        row = {
            "player": p["name"], "slug": p["slug"], "team": p["team"], "pos": p["pos"],
            "market": p["market"], "stat_label": p["stat_label"],
            "week": 9, "opp": nxt["opp"], "venue": nxt["venue"],
            "n_games": len(vals), "season_total": p["season_total"]["yds"],
            "raw_mean": round(mean(vals), 2), "recency_mean": round(base, 2),
            "env_factor": round(factor, 3), "expected_team_pts": nxt["exp_pts"],
            "league_ppg": round(league_ppg, 2),
            "projection": round(proj, 2), "player_sd": None if s is None else round(s, 2),
            "originated_line": line,
            "p_over": round(1.0 - norm_cdf((line - proj) / s), 4) if s else None,
            "p_under": round(norm_cdf((line - proj) / s), 4) if s else None,
            "price": -110,
            "source_url": p["source_url"],
        }
        props.append(row)

    # ---------------- empirical player-leg correlations -------------------------
    by_team = {}
    for p in doc["players"]:
        by_team.setdefault(p["team"], {})[p["pos"] if p["pos"] != "WR" else "WR" + str(len(by_team.get(p["team"], {})))] = p
    pairs = []
    for team, roster in by_team.items():
        qbs = [v for k, v in roster.items() if v["pos"] == "QB"]
        wrs = [v for k, v in roster.items() if v["pos"] == "WR"]
        for qb in qbs:
            for wr in wrs:
                wmap = {g["week"]: g for g in wr["games"]}
                a, b, weeks = [], [], []
                for g in qb["games"]:
                    if g["week"] in wmap:
                        a.append(g["value"]); b.append(wmap[g["week"]]["value"]); weeks.append(g["week"])
                r = pearson(a, b)
                pairs.append({"team": team, "leg_a": qb["name"], "leg_b": wr["name"],
                              "market_a": qb["market"], "market_b": wr["market"],
                              "n": len(a), "r": None if r is None else round(r, 4),
                              "r_ci95": corr_ci(r, len(a)), "weeks": weeks,
                              "sources": [qb["source_url"], wr["source_url"]]})

    player_team_corr = []
    for p in doc["players"]:
        pts = [g["team_pts"] for g in p["games"]]
        mar = [g["team_pts"] - g["opp_pts"] for g in p["games"]]
        vals = [g["value"] for g in p["games"]]
        r1, r2 = pearson(vals, pts), pearson(vals, mar)
        player_team_corr.append({"player": p["name"], "team": p["team"], "market": p["market"], "n": len(vals),
                                 "r_vs_team_points": None if r1 is None else round(r1, 4),
                                 "r_vs_team_points_ci95": corr_ci(r1, len(vals)),
                                 "r_vs_team_margin": None if r2 is None else round(r2, 4),
                                 "r_vs_team_margin_ci95": corr_ci(r2, len(vals)),
                                 "source_url": p["source_url"]})

    # pooled QB1 <-> WR1 correlation across teams
    pooled_a, pooled_b = [], []
    for pr in pairs:
        qb = next(x for x in doc["players"] if x["name"] == pr["leg_a"])
        wr = next(x for x in doc["players"] if x["name"] == pr["leg_b"])
        wmap = {g["week"]: g for g in wr["games"]}
        for g in qb["games"]:
            if g["week"] in wmap:
                pooled_a.append(g["value"]); pooled_b.append(wmap[g["week"]]["value"])
    pooled_r = pearson(pooled_a, pooled_b)

    # ---------------- SGP mispricing illustration -----------------------------
    sgp_cases = []
    for pr in pairs:
        wr = next(x for x in doc["players"] if x["name"] == pr["leg_b"])
        qb = next(x for x in doc["players"] if x["name"] == pr["leg_a"])
        rowq = next((x for x in props if x["player"] == qb["name"]), None)
        roww = next((x for x in props if x["player"] == wr["name"]), None)
        if not rowq or not roww or rowq["player_sd"] is None or roww["player_sd"] is None:
            continue
        if pr["r"] is None:
            continue
        r = pr["r"]
        p_naive = rowq["p_over"] * roww["p_over"]
        p_corr = bivariate_joint((rowq["projection"], rowq["player_sd"], rowq["originated_line"], 1),
                                 (roww["projection"], roww["player_sd"], roww["originated_line"], 1), r)
        sgp_cases.append({
            "team": pr["team"], "leg_a": qb["name"], "leg_b": wr["name"], "r": r, "n_pairs": pr["n"],
            "p_over_a": rowq["p_over"], "p_over_b": roww["p_over"],
            "p_joint_independent": round(p_naive, 4), "p_joint_correlated": round(p_corr, 4),
            "fair_odds_independent": None if p_naive == 0 else round(-100 / ((1 / p_naive) - 1)) if p_naive > 0.5 else round(((1 / p_naive) - 1) * 100),
            "fair_odds_correlated": None if p_corr == 0 else round(-100 / ((1 / p_corr) - 1)) if p_corr > 0.5 else round(((1 / p_corr) - 1) * 100),
            "rel_mispricing_pct": None if p_naive == 0 else round(100 * (p_corr - p_naive) / p_naive, 2),
        })

    # ---------------- expanding-window diagnostic (no market prices) -----------
    diag = []
    for p in doc["players"]:
        vals = [g["value"] for g in p["games"]]
        for i in range(3, len(vals)):
            hist = vals[:i]
            line = round(weighted_mean(hist) * 2) / 2
            actual = vals[i]
            if actual == line:
                continue
            diag.append({"player": p["name"], "market": p["market"], "week_index": i,
                         "line": line, "actual": actual,
                         "over": 1 if actual > line else 0,
                         "p_over_pred": 1.0 - norm_cdf((line - weighted_mean(hist)) / sd(hist)) if sd(hist) else None})
    n = len(diag)
    hits = sum(1 for d in diag if (d["p_over_pred"] is not None and
                                   ((d["p_over_pred"] >= 0.5 and d["over"] == 1) or (d["p_over_pred"] < 0.5 and d["over"] == 0))))
    brier = sum((d["p_over_pred"] - d["over"]) ** 2 for d in diag if d["p_over_pred"] is not None)
    nb = sum(1 for d in diag if d["p_over_pred"] is not None)
    diagnostic = {
        "n_observations": n, "n_with_model_prob": nb,
        "side_hit_rate": round(hits / nb, 4) if nb else None,
        "brier": round(brier / nb, 4) if nb else None,
        "note": "Expanding-window diagnostic only: no player-prop price exists in any reachable source, "
                "so no prop strategy can be settled against a real market. Sample n is far below the gate.",
    }

    json.dump(props, open(os.path.join(PROC, "props.json"), "w"), indent=1)
    json.dump({"pairs": pairs, "pooled_qb_wr": {"r": None if pooled_r is None else round(pooled_r, 4),
                                                "n": len(pooled_a), "ci95": corr_ci(pooled_r, len(pooled_a))},
               "player_team": player_team_corr, "sgp_cases": sgp_cases,
               "source": "nfl.com player stats pages (2026 regular season game logs)"},
              open(os.path.join(PROC, "prop_corr.json"), "w"), indent=1)
    json.dump(diagnostic, open(os.path.join(PROC, "prop_diag.json"), "w"), indent=1)

    print("props:", len(props), "| pairs:", len(pairs), "| pooled r:", None if pooled_r is None else round(pooled_r, 3),
          "n=", len(pooled_a))
    for pr in pairs:
        print(f"  {pr['team']}: {pr['leg_a']} vs {pr['leg_b']}  r={pr['r']} n={pr['n']} ci={pr['r_ci95']}")
    print("diagnostic:", diagnostic)


if __name__ == "__main__":
    main()
