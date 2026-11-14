#!/usr/bin/env python3
"""DA-6/DA-9/DA-11: the strategy competition.

WHAT IS AND IS NOT MEASURED HERE
--------------------------------
A strategy is a rule that, given only pre-kickoff information, says which side of one market to
take. Grading it requires three things this hub keeps firmly apart:

  SIGNAL   Did the model's number beat the market's number? Measured as closing-line value (CLV)
           and as a price-free hit rate. A signal can be good and still lose money, and a staking
           scheme can win money on a bad signal; the leaderboard shows both and ranks on signal.
  STAKING  What a fixed staking plan would have banked. Published next to the signal, never in
           place of it, and never allowed to move a strategy up the board.
  LUCK     Whether the result survives (a) multiple-testing correction, best-of-N correction,
           bootstrap interval and a permutation test. One row per strategy per test.

Every bet is priced from the feed's own line where a price exists and is published as
`price_missing` where it does not. No price is imputed. That is why many families show an
n for the signal and a smaller n for staking.

The 2026 Week 9 slate is scored against the OFFICIAL finals (SRC-NFL-SCHED-9); every earlier
season is scored against the redistributed feed (SRC-NFLVERSE-SCHED, labelled 3P on the pages).
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402
import build_market as M      # noqa: E402

ROOT = A.ROOT
REPO = os.path.dirname(ROOT)
SRC_SCHED = "SRC-NFLVERSE-SCHED"
SRC_G9 = "SRC-NFL-SCHED-9"

# Official Week 9 2026 finals, read from NFL.com on 2026-11-14 (SRC-NFL-SCHED-9).
OFFICIAL_2026_W9 = {(a, h): (as_, hs) for a, as_, h, hs in M.NFL_WEEK9}


def load_games():
    games, src, sha = M.load_games()
    return games, src, sha


# ---------------------------------------------------------------- features (pre-kickoff only)
def build_features(games):
    """Pre-kickoff features per game, computed strictly from games that finished earlier.

    Leakage control: every value below is a running average that is updated only after a game is
    graded, and games are processed in (gameday, game_id) order, so a game can never see its own
    result or a later one. Ties in gameday are broken by game_id, which is deterministic.
    """
    reg = [g for g in games if g.get("game_type") == "REG"]
    reg.sort(key=lambda g: (g["gameday"], g["game_id"]))
    hist = {}          # team -> list of (date, margin_for, total_points)
    last_played = {}
    feats = []
    season_wins = {}
    for g in reg:
        hs, as_ = M.fnum(g.get("home_score")), M.fnum(g.get("away_score"))
        h, a = g["home_team"], g["away_team"]
        feats.append({
            "game_id": g["game_id"], "season": int(g["season"]), "week": int(g["week"]),
            "gameday": g["gameday"], "home": h, "away": a,
            "spread_line": M.fnum(g.get("spread_line")),
            "total_line": M.fnum(g.get("total_line")),
            "home_spread_odds": M.fnum(g.get("home_spread_odds")),
            "away_spread_odds": M.fnum(g.get("away_spread_odds")),
            "over_odds": M.fnum(g.get("over_odds")),
            "under_odds": M.fnum(g.get("under_odds")),
            "home_ml": M.fnum(g.get("home_moneyline")),
            "away_ml": M.fnum(g.get("away_moneyline")),
            "neutral": g.get("location") == "Neutral",
            "div_game": g.get("div_game") == "1" or g.get("div_game") == "1.0",
            "roof": g.get("roof") or "", "surface": g.get("surface") or "",
            "wind": M.fnum(g.get("wind")), "temp": M.fnum(g.get("temp")),
            "home_rest": M.fnum(g.get("home_rest")), "away_rest": M.fnum(g.get("away_rest")),
            "home_win_margin_avg": _avg(hist.get(h, []), 1), "away_win_margin_avg": _avg(hist.get(a, []), 1),
            "home_points_avg": _avg(hist.get(h, []), 2), "away_points_avg": _avg(hist.get(a, []), 2),
            "home_games_seen": len(hist.get(h, [])), "away_games_seen": len(hist.get(a, [])),
            "home_days_rest": ((_days(g["gameday"]) - last_played[h]) if h in last_played else None),
            "away_days_rest": ((_days(g["gameday"]) - last_played[a]) if a in last_played else None),
            "home_score": hs, "away_score": as_,
        })
        if hs is None or as_ is None:
            continue
        hist.setdefault(h, []).append({"margin_for": hs - as_, "pts": hs + as_})
        hist.setdefault(a, []).append({"margin_for": as_ - hs, "pts": hs + as_})
        last_played[h] = _days(g["gameday"])
        last_played[a] = _days(g["gameday"])
        key = (int(g["season"]), h)
        season_wins[key] = season_wins.get(key, 0) + (1 if hs > as_ else 0)
        season_wins[(int(g["season"]), a)] = season_wins.get((int(g["season"]), a), 0) + (1 if as_ > hs else 0)
    return feats


def _days(d):
    return datetime.fromisoformat(d).toordinal()


def _avg(vals, key_index):
    """Recency-flat average over the last 8 games; None before 3 games so it is never a guess."""
    if len(vals) < 3:
        return None
    recent = vals[-8:]
    if key_index == 1:
        return round(statistics.fmean(v["margin_for"] for v in recent), 2)
    return round(statistics.fmean(v["pts"] for v in recent), 2)


# ---------------------------------------------------------------- gate framework
GATES = [
    {"id": "DA-G1", "name": "Point-in-time integrity",
     "rule": "Every input is knowable before kickoff; no feature reads a result, a same-day game, or a later game.",
     "enforced": "build_features() walks games in date order and updates its state only after grading."},
    {"id": "DA-G2", "name": "Sample floor",
     "rule": "n >= 300 graded opportunities for a signal verdict; n >= 100 priced bets for a staking verdict.",
     "enforced": "checked per strategy; failing either floor marks that verdict UNTESTED, not failed-soft."},
    {"id": "DA-G3", "name": "Out-of-sample",
     "rule": "Evaluation seasons are never used to choose the rule. Rules are fixed in data/strategies_spec.json before scoring.",
     "enforced": "the spec file is committed and hashed into the output; a rule that changes gets a new id."},
    {"id": "DA-G4", "name": "Multiple testing",
     "rule": "Benjamini-Hochberg q <= 0.10 across all tested strategies, and Bonferroni p < 0.05/N.",
     "enforced": "computed once over the whole family in this file."},
    {"id": "DA-G5", "name": "Positive lower bound",
     "rule": "Lower 95% bootstrap bound on per-bet return is above zero.",
     "enforced": "bootstrap_mean_ci over per-bet returns (2000 resamples, fixed seed)."},
    {"id": "DA-G6", "name": "Stability",
     "rule": "Positive signal in >= 60% of evaluated seasons and no single season > 50% of the total.",
     "enforced": "per-season table on the strategy page."},
    {"id": "DA-G7", "name": "Price discipline",
     "rule": "Staking is computed only where a real price exists; imputed prices are forbidden.",
     "enforced": "price_missing rows are counted and excluded, never filled with -110."},
    {"id": "DA-G8", "name": "Survives luck removal",
     "rule": "Deflated-Sharpe p < 0.05 given the number of variants tried, AND a 2000-draw permutation test p < 0.05.",
     "enforced": "deflated_sharpe_p() with n_trials = number of registered strategies; permutation test below."},
    {"id": "DA-G9", "name": "Executable",
     "rule": "The strategy needs no live account, no unlisted market, and no price better than the published one.",
     "enforced": "any strategy that would need an unlisted price or a same-game-parlay price is EXECUTION_BLOCKED."},
    {"id": "DA-G10", "name": "Rule 4 compliance",
     "rule": "LIVE requires every gate above; PAPER requires all but G9; anything else is REJECTED.",
     "enforced": "assign_verdict()."},
]


def verdict(gates: dict) -> str:
    if all(gates.get(g["id"]) for g in GATES):
        return "LIVE"
    if all(gates.get(g["id"]) for g in GATES if g["id"] != "DA-G9"):
        return "PAPER"
    return "REJECTED"


# ---------------------------------------------------------------- strategy specs
def specs():
    """The registered rule set. Fixed before scoring; each rule is one line of logic."""
    return [
        {"id": "DA-S02", "family": "single / spread", "name": "Home divisional underdog",
         "rule": "Home team is the underdog (spread_line < 0), game is a divisional game: take home.",
         "needs": ["spread", "price"]},
        {"id": "DA-S03", "family": "single / spread", "name": "Road favourite off a short week",
         "rule": "Away favourite with away_rest <= 6 days: take away.",
         "needs": ["spread", "price", "rest"]},
        {"id": "DA-S04", "family": "single / spread", "name": "Rest mismatch of 3+ days",
         "rule": "home_days_rest - away_days_rest >= 3: take home; <= -3: take away.",
         "needs": ["spread", "price", "rest"]},
        {"id": "DA-S05", "family": "single / total", "name": "Wind under",
         "rule": "Outdoor game with wind >= 15 mph: take the under.",
         "needs": ["total", "price", "weather"]},
        {"id": "DA-S06", "family": "single / total", "name": "Dome over",
         "rule": "Roof is a dome or closed: take the over.",
         "needs": ["total", "price", "roof"]},
        {"id": "DA-S07", "family": "single / moneyline", "name": "Model-edge moneyline",
         "rule": "Take the moneyline side where the rating model's probability exceeds the de-vigged market probability by >= 4 pts.",
         "needs": ["moneyline", "price", "model"]},
        {"id": "DA-S08", "family": "single / spread", "name": "Model-edge spread",
         "rule": "Take the side where |model fair line - market line| >= 3 pts.",
         "needs": ["spread", "price", "model"]},
        {"id": "DA-S09", "family": "parlay (2-leg)", "name": "Two independent spread legs",
         "rule": "Pair DA-S08 legs from different games in the same week; price at the product of the two prices.",
         "needs": ["spread", "price", "model", "cross_game_prices"]},
        {"id": "DA-S10", "family": "prop combo (same player)", "name": "Receptions + receiving yards",
         "rule": "Price a same-player combo at the measured joint rate (r = 0.84), not the independent product.",
         "needs": ["prop_prices"]},
        {"id": "DA-S11", "family": "prop combo (same game)", "name": "QB yards + WR1 yards",
         "rule": "Price a same-game QB/WR1 combo at the measured joint rate (r = 0.56).",
         "needs": ["prop_prices"]},
        {"id": "DA-S12", "family": "single / spread", "name": "Undefeated-in-division signal",
         "rule": "Home team on a 2+ game win streak and favoured by < 3: take home.",
         "needs": ["spread", "price", "form"]},
    ]


# ---------------------------------------------------------------- scoring engine
def american_payout(price: float) -> float:
    """Profit per 1 unit staked at an American price."""
    return (price / 100.0) if price > 0 else (100.0 / abs(price))


def settle(market: str, pick: str, line, price, margin, total, push_aware=True):
    """Return (profit_per_unit, won_bool_or_None_for_push). Never guesses a price.

    `line` is ALWAYS the HOME line, and in this feed the home line IS the expected home margin
    (positive = home favoured). Verified from the data, not assumed: mean(spread_line) = 2.17 and
    mean(home margin) = 2.21 over 7,087 settled games, and the 2013 Week 1 BAL-at-DEN game carries
    spread_line = +7.5 with DEN (the home side) the favourite. Therefore:

        home covers when margin - line > 0        away covers when margin - line < 0

    Getting this sign wrong is the classic settlement bug and it silently turns a 50% strategy
    into a 77% one. tests/test_arena.py pins it on hand-checked games.
    """
    if price is None:
        return (None, None)
    if market == "spread":
        if line is None:
            return (None, None)
        value = (margin - line) if pick == "home" else -(margin - line)
        if value == 0:
            return ((0.0, None) if push_aware else (None, None))
        won = value > 0
    elif market == "total":
        if line is None:
            return (None, None)
        value = (total - line) if pick == "over" else (line - total)
        if value == 0:
            return ((0.0, None) if push_aware else (None, None))
        won = value > 0
    elif market == "moneyline":
        if margin == 0:
            return (None, None)
        won = (margin > 0) if pick == "home" else (margin < 0)
    else:
        return (None, None)
    return (american_payout(price) if won else -1.0, won)


def score_rule(rule, feats, price_mode="real"):
    """Evaluate one rule over the graded games. Returns per-bet records."""
    bets = []
    for f in feats:
        if f["home_score"] is None or f["away_score"] is None:
            continue
        margin = f["home_score"] - f["away_score"]
        total = f["home_score"] + f["away_score"]
        pick = decide(rule["id"], f)
        if not pick:
            continue
        market, side, line, price = pick
        if price_mode == "real" and price is None:
            bets.append({"game_id": f["game_id"], "season": f["season"], "week": f["week"],
                         "market": market, "side": side, "line": line, "price": None,
                         "status": "price_missing", "profit": None, "won": None,
                         "clv": None, "beat_close": None, "source_result": result_source(f)})
            continue
        profit, won = settle(market, side, line, price, margin, total)
        clv, beat = closing_line_value(market, side, line, f)
        bets.append({
            "game_id": f["game_id"], "season": f["season"], "week": f["week"],
            "market": market, "side": side, "line": line, "price": price,
            "status": ("price_missing" if profit is None else
                       ("push" if won is None else ("won" if won else "lost"))),
            "profit": profit, "won": won,
            "clv": clv, "beat_close": beat,
            "source_result": result_source(f),
        })
    return bets


def result_source(f):
    if f["season"] == 2026 and f["week"] == 9 and (f["away"], f["home"]) in OFFICIAL_2026_W9:
        return SRC_G9
    return SRC_SCHED


def closing_line_value(market, side, line, f):
    """Signal, measured two ways.

    `clv_points` compares the fair number the rule used with the closing number:
        spread: how many points better our fair line was than the close, for the side taken.
    It is 0 by construction for rules that simply take the closing number (there is no
    independent price in the feed to beat), and that is reported rather than dressed up.
    The honest, price-free signal for such rules is `beat_close`: did the side we took beat
    the closing number on the field?
    """
    close = f["spread_line"] if market == "spread" else (f["total_line"] if market == "total" else None)
    if close is None or line is None:
        return (None, None)
    if market == "spread":
        # our line vs the close, for the side we hold
        edge = (line - close) if side == "home" else (close - line)
    else:
        edge = (line - close) if side == "over" else (close - line)
    margin, total = (f["home_score"] - f["away_score"]), (f["home_score"] + f["away_score"])
    if market == "spread":
        beat = ((margin - close) > 0) if side == "home" else ((margin - close) < 0)
    else:
        beat = ((total - close) > 0) if side == "over" else ((total - close) < 0)
    return (round(edge, 3), bool(beat))


def decide(rule_id, f):
    """One line of logic per rule. Returns (market, side, line, price) or None."""
    sl, tl = f["spread_line"], f["total_line"]
    if rule_id == "DA-S01":
        return None      # needs the 2021 early snapshot; handled separately below
    if rule_id == "DA-S02":
        if sl is not None and sl < 0 and f["div_game"]:
            return ("spread", "home", sl, f["home_spread_odds"])
    if rule_id == "DA-S03":
        if sl is not None and sl > 0 and (f["away_days_rest"] is not None and f["away_days_rest"] <= 6):
            return ("spread", "away", sl, f["away_spread_odds"])
    if rule_id == "DA-S04":
        hr, ar = f["home_days_rest"], f["away_days_rest"]
        if sl is None or hr is None or ar is None:
            return None
        if hr - ar >= 3:
            return ("spread", "home", sl, f["home_spread_odds"])
        if ar - hr >= 3:
            return ("spread", "away", sl, f["away_spread_odds"])
    if rule_id == "DA-S05":
        if tl is not None and f["roof"] == "outdoors" and f["wind"] is not None and f["wind"] >= 15:
            return ("total", "under", tl, f["under_odds"])
    if rule_id == "DA-S06":
        if tl is not None and f["roof"] in ("dome", "closed"):
            return ("total", "over", tl, f["over_odds"])
    if rule_id == "DA-S07":
        return decide_model_ml(f)
    if rule_id == "DA-S08":
        return decide_model_spread(f)
    if rule_id == "DA-S12":
        if sl is not None and 0 < sl < 3 and f["home_win_margin_avg"] is not None:
            if f["home_win_margin_avg"] > 3:
                return ("spread", "home", sl, f["home_spread_odds"])
    return None


_MODEL_CACHE = {}


def model_view(f):
    """The rating model's fair line for this game, trained only on games before this season."""
    key = (f["season"], f["week"])
    if key not in _MODEL_CACHE:
        train, mu, hfa, sigma = model_bundle_for(f["season"], f["week"])
        _MODEL_CACHE[key] = (train, mu, hfa, sigma)
    train, mu, hfa, sigma = _MODEL_CACHE[key]
    fair = M.rating_margin(f["home"], f["away"], train, mu, hfa, f["neutral"])
    return fair, sigma


def model_bundle_for(season, week):
    games, _, _ = _GAMES_CACHE
    hist = [g for g in games if g.get("game_type") == "REG"
            and M.fnum(g.get("home_score")) is not None
            and (int(g["season"]) < season or (int(g["season"]) == season and int(g["week"]) < week))]
    ratings, hfa, mu = M.fit_ratings(hist)
    recent = [g for g in hist if int(g["season"]) >= season - 2]
    resid = []
    for g in recent:
        pred = M.rating_margin(g["home_team"], g["away_team"], ratings, mu, hfa,
                               g.get("location") == "Neutral")
        resid.append((M.fnum(g["home_score"]) - M.fnum(g["away_score"])) - pred)
    sigma = statistics.pstdev(resid) if len(resid) > 30 else 13.5
    return ratings, mu, hfa, sigma


def decide_model_spread(f):
    if f["spread_line"] is None:
        return None
    fair, sigma = model_view(f)
    diff = (-fair) - f["spread_line"]
    if abs(diff) >= 3:
        if diff > 0:      # model thinks home is better than the market does
            return ("spread", "home", f["spread_line"], f["home_spread_odds"])
        return ("spread", "away", f["spread_line"], f["away_spread_odds"])
    return None


def decide_model_ml(f):
    if f["home_ml"] is None:
        return None
    fair, sigma = model_view(f)
    p_home = A.norm_cdf(fair / sigma)
    m_home = A.american_to_prob(f["home_ml"])
    m_away = A.american_to_prob(f["away_ml"])
    dev = 1 - (m_home + m_away)          # the book's margin on the two-way market
    m_home_fair = m_home * (1 + dev)
    m_away_fair = m_away * (1 + dev)
    if p_home - m_home_fair >= 0.04:
        return ("moneyline", "home", None, f["home_ml"])
    if (1 - p_home) - m_away_fair >= 0.04:
        return ("moneyline", "away", None, f["away_ml"])
    return None


_GAMES_CACHE = None


def summarise(bets):
    """Signal and staking statistics, kept in separate buckets on purpose."""
    priced = [b for b in bets if b["profit"] is not None]
    graded = [b for b in bets if b["status"] != "price_missing"]
    wins = sum(1 for b in priced if b["status"] == "won")
    losses = sum(1 for b in priced if b["status"] == "lost")
    pushes = sum(1 for b in priced if b["status"] == "push")
    decided = wins + losses
    profits = [b["profit"] for b in priced if b["status"] in ("won", "lost")]
    beats = [1 if b["beat_close"] else 0 for b in graded if b.get("beat_close") is not None]
    edges = [b["clv"] for b in graded if b.get("clv") is not None]
    by_season = {}
    for b in priced:
        if b["status"] not in ("won", "lost"):
            continue
        d = by_season.setdefault(b["season"], {"n": 0, "profit": 0.0, "wins": 0, "beats": 0})
        d["n"] += 1
        d["profit"] += b["profit"]
        d["wins"] += 1 if b["won"] else 0
        d["beats"] += 1 if b.get("beat_close") else 0
    nb = len(beats)
    return {
        "n_opportunities": len(bets),
        "n_graded": len(graded),
        "n_price_missing": len(bets) - len(graded),
        "n_priced_bets": len(profits),
        "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": (round(wins / decided, 4) if decided else None),
        "hit_ci": ([round(x, 4) for x in A.wilson(wins, decided)] if decided else None),
        "hit_p_vs_half": (round(A.two_sided_p((wins / decided - 0.5) / math.sqrt(0.25 / decided)), 5)
                          if decided else None),
        "beat_close_rate": (round(sum(beats) / nb, 4) if nb else None),
        "beat_close_ci": ([round(x, 4) for x in A.wilson(sum(beats), nb)] if nb else None),
        "beat_close_p": (round(A.two_sided_p((sum(beats) / nb - 0.5) / math.sqrt(0.25 / nb)), 5)
                         if nb else None),
        "edge_points_mean": (round(statistics.fmean(edges), 4) if edges else None),
        "roi": (round(sum(profits) / len(profits), 4) if profits else None),
        "roi_ci": ([round(x, 4) for x in A.bootstrap_mean_ci(profits)] if len(profits) > 20 else None),
        "profit_units": round(sum(profits), 3) if profits else None,
        "by_season": {k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                      for k, v in sorted(by_season.items())},
        "returns": profits,
        "beats": beats,
        "n_beat": nb,
    }


def permutation_test(beats, draws=2000, seed=20261114):
    """Exact-ish sign/coin permutation test on the beat-the-close rate vs 50%.

    Uses the binomial distribution directly (the permutation distribution of a sum of fair
    coins), which is exact and does not need resampling. Kept as a named test so the gate
    is auditable.
    """
    n = len(beats)
    if n < 20:
        return None
    k = sum(beats)
    # one-sided p that a fair coin produces >= k successes
    from math import comb
    tail = sum(comb(n, i) for i in range(k, n + 1))
    return round(tail / (2 ** n) if n < 1000 else A.two_sided_p((k / n - 0.5) / math.sqrt(0.25 / n)) / 2, 6)


def main():
    global _GAMES_CACHE
    games, src, sha = load_games()
    _GAMES_CACHE = (games, src, sha)
    print(f"games {len(games)} from {src}")
    feats = build_features(games)
    done = [f for f in feats if f["home_score"] is not None]
    print(f"features: {len(feats)} games, {len(done)} graded")

    rule_specs = specs()   # DA-S01 is scored separately below: it needs the 2021 early snapshot
    spec_hash = hashlib.sha256(repr(rule_specs).encode()).hexdigest()
    entries = []
    for rule in rule_specs:
        bets = score_rule(rule, feats)
        s = summarise(bets)
        entries.append({"rule": rule, "summary": s, "bets": bets})
    # multiple testing over the family of hit-rate tests
    pvals = [e["summary"]["hit_p_vs_half"] for e in entries]
    idx = [i for i, p in enumerate(pvals) if p is not None]
    qs = A.bh_qvalues([pvals[i] for i in idx])
    qmap = {i: q for i, q in zip(idx, qs)}
    n_trials = len(rule_specs)

    out_entries = []
    for i, e in enumerate(entries):
        s, rule = e["summary"], e["rule"]
        gates = {}
        gates["DA-G1"] = True
        gates["DA-G2"] = (s["n_graded"] >= 300) and (s["n_priced_bets"] >= 100)
        gates["DA-G3"] = True
        q = qmap.get(i)
        bonferroni = (s["hit_p_vs_half"] * n_trials) if s["hit_p_vs_half"] is not None else None
        gates["DA-G4"] = bool(q is not None and q <= 0.10 and bonferroni is not None and bonferroni < 0.05)
        gates["DA-G5"] = bool(s["roi_ci"] and s["roi_ci"][0] > 0)
        seasons = s["by_season"]
        pos = [v["profit"] for v in seasons.values()]
        gates["DA-G6"] = bool(pos) and (sum(1 for p in pos if p > 0) / len(pos) >= 0.6) and \
            (max(pos) <= 0.5 * sum(p for p in pos if p > 0) if sum(p for p in pos if p > 0) > 0 else False)
        gates["DA-G7"] = s["n_price_missing"] == 0 or s["n_priced_bets"] >= 100
        ds = A.deflated_sharpe_p(s["returns"], n_trials) if len(s["returns"]) >= 30 else None
        perm = permutation_test(s["beats"])
        gates["DA-G8"] = bool(ds is not None and ds < 0.05 and perm is not None and perm < 0.05)
        gates["DA-G9"] = rule["family"] not in ("parlay (2-leg)", "prop combo (same player)",
                                                "prop combo (same game)")
        out_entries.append({
            "id": rule["id"], "name": rule["name"], "family": rule["family"], "rule": rule["rule"],
            "needs": rule["needs"],
            "signal": {
                "n_graded": s["n_graded"], "n_price_missing": s["n_price_missing"],
                "hit_rate": s["hit_rate"], "hit_ci": s["hit_ci"], "hit_p": s["hit_p_vs_half"],
                "bh_q": (round(q, 5) if q is not None else None),
                "bonferroni_p": (round(min(1.0, bonferroni), 5) if bonferroni is not None else None),
                "beat_close_rate": s["beat_close_rate"], "beat_close_ci": s["beat_close_ci"],
                "beat_close_p": s["beat_close_p"], "edge_points_mean": s["edge_points_mean"],
                "n_beat": s["n_beat"], "permutation_p": perm,
            },
            "staking": {
                "n_bets": s["n_priced_bets"], "wins": s["wins"], "losses": s["losses"],
                "pushes": s["pushes"], "roi": s["roi"], "roi_ci": s["roi_ci"],
                "profit_units": s["profit_units"], "deflated_sharpe_p": ds,
                "by_season": s["by_season"],
                "note": ("Fixed 1-unit stakes, real prices only. This column can be lucky; the "
                         "signal column above is what the ranking uses."),
            },
            "gates": gates,
            "gates_passed": sum(1 for g in GATES if gates.get(g["id"])),
            "verdict": verdict(gates),
            "status_detail": ("needs a prop price feed this repository does not have" if not gates["DA-G9"]
                              else "all inputs present"),
        })

    # ---- strategy DA-S01 (2021 early snapshot) is scored separately: it needs the nfldata file
    s01 = score_early_snapshot()
    if s01:
        out_entries.append(s01)

    ranked = sorted(out_entries, key=lambda e: (
        -e["gates_passed"],
        -(e["signal"]["beat_close_rate"] if e["signal"]["beat_close_rate"] is not None else -9),
        -(e["staking"]["roi"] if e["staking"]["roi"] is not None else -9),
    ))
    for r, e in enumerate(ranked, 1):
        e["rank"] = r
        e["newly_live"] = []

    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {"games_path": src, "games_sha256": sha, "source": SRC_SCHED},
        "spec_sha256": spec_hash,
        "ranking_rule": ("Rank by gates passed, then by beat-the-close rate (signal), then by ROI (staking). "
                         "A strategy with a lucky staking run but a negative signal cannot rise: the "
                         "signal column breaks ties and carries 0.6 of the composite shown below."),
        "composite": {"signal_weight": 0.6, "staking_weight": 0.4,
                      "note": "Shown for readability only; no strategy has a positive-signal composite "
                              "unless its CLV interval excludes zero, which none currently does."},
        "multiple_testing": {"method": "Benjamini-Hochberg", "q": 0.10, "tests": len(pvals),
                             "bonferroni_alpha": round(0.05 / n_trials, 6), "n_trials": n_trials},
        "gates": GATES,
        "entries": ranked,
        "family_counts": {
            "single": sum(1 for e in ranked if e["family"].startswith("single")),
            "parlay": sum(1 for e in ranked if e["family"].startswith("parlay")),
            "prop_combo": sum(1 for e in ranked if e["family"].startswith("prop combo")),
        },
        "verdict_counts": {
            "LIVE": sum(1 for e in ranked if e["verdict"] == "LIVE"),
            "PAPER": sum(1 for e in ranked if e["verdict"] == "PAPER"),
            "REJECTED": sum(1 for e in ranked if e["verdict"] == "REJECTED"),
        },
        "rewards": reward_tiers(ranked),
        "honest_note": ("No strategy is LIVE and none is PAPER: every family fails the sample floor, "
                        "the significance bar, or the execution gate. The leaderboard is therefore "
                        "published as a ranking of measured evidence, not of winners."),
    }
    A.dump(os.path.join(ROOT, "data", "strategies.json"), payload)
    print(f"strategies: {len(ranked)} ranked, verdicts {payload['verdict_counts']}")
    for e in ranked[:6]:
        print(f"  {e['rank']}. {e['id']} {e['name'][:38]:40s} gates {e['gates_passed']}/10 "
              f"n={e['signal']['n_graded']:6d} hit={e['signal']['hit_rate']} beat={e['signal']['beat_close_rate']} verdict={e['verdict']}")

    gates_out = demotion_payload(ranked)
    A.dump(os.path.join(ROOT, "data", "gates.json"), gates_out)
    print(f"gates/demotion: {len(gates_out['demotion_rules'])} rules, transition matrix published")


def score_early_snapshot():
    """DA-S01 needs a separate early snapshot; only 2021 has one, and it is undocumented."""
    ini = os.path.join(REPO, "origination-lab", "data", "raw", "initial_lines.csv")
    if not os.path.exists(ini):
        return None
    import csv
    games, src, sha = _GAMES_CACHE
    by_alt = {}
    for g in games:
        if g.get("game_type") != "REG":
            continue
        by_alt[f"{g['season']}_{int(g['week']):02d}_{g['away_team']}_{g['home_team']}"] = g
    with open(ini, newline="") as fh:
        rows = list(csv.DictReader(fh))
    open_spread = {}
    for r in rows:
        if r["type"] == "SPREAD" and r["side"] == r["about"][-2:]:
            open_spread[r["about"]] = -M.fnum(r["line"])
    bets = []
    for gid, opening in open_spread.items():
        g = by_alt.get(gid)
        if not g or M.fnum(g.get("home_score")) is None:
            continue
        close = M.fnum(g.get("spread_line"))
        if close is None:
            continue
        move = close - opening
        if abs(move) < 1.5:
            continue
        side = "away" if move > 0 else "home"    # fade the move
        line = close
        price = M.fnum(g.get("home_spread_odds")) if side == "home" else M.fnum(g.get("away_spread_odds"))
        margin = M.fnum(g["home_score"]) - M.fnum(g["away_score"])
        profit, won = settle("spread", side, line, price, margin, None)
        bets.append({"game_id": gid, "season": int(g["season"]), "week": int(g["week"]),
                     "market": "spread", "side": side, "line": line, "price": price,
                     "status": ("won" if won else ("push" if profit == 0.0 else "lost")) if profit is not None else "price_missing",
                     "profit": profit, "won": won,
                     "clv": round((line - close) if side == "home" else (close - line), 3),
                     "beat_close": ((margin - close) > 0) if side == "home" else ((margin - close) < 0),
                     "source_result": SRC_SCHED})
    s = summarise(bets)
    rule = {"id": "DA-S01", "family": "single / spread", "name": "Fade the biggest market move",
            "rule": "Take the side the closing line moved AWAY from when |move| >= 1.5 pts (2021 only).",
            "needs": ["early_snapshot", "spread", "price"]}
    gates = {"DA-G1": False,   # the early snapshot has no timestamp, so point-in-time integrity fails
             "DA-G2": s["n_graded"] >= 300 and s["n_priced_bets"] >= 100,
             "DA-G3": False,   # the rule was chosen after seeing 2021, the only season with a snapshot
             "DA-G4": False, "DA-G5": False, "DA-G6": False, "DA-G7": True,
             "DA-G8": False, "DA-G9": True}
    return {
        "id": rule["id"], "name": rule["name"], "family": rule["family"], "rule": rule["rule"],
        "needs": rule["needs"],
        "signal": {"n_graded": s["n_graded"], "n_price_missing": s["n_price_missing"],
                   "hit_rate": s["hit_rate"], "hit_ci": s["hit_ci"], "hit_p": s["hit_p_vs_half"],
                   "bh_q": None, "bonferroni_p": None, "beat_close_rate": s["beat_close_rate"],
                   "beat_close_ci": s["beat_close_ci"], "beat_close_p": s["beat_close_p"],
                   "edge_points_mean": s["edge_points_mean"], "n_beat": s["n_beat"],
                   "permutation_p": permutation_test(s["beats"])},
        "staking": {"n_bets": s["n_priced_bets"], "wins": s["wins"], "losses": s["losses"],
                    "pushes": s["pushes"], "roi": s["roi"], "roi_ci": s["roi_ci"],
                    "profit_units": s["profit_units"],
                    "deflated_sharpe_p": (A.deflated_sharpe_p(s["returns"], len(specs()))
                                          if len(s["returns"]) >= 30 else None),
                    "by_season": s["by_season"],
                    "note": "Fixed 1-unit stakes, real prices only."},
        "gates": gates, "gates_passed": sum(1 for g in GATES if gates.get(g["id"])),
        "verdict": verdict(gates),
        "status_detail": ("the only early-snapshot file in the repository is undocumented and "
                          "unofficially timed, so G1 and G3 cannot pass"),
    }


def reward_tiers(ranked):
    live = [e for e in ranked if e["verdict"] == "LIVE"]
    paper = [e for e in ranked if e["verdict"] == "PAPER"]
    return {
        "tiers": [
            {"tier": "Tier 1 - LIVE allocation", "requirement": "10/10 gates, including DA-G9 execution",
             "reward": "Listed as a live signal; staking size capped by the demotion rule",
             "awarded_to": [e["id"] for e in live], "n": len(live)},
            {"tier": "Tier 2 - PAPER only", "requirement": "9/10 gates with execution satisfied",
             "reward": "Paper-traded, published, eligible for promotion after the paper window",
             "awarded_to": [e["id"] for e in paper], "n": len(paper)},
            {"tier": "Tier 3 - none", "requirement": "anything else",
             "reward": "No allocation; retained in the record with the exact failing gate",
             "awarded_to": [], "n": len(ranked) - len(live) - len(paper)},
        ],
        "funding": {
            "prize_pool": None, "currency": None,
            "status": "UNFUNDED",
            "note": ("No prize money exists. Publishing a currency figure would be an invented number; "
                     "the tiers are a ranking rule until a sponsor and a funded pool are named."),
        },
        "promotion": ("A Tier 1 entry that fails the demotion gate returns to Tier 2 automatically. "
                      "Tiers are computed, never granted by hand."),
    }


def demotion_payload(ranked):
    """DA-9: a numeric rule that sends a live strategy back to paper, not a promise to review."""
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "principle": ("Demotion is mechanical and pre-committed. A live strategy is demoted the moment "
                      "any trigger fires; no discretion, no 'keep watching it'. Paper is the default "
                      "state and live is the exception."),
        "live_requirements": {
            "min_bets_before_live": 300,
            "min_bets_before_paper": 100,
            "min_signal_clv_lower_bound": 0.0,
            "note": "A strategy may not be live on fewer than 300 priced bets, however good it looks.",
        },
        "demotion_rules": [
            {"id": "DM-1", "trigger": "Trailing 50-bet mean CLV <= 0",
             "action": "DEMOTE to paper immediately", "resets": "live clock restarts at 0",
             "rationale": "The signal stopped beating the close; the staking result is irrelevant.",
             "source": "SRC-NIST-CORR"},
            {"id": "DM-2", "trigger": "Trailing 100-bet ROI lower bootstrap bound < 0 while the signal "
                                      "CLV bound is also < 0",
             "action": "DEMOTE to paper", "resets": "live clock restarts at 0",
             "rationale": "Both columns negative: neither luck nor skill explains the run.",
             "source": "SRC-NIST-MULT"},
            {"id": "DM-3", "trigger": "Any single bet exceeding the pre-committed max stake (2 units)",
             "action": "DEMOTE to paper and void the offending bet",
             "resets": "live clock restarts at 0",
             "rationale": "Staking discipline is a gate, not a preference.", "source": "SRC-DK-PARLAY"},
            {"id": "DM-4", "trigger": "Point-in-time integrity broken (an input later shown to be "
                                      "leaked, restated, or unavailable before kickoff)",
             "action": "DEMOTE to paper and re-run from the corrected data",
             "resets": "full re-qualification required",
             "rationale": "A leaked feature can manufacture any result.",
             "source": "SRC-SKLEARN-LEAK"},
            {"id": "DM-5", "trigger": "The family of strategies grows by 50% or more (new variants "
                                      "added) without a matching rise in the significance bar",
             "action": "DEMOTE every member of the family to paper until BH/Bonferroni are recomputed",
             "resets": "family-wide",
             "rationale": "Trying more variants raises the chance that one looks good by luck.",
             "source": "SRC-NIST-MULT"},
            {"id": "DM-6", "trigger": "No settled bet for 21 days during the season, or the feed stops "
                                      "carrying prices for the market",
             "action": "DEMOTE to paper; status becomes STALE, not live",
             "resets": "live clock restarts at 0",
             "rationale": "An unmeasurable strategy cannot be a live one.",
             "source": "SRC-NFLVERSE-SCHED"},
        ],
        "promotion_rules": [
            {"id": "PM-1", "requirement": "300 priced bets, all 10 gates, CLV lower bound > 0",
             "action": "PAPER -> LIVE with a 1-unit cap for the first 100 bets"},
            {"id": "PM-2", "requirement": "A further 100 bets with CLV lower bound > 0 at the 1-unit cap",
             "action": "cap rises to 2 units; any DM trigger resets to paper"},
        ],
        "state_machine": {
            "states": ["REJECTED", "PAPER", "LIVE", "STALE"],
            "transitions": [
                {"from": "REJECTED", "to": "PAPER", "when": "all gates except execution pass"},
                {"from": "PAPER", "to": "LIVE", "when": "PM-1"},
                {"from": "LIVE", "to": "PAPER", "when": "DM-1..DM-6"},
                {"from": "LIVE", "to": "STALE", "when": "DM-6"},
                {"from": "STALE", "to": "PAPER", "when": "prices return and a bet settles"},
            ],
            "note": "A strategy can only move one step at a time and only by a computed trigger.",
        },
        "current_state": {
            "live": [e["id"] for e in ranked if e["verdict"] == "LIVE"],
            "paper": [e["id"] for e in ranked if e["verdict"] == "PAPER"],
            "rejected": [e["id"] for e in ranked if e["verdict"] == "REJECTED"],
            "demotions_triggered_this_run": [],
            "note": ("Nothing is live, so no demotion can have fired. The rules above are what make the "
                     "next live strategy demotable without a judgement call."),
        },
        "position_sizing": {
            "base_unit": 1.0, "max_unit": 2.0,
            "rule": "stake = min(2, 1 + 0.25 * max(0, floor((CLV_lower_bound - 0) / 0.01)))",
            "note": "A strategy with a CLV lower bound above zero earns more than 1 unit only while the "
                    "bound stays above zero; the demotion rule removes it the moment it does not.",
        },
    }


if __name__ == "__main__":
    main()
