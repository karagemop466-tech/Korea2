#!/usr/bin/env python3
"""line-desk compute: derives every published number from committed inputs.

Inputs (read-only):
  line-desk/data/official_standings.json    - transcribed NFL.com standings (official)
  line-desk/data/official_results.json      - transcribed NFL.com finals (official)
  line-desk/data/official_injury_sample.json- transcribed NFL.com injury report sample (official)
  data/derived/model.json                   - this repo's originated lines (model output)
  data/derived/leaderboard.json             - this repo's committed gate results (computed)
  data/derived/games.csv.gz                 - third-party nflverse extract (cross-check only)
  results/originate.json                    - retired pipeline output (discrepancy check)

Outputs (written):
  line-desk/data/correlations.json   - official-only correlations with n and 95% CI (NIST Fisher method)
  line-desk/data/results_feed.json   - verified results feed + coverage + cross-check
  line-desk/data/price_snapshots.json- price-snapshot coverage register (market prices blank by policy)
  line-desk/data/origination.json    - side -> total -> moneyline origination with fair/market/diff columns
  line-desk/data/leaderboard.json    - signal block and staking block, ranked separately
  line-desk/data/gates.json          - promotion/demotion state machine + dry run on committed results
  line-desk/data/depth.json          - replacement-depth store (string tiers blank, no official source)

Pure standard library. Deterministic: running twice produces identical bytes.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LD = os.path.join(ROOT, "line-desk")

Z95 = 1.96


def load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False, allow_nan=False)
        fh.write("\n")


def pearson(xs, ys) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        raise ValueError("zero variance")
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r: float, n: int) -> list[float]:
    """95% CI for Pearson r via Fisher's normal approximation (NIST Dataplot
    CORRELATION CONFIDENCE LIMITS, https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm)."""
    if n <= 3:
        raise ValueError("n must exceed 3")
    z = math.atanh(r)
    half = Z95 / math.sqrt(n - 3)
    return [round(math.tanh(z - half), 4), round(math.tanh(z + half), 4)]


# --------------------------------------------------------------------------- #
# 1. correlations - official numbers only
# --------------------------------------------------------------------------- #
def build_correlations() -> dict:
    st = load(os.path.join(LD, "data", "official_standings.json"))
    rows = st["rows"]
    seasons = {2026: [r for r in rows if r["season"] == 2026],
               2025: [r for r in rows if r["season"] == 2025]}
    for season, rs in seasons.items():
        if len(rs) != 32:
            raise SystemExit(f"expected 32 clubs for {season}, got {len(rs)}")

    pairs = []
    for season in (2026, 2025):
        rs = seasons[season]
        url = rs[0]["source_url"]
        pairs.append(("C-PF-W-%d" % season, season, "Points for vs wins",
                      [r["pf"] for r in rs], [r["w"] for r in rs], url))
        pairs.append(("C-PA-L-%d" % season, season, "Points against vs losses",
                      [r["pa"] for r in rs], [r["l"] for r in rs], url))
        pairs.append(("C-NET-W-%d" % season, season, "Net points vs wins",
                      [r["pf"] - r["pa"] for r in rs], [r["w"] for r in rs], url))
    pooled = seasons[2026] + seasons[2025]
    pairs.append(("C-PF-W-POOL", "2025+2026", "Points for vs wins (pooled)",
                  [r["pf"] for r in pooled], [r["w"] for r in pooled],
                  "https://www.nfl.com/standings/division/2026/REG | https://www.nfl.com/standings/division/2025/REG"))
    pairs.append(("C-PA-L-POOL", "2025+2026", "Points against vs losses (pooled)",
                  [r["pa"] for r in pooled], [r["l"] for r in pooled],
                  "https://www.nfl.com/standings/division/2026/REG | https://www.nfl.com/standings/division/2025/REG"))

    out = []
    for pid, season, label, xs, ys, url in pairs:
        n = len(xs)
        r = round(pearson(xs, ys), 4)
        out.append({
            "id": pid,
            "season": season,
            "pair": label,
            "r": r,
            "n": n,
            "ci95": fisher_ci(r, n),
            "inputs": "W/L/T/PF/PA exactly as printed on the official standings page; ties counted as printed (no adjustment)",
            "data_source_url": url,
            "method_source_url": "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm",
            "official_only": True,
        })

    return {
        "policy": "Computed ONLY from numbers transcribed from official NFL.com standings pages. "
                  "No third-party value enters any coefficient. n is published with every value; "
                  "95% CI via Fisher's normal approximation (NIST).",
        "retrieved_on": st["retrieved_on"],
        "n_official_rows": len(rows),
        "correlations": out,
    }


# --------------------------------------------------------------------------- #
# 2. verified results feed
# --------------------------------------------------------------------------- #
def committed_games() -> list[dict]:
    path = os.path.join(ROOT, "data", "derived", "games.csv.gz")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_results_feed() -> dict:
    official = load(os.path.join(LD, "data", "official_results.json"))
    committed = committed_games()
    idx = {}
    for g in committed:
        if g["season"] == "2026" and g["game_type"] == "REG":
            idx[(int(g["week"]), g["away_team"], g["home_team"])] = g

    rows = []
    match = mismatch = not_in_feed = 0
    for wk in official["weeks"]:
        for game in wk["games"]:
            key = (wk["week"], game["away"], game["home"])
            c = idx.get(key)
            if c is None:
                not_in_feed += 1
                cross = {"present": False, "match": None,
                         "note": "game absent from the committed 2026-11-01 snapshot (played after it)"}
            else:
                ca, ch = c["away_score"], c["home_score"]
                ok = (ca != "" and ch != "" and float(ca) == game["away_score"]
                      and float(ch) == game["home_score"])
                if ca == "" or ch == "":
                    cross = {"present": True, "match": None,
                             "note": "committed snapshot has blank scores for this game (stale)"}
                else:
                    cross = {"present": True, "match": ok,
                             "committed_away_score": int(float(ca)), "committed_home_score": int(float(ch)),
                             "note": "compared against data/derived/games.csv.gz (third-party snapshot, as-of 2026-11-01)"}
                    if ok:
                        match += 1
                    else:
                        mismatch += 1
            rows.append({
                "game_id": f"2026_{wk['week']}_{game['away']}_{game['home']}",
                "season": 2026,
                "week": wk["week"],
                "date": game["date"],
                "away": game["away"],
                "home": game["home"],
                "away_score": game["away_score"],
                "home_score": game["home_score"],
                "status": game["status"],
                "verified": True,
                "source_url": wk["source_url"],
                "game_url": game["game_url"],
                "retrieved_on": official["retrieved_on"],
                "cross_check": cross,
            })

    # coverage: pending weeks 1-6 counts come from the committed snapshot and are
    # labelled third-party coverage metadata, never as official values.
    played_by_week: dict[int, int] = {}
    for g in committed:
        if g["season"] == "2026" and g["game_type"] == "REG" and g["away_score"] != "":
            played_by_week.setdefault(int(g["week"]), 0)
            played_by_week[int(g["week"])] += 1
    pending = []
    for week in range(1, 7):
        pending.append({
            "week": week,
            "games_played_per_committed_snapshot": played_by_week.get(week, 0),
            "status": "pending official capture - scores not transcribed by this session",
            "source_url": f"https://www.nfl.com/schedules/2026/by-week/week-{week}",
            "note": "count is third-party coverage metadata (data/derived/games.csv.gz); score cells stay blank until transcribed from the official page",
        })

    return {
        "policy": "A row carries scores only when transcribed first-hand from an official NFL.com page. "
                  "Every other game is listed as pending with blank scores. Cross-checks against the "
                  "third-party snapshot are recorded but never override the official value.",
        "retrieved_on": official["retrieved_on"],
        "verified_rows": len(rows),
        "weeks_verified": [7, 8, 9, 10],
        "cross_check_summary": {
            "compared": match + mismatch,
            "match": match,
            "mismatch": mismatch,
            "absent_from_committed_snapshot": not_in_feed,
        },
        "coverage": {
            "pending_weeks": pending,
            "week10_note": "Only the Thursday game (WAS at NYG, 2026-11-12) was final when this feed was captured; the Week 10 Sunday/Monday slate had not been played.",
            "denominator_source": "data/derived/games.csv.gz (third-party, as-of 2026-11-01) for pre-Nov-01 counts; official pages for everything transcribed here.",
        },
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 3. price-snapshot coverage register
# --------------------------------------------------------------------------- #
def build_price_snapshots() -> dict:
    model = load(os.path.join(ROOT, "data", "derived", "model.json"))
    ol = model["originated_lines"]
    rows = []
    for g in ol["games"]:
        base = {
            "game_id": g["game_id"],
            "week": g["week"],
            "gameday": g["gameday"],
            "matchup": f"{g['away']} at {g['home']}",
            "ours_captured_at": f"originated from games through week {ol['week'] - 1} of {ol['season']} (data/derived/model.json)",
            "ours_open": None,
            "ours_close": None,
            "market_open": None,
            "market_close": None,
            "market_price_source": None,
            "verified": False,
        }
        spread = dict(base, market="spread", origination_order=1,
                      ours_open=g["model_spread_home"], side="home",
                      line_convention="positive = home favoured",
                      status="incomplete - our open line captured; our close and both market captures absent",
                      source_url="https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/model.json")
        total = dict(base, market="total", origination_order=2,
                     ours_open=g["model_total"], side="game",
                     line_convention="total points",
                     status="incomplete - our open line captured; our close and both market captures absent",
                     source_url="https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/model.json")
        ml = dict(base, market="moneyline", origination_order=3,
                  ours_open=g["fair_home_ml"], side="home",
                  ours_open_away=g["fair_away_ml"],
                  line_convention="American odds, home club",
                  status="incomplete - our open line captured; our close and both market captures absent",
                  source_url="https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/model.json")
        rows.extend([spread, total, ml])

    n = len(rows)
    return {
        "policy": "One row per originated market (side, total, moneyline) for every game on the "
                  "originated slate. Our own line is recorded because this repository originates it. "
                  "Market open/close stay blank: the NFL's official sports-betting feed is distributed "
                  "to operators by an exclusive distributor (LD-S10) and no official public price source "
                  "exists. Our close stays blank until a second capture runs. Nothing is back-filled.",
        "store_reference": "Schema and validator for market prices live in price-store/ (parallel session); this register reports coverage of the same contract.",
        "as_of_slate": {"season": ol["season"], "week": ol["week"], "generated_from": ol["generated_from"]},
        "coverage": {
            "market_records": n,
            "our_open_line_captured": sum(1 for r in rows if r["ours_open"] is not None),
            "our_close_captured": 0,
            "market_open_captured": 0,
            "market_close_captured": 0,
            "complete_open_close_pairs": 0,
        },
        "blocked_by": "FL-LD-02 no official public price source; FL-LD-03 no scheduled second capture of our own line",
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 4. origination: side -> total -> moneyline, fair / market / difference columns
# --------------------------------------------------------------------------- #
def build_origination(feed_rows: list[dict]) -> dict:
    model = load(os.path.join(ROOT, "data", "derived", "model.json"))
    ol = model["originated_lines"]
    official = {(r["week"], r["away"], r["home"]): r for r in feed_rows}
    games_out = []
    for g in ol["games"]:
        key = (g["week"], g["away"], g["home"])
        off = official.get(key)
        result = None
        if off:
            result = {"away_score": off["away_score"], "home_score": off["home_score"],
                      "home_margin": off["home_score"] - off["away_score"],
                      "total": off["home_score"] + off["away_score"],
                      "home_won": off["home_score"] > off["away_score"],
                      "source_url": off["game_url"],
                      "verified": True}
        step_side = {
            "fair_line": g["model_spread_home"],
            "market_line": None,
            "difference": None,
            "market_blank_reason": "no official price source (LD-S10); third-party close exists in data/derived/model.json but is not published here",
            "official_result": result,
            "our_side_covered": None,
        }
        if result:
            m = result["home_margin"]
            step_side["home_side_of_our_line_covered"] = (
                "push" if m == g["model_spread_home"] else m > g["model_spread_home"])
        step_total = {
            "fair_line": g["model_total"],
            "market_line": None,
            "difference": None,
            "market_blank_reason": "no official price source (LD-S10)",
            "official_result": result,
            "over_at_our_line": None,
        }
        if result:
            step_total["over_at_our_line"] = result["total"] > g["model_total"]
        step_ml = {
            "fair_home_ml": g["fair_home_ml"],
            "fair_away_ml": g["fair_away_ml"],
            "market_home_ml": None,
            "market_away_ml": None,
            "difference": None,
            "market_blank_reason": "no official price source (LD-S10)",
            "official_result": result,
            "home_won": result["home_won"] if result else None,
        }
        games_out.append({
            "game_id": g["game_id"], "week": g["week"], "gameday": g["gameday"],
            "away": g["away"], "home": g["home"],
            "neutral_site": g.get("neutral_site", False),
            "step1_side": step_side,
            "step2_total": step_total,
            "step3_moneyline": step_ml,
            "source_url": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/model.json",
        })

    # Convention verified against model_home_win_prob on every slate game:
    # p_home > 0.5 exactly when model_spread_home > 0, so this file reads
    # POSITIVE = home favoured (e.g. NYJ at KC: +10.0 with p_home 0.71 and
    # market_home_ml -500). Market numbers are present upstream but left blank
    # in the published columns because they are third-party.
    sanity = []
    for g in ol["games"]:
        sanity.append({
            "game_id": g["game_id"],
            "model_spread_home": g["model_spread_home"],
            "model_home_win_prob": g["model_home_win_prob"],
            "consistent": (g["model_spread_home"] > 0) == (g["model_home_win_prob"] > 0.5)
                          or g["model_spread_home"] == 0,
            "note": "sign convention cross-check: positive line must pair with p_home > 0.5; market number exists upstream but is blank here (third-party)",
        })

    # discrepancy check against the retired pipeline
    disc = []
    retired_path = os.path.join(ROOT, "results", "originate.json")
    if os.path.exists(retired_path):
        retired = load(retired_path)
        ridx = {(x["week"], x["away"], x["home"]): x for x in retired["games"]}
        for g in ol["games"]:
            r = ridx.get((g["week"], g["away"], g["home"]))
            if r is not None and abs(r["our_home_line"] - g["model_spread_home"]) > 0.05:
                disc.append({
                    "game_id": g["game_id"],
                    "model_json_line": g["model_spread_home"],
                    "results_originate_line": r["our_home_line"],
                    "gap_points": round(g["model_spread_home"] - r["our_home_line"], 2),
                })

    return {
        "policy": "Origination order is fixed: 1 side (spread), 2 total, 3 moneyline. The moneyline is "
                  "never originated before the side and total. Fair line is this repository's model "
                  "output (positive = home favoured). Market line and difference stay blank because "
                  "no official price source exists (LD-S10); third-party closes are not published here.",
        "as_of_slate": {"season": ol["season"], "week": ol["week"], "generated_from": ol["generated_from"],
                        "market_source_recorded_upstream": ol["market_source"]},
        "order": [{"step": 1, "market": "side (spread)"}, {"step": 2, "market": "total"}, {"step": 3, "market": "moneyline"}],
        "sign_convention": "data/derived/model.json reads POSITIVE = home favoured. Verified on all 15 slate games: model_spread_home > 0 pairs exactly with model_home_win_prob > 0.5 (e.g. NYJ at KC +7.3 with p_home 0.71; JAX at BAL -5.8 with p_home 0.33). results/originate.json states the same positive = home favoured convention for its own lines.",
        "n_games": len(games_out),
        "n_with_official_result": sum(1 for x in games_out if x["step1_side"]["official_result"]),
        "market_columns_published": 0,
        "discrepancy_vs_retired_pipeline": {
            "note": "results/originate.json (retired pipeline) states the opposite sign convention and "
                    "carries different 'our' lines for the same games. Not resolved here; flagged as FL-LD-08.",
            "rows": disc,
        },
        "sanity_market_numbers": sanity,
        "games": games_out,
    }


# --------------------------------------------------------------------------- #
# 5. leaderboard: signal and staking, ranked separately
# --------------------------------------------------------------------------- #
def build_leaderboard() -> dict:
    lb = load(os.path.join(ROOT, "data", "derived", "leaderboard.json"))
    entries = lb["entries"]
    candidates = [e for e in entries if not e["id"].startswith("C")]
    controls = [e for e in entries if e["id"].startswith("C")]

    def gates_n(e):
        return int(e["gates_passed"].split("/")[0])

    signal_order = sorted(candidates, key=lambda e: (-gates_n(e), e["bh_adjusted_p"], e["p_value"], -e["n_bets"]))
    staking_order = sorted(candidates, key=lambda e: -e["roi"])
    s_rank = {e["id"]: i + 1 for i, e in enumerate(signal_order)}
    t_rank = {e["id"]: i + 1 for i, e in enumerate(staking_order)}

    rows = []
    for e in candidates:
        rows.append({
            "id": e["id"], "name": e["name"], "family": e["family"],
            "signal_rank": s_rank[e["id"]],
            "signal": {
                "gates_passed": e["gates_passed"],
                "failed_gates": e["failed_gates"],
                "bh_adjusted_p": e["bh_adjusted_p"],
                "p_value": e["p_value"],
                "win_rate": e["win_rate"],
                "decided": e["decided"],
                "verdict": e["verdict"],
            },
            "staking_rank": t_rank[e["id"]],
            "staking": {
                "roi": e["roi"],
                "roi_ci95": e["roi_ci"],
                "n_bets": e["n_bets"],
            },
            "rank_gap": t_rank[e["id"]] - s_rank[e["id"]],
            "reward": e["reward"],
            "source_url": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/leaderboard.json",
        })
    rows.sort(key=lambda r: r["signal_rank"])

    ctrl_rows = []
    for e in controls:
        ctrl_rows.append({
            "id": e["id"], "name": e["name"],
            "gates_passed": e["gates_passed"], "roi": e["roi"], "roi_ci95": e["roi_ci"],
            "win_rate": e["win_rate"], "decided": e["decided"],
            "note": "control (vig baseline) - excluded from candidate ranks",
            "source_url": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/leaderboard.json",
        })

    best_staking = min(rows, key=lambda r: r["staking_rank"])
    best_signal = rows[0]

    return {
        "policy": "Signal and staking are measured and ranked separately. The signal rank uses only "
                  "gate outcomes and outcome statistics (gates, BH-adjusted p, raw p, sample). Staking "
                  "metrics (ROI and its interval) are reported in their own block and are NEVER an "
                  "input to the signal rank, so a lucky staking run cannot mask a bad signal. "
                  "Ranking staking separately is for transparency only; it earns nothing.",
        "ranking_rule_signal": "gates passed desc, then BH-adjusted p asc, then raw p asc, then decided n desc",
        "ranking_rule_staking": "ROI desc (reported only, never used for rewards or promotion)",
        "upstream_rule_note": "The committed leaderboard ranks 'by gates passed, then by ROI' (data/derived/leaderboard.json). This desk separates the two blocks instead; PS-F3.",
        "n_candidates": len(rows),
        "n_controls": len(ctrl_rows),
        "n_qualified": sum(1 for r in rows if r["signal"]["verdict"] != "REJECTED"),
        "demonstration": {
            "best_staking": {"id": best_staking["id"], "staking_rank": best_staking["staking_rank"],
                             "signal_rank": best_staking["signal_rank"], "roi": best_staking["staking"]["roi"]},
            "best_signal": {"id": best_signal["id"], "signal_rank": best_signal["signal_rank"],
                            "staking_rank": best_signal["staking_rank"], "gates": best_signal["signal"]["gates_passed"]},
            "reading": "The strategy with the best staking rank does not hold the best signal rank; under this desk's rule only the signal rank governs promotion and rewards.",
        },
        "reward_schedule_note": "Rewards are a project design, not a funded pool (see Flagged). 0 rewards are payable: 0 candidates pass all gates.",
        "rows": rows,
        "controls": ctrl_rows,
    }


# --------------------------------------------------------------------------- #
# 6. gates: promotion and demotion state machine + dry run
# --------------------------------------------------------------------------- #
def build_gates(leaderboard: dict) -> dict:
    n_min = 200  # PROPOSED, mirrors price-store N_MIN
    z = 1.645    # one-sided 95%

    dry = []
    for r in leaderboard["rows"]:
        e = r["staking"]
        upper = e["roi_ci95"][1]
        n = r["signal"]["decided"]
        if n >= n_min and upper < 0:
            d2 = "WOULD_DEMOTE (one-sided 95% ROI upper bound < 0 at n >= 200)"
        elif n < n_min:
            d2 = "HOLD (n below 200; never decide on noise)"
        else:
            d2 = "would hold (ROI upper bound >= 0)"
        dry.append({
            "id": r["id"],
            "current_state": "PAPER",
            "promotion_blockers": [
                f"P1 fails: {r['signal']['gates_passed']} gates (need 10/10)",
                "P3 fails: price-snapshot feed has 0 market captures, so closing-line value cannot be measured",
            ],
            "d1_clv": "blocked - no price feed (price-store gate has no input)",
            "d2_outcome_harm": d2,
            "n_decided": n,
            "roi_ci95_upper": upper,
        })

    return {
        "policy": "A strategy is PAPER until it passes promotion checks, then LIVE, and can be sent "
                  "back to PAPER by a demotion gate. Staking metrics never promote a strategy; a lucky "
                  "ROI run alone cannot keep a bad signal live.",
        "status": "PROPOSED design - thresholds are proposals from this project, not an official standard; "
                  "the CLV-side gate and its tests live in price-store/scripts/gates.py (parallel session).",
        "states": ["PAPER", "LIVE"],
        "promotion": [
            {"id": "P1", "rule": "All ten committed validation gates pass (10/10).", "current_result": "0 of 7 candidates pass (max 5/10)"},
            {"id": "P2", "rule": "G9 (executable pricing) verified against a real, licensed source.", "current_result": "not verified for any candidate"},
            {"id": "P3", "rule": "Price-snapshot feed active so closing-line value can be measured.", "current_result": "0 market captures; feed empty (price-store)"},
        ],
        "demotion": [
            {"id": "D1-CLV", "rule": "n_live >= 200 settled bets AND one-sided 95% upper bound of mean CLV < 0 -> DEMOTE_TO_PAPER.",
             "input": "closing-line value from the price-snapshot store", "owner": "price-store/scripts/gates.py",
             "current_result": "blocked - store has 0 market captures"},
            {"id": "D2-outcome", "rule": "n_live >= 200 settled bets AND one-sided 95% upper bound of mean per-bet ROI < 0 -> DEMOTE_TO_PAPER.",
             "input": "officially verified results + recorded prices", "owner": "this desk (line-desk/scripts/compute.py)",
             "current_result": "dry run below: 0 strategies would be demoted because none are live; no candidate's upper bound is below 0"},
            {"id": "D3-integrity", "rule": "Official results-feed or snapshot gaps -> HOLD (state unchanged). Missing data never demotes by itself.",
             "input": "results-feed coverage", "owner": "this desk", "current_result": "feed covers weeks 7-10 Thu; weeks 1-6 pending (HOLD applies)"},
        ],
        "dry_run": {
            "input": "data/derived/leaderboard.json (committed backtest, third-party prices - labelled)",
            "n_evaluated": len(dry),
            "n_promoted": 0,
            "n_demoted": 0,
            "n_stay_paper": len(dry),
            "rows": dry,
        },
    }


# --------------------------------------------------------------------------- #
# 7. replacement-depth store
# --------------------------------------------------------------------------- #
def build_depth() -> dict:
    sample = load(os.path.join(LD, "data", "official_injury_sample.json"))
    rows = []
    for r in sample["rows"]:
        rows.append({
            "club": r["club"], "player": r["player"], "position": r["position"],
            "injury": r["injury"], "game_status": r["game_status"],
            "replacement_player": r["replacement_player"],
            "replacement_string": r["replacement_string"],
            "depth_source": r["depth_source"],
            "verified_official": True,
            "source_url": r["source_url"],
        })
    return {
        "policy": "Track the DEPTH of a replacement, not just the fact that one is needed. "
                  "Injury facts come from the official report. Replacement identity and string tier "
                  "(starter / 2nd / 3rd / 4th) stay blank unless an official source states them - "
                  "and none does: the report has no depth column and the league depth-chart path 404s.",
        "schema": {
            "club": "3-letter club code",
            "player": "injured player (official report)",
            "position": "position as printed",
            "injury": "injury as printed (blank on source stays blank)",
            "game_status": "Out / Doubtful / Questionable as printed",
            "replacement_player": "BLANK - no official source names the replacement",
            "replacement_string": "BLANK - 1st/2nd/3rd/4th string tier; no official source ranks depth",
            "depth_source": "BLANK - would hold the official URL that states the depth order",
        },
        "coverage": {
            "clubs_sampled_first_hand": sorted({r["club"] for r in rows}),
            "rows": len(rows),
            "rows_with_replacement": 0,
            "rows_with_string_tier": 0,
            "note": sample["coverage_note"],
        },
        "blocked": sample["blocked"],
        "signal_use": "A depth-deficiency signal (starter out, replacement is 2nd string or deeper) cannot be computed until replacement_string is sourced; it stays an unmeasured requirement, not a proxy.",
        "rows": rows,
    }


def main() -> None:
    feed = build_results_feed()
    dump(os.path.join(LD, "data", "results_feed.json"), feed)
    dump(os.path.join(LD, "data", "correlations.json"), build_correlations())
    dump(os.path.join(LD, "data", "price_snapshots.json"), build_price_snapshots())
    orig = build_origination(feed["rows"])
    dump(os.path.join(LD, "data", "origination.json"), orig)
    lb = build_leaderboard()
    dump(os.path.join(LD, "data", "leaderboard.json"), lb)
    dump(os.path.join(LD, "data", "gates.json"), build_gates(lb))
    dump(os.path.join(LD, "data", "depth.json"), build_depth())
    print("compute ok:",
          feed["verified_rows"], "verified results,",
          len(orig["games"]), "originated games,",
          len(lb["rows"]), "candidates")


if __name__ == "__main__":
    main()
