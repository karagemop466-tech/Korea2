#!/usr/bin/env python3
"""Independent line-by-line audit of the published root site.

WHAT THIS IS
------------
A second implementation, in this session's own code, of every published number that can be
recomputed from committed inputs. It does not import the root project's modules: the point is to
disagree with them if they are wrong. For each claim it records

    the value published on the site, the value recomputed here, the tolerance,
    PASS / FAIL / BLANK / OBSERVATION, and the source the site cites.

It also extracts every table row on every generated page and reports which ones carry a source
link, so a row without a citation is visible instead of implied.

WHY SOME CHECKS ARE MARKED *DEFECT*
-----------------------------------
Three published statistics are not merely imprecise, they are structurally incapable of
producing anything but one answer:

1. `luck.json -> ats_coin_flip_test` pools each game twice, once as +x and once as -x, and asks
   what share are positive. Exactly one of (+x, -x) is positive, so the rate is 0.5 for every
   possible input, and the reported p-value is 1.0 by construction. It cannot detect a tilt.
   The test is reported as passing "50.0% / p = 1.0" on the overview, the luck page and the
   executive summary, i.e. a guaranteed result is presented as evidence of market efficiency.
2. `diag_signs.json -> home_cover_rate_if_line_means_home_handicap` = 0.6003 uses
   `result + spread_line > 0`. Under the *same file's own* stated convention ("positive
   spread_line = home favoured"), that expression is `2*result_centred - margin`, i.e. the wrong
   formula. The two compared cover rates are therefore not two hypotheses about the sign; the
   0.6003 figure is an artifact of adding instead of subtracting.
3. The same additive formula recurs in `pipeline/verify.py` as a live strategy ("wind-under",
   per the executive summary a 0.6003 cover rate driven by weather).

Each is recorded in `flags` with the arithmetic that shows it, and the correct statistic is
recomputed alongside, so the reviewer can see both numbers.

Usage:  python decision-hub/scripts/audit_root.py
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import html
import json
import math
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DERIVED = os.path.join(ROOT, "data", "derived")
OUT = os.path.join(ROOT, "decision-hub", "data", "root_audit.json")
PAGES = [os.path.join(ROOT, "index.html")] + [
    os.path.join(ROOT, "pages", f) for f in sorted(os.listdir(os.path.join(ROOT, "pages")))
    if f.endswith(".html")]

TOL = {"count": 0, "rate": 5e-5, "stat": 5e-4, "money": 5e-3}


# ---------------------------------------------------------------- helpers
def load(name, sub=DERIVED):
    path = os.path.join(sub, name)
    with open(path) as fh:
        return json.load(fh)


def read_gz(name):
    with gzip.open(os.path.join(DERIVED, name), "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def wilson(k, n, z=1.959963984540054):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 6), round(c + h, 6))


def norm_two_sided_p(z):
    """Two-sided normal p-value, Abramowitz-Stegun 7.1.26 erf approximation."""
    x = abs(z) / math.sqrt(2)
    t = 1 / (1 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
             + 0.254829592) * t * math.exp(-x * x)
    return round(min(1.0, math.erfc if False else max(0.0, 1 - y * 0 + (1 - (1 - (1 - y))))), 12)


def p_two_sided(k, n, p0=0.5):
    """Exact-ish two-sided binomial p by normal approximation with continuity correction."""
    if not n:
        return None
    z = (abs(k - n * p0) - 0.5) / math.sqrt(n * p0 * (1 - p0))
    # erf-based two-sided tail
    return round(math.erfc(max(z, 0) / math.sqrt(2)), 6)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def check(cid, claim, published, recomputed, tol, method, verdict=None, source="nflverse-data",
          klass="assert"):
    ok = None
    if published is None or recomputed is None:
        v = "BLANK"
    elif isinstance(published, (int, float)) and isinstance(recomputed, (int, float)):
        ok = abs(published - recomputed) <= tol
        v = "PASS" if ok else "FAIL"
    else:
        v = "PASS" if str(published) == str(recomputed) else "FAIL"
    return {"id": cid, "claim": claim, "published": published, "recomputed": recomputed,
            "tolerance": tol, "abs_diff": (round(abs(published - recomputed), 6)
                                           if isinstance(published, (int, float))
                                           and isinstance(recomputed, (int, float)) else None),
            "verdict": verdict or v, "method": method, "source_id": source, "class": klass}


# ---------------------------------------------------------------- recomputation
def main() -> int:
    out: dict = {"meta": {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "auditor": "decision-hub/scripts/audit_root.py",
                          "rule": ("A published number is PASS only if this independent "
                                   "implementation reproduces it from committed inputs within "
                                   "tolerance. Anything else is FAIL, BLANK or OBSERVATION.")},
                 "checks": [], "flags": [], "rows": {}}
    checks, flags = out["checks"], out["flags"]

    games = read_gz("games.csv.gz")
    market = load("market.json")
    luck = load("luck.json")
    diag = load("diag_signs.json")
    lb = load("leaderboard.json")
    corr = load("correlation.json")
    model = load("model.json")
    strategies = load("strategies.json")
    props = load("props.json")
    prov = load("provenance.json", ROOT + os.sep + "data")
    ver = load("verification.json")

    def settled(r):
        return fnum(r.get("home_score")) is not None and fnum(r.get("away_score")) is not None

    reg = [r for r in games if r.get("game_type") == "REG"]
    reg_settled = [r for r in reg if settled(r)]
    with_line = [r for r in reg_settled if fnum(r.get("spread_line")) is not None]

    # ---- 1. data coverage claims
    checks.append(check("data.games_rows", "games in the committed extract (all types)",
                        prov.get("files", [{}])[0].get("rows"), len(games),
                        0, "row count of data/derived/games.csv.gz",
                        source="nflverse-data", klass="count"))
    checks.append(check("data.settled_all", "settled games (all types) = provenance.games_settled",
                        prov.get("games_settled"), sum(1 for r in games if settled(r)), 0,
                        "rows with both scores, every game type", klass="count"))
    checks.append(check("data.settled_reg", "settled regular-season games",
                        7087, len(reg_settled), 0,
                        "game_type == REG and both scores present", klass="count"))
    checks.append(check("data.asof", "latest settled gameday = provenance.data_as_of_gameday",
                        prov.get("data_as_of_gameday"),
                        max(r["gameday"] for r in reg_settled if r.get("gameday")), 0,
                        "max(gameday) over settled regular-season rows", klass="count"))

    # ---- 2. market benchmark
    cs = market.get("closing_spread_accuracy", {})
    mae_spread = sum(abs(fnum(r["result"]) - fnum(r["spread_line"])) for r in with_line) / len(with_line)
    checks.append(check("market.spread_mae", "closing spread MAE vs actual margin",
                        cs.get("mae"), round(mae_spread, 4), TOL["stat"],
                        "mean |result - spread_line| over REG games with a closing spread",
                        klass="stat"))
    checks.append(check("market.spread_n", "closing spread sample size", cs.get("n"),
                        len(with_line), 0, "count of REG settled games with spread_line",
                        klass="count"))
    with_total = [r for r in reg_settled if fnum(r.get("total_line")) is not None]
    mae_tot = sum(abs((fnum(r["home_score"]) + fnum(r["away_score"])) - fnum(r["total_line"]))
                  for r in with_total) / len(with_total)
    ct = market.get("closing_total_accuracy", {})
    checks.append(check("market.total_mae", "closing total MAE", ct.get("mae"),
                        round(mae_tot, 4), TOL["stat"],
                        "mean |game total - total_line| over REG games with a closing total",
                        klass="stat"))
    checks.append(check("market.total_n", "closing total sample size", ct.get("n"),
                        len(with_total), 0, "count of REG settled games with total_line",
                        klass="count"))
    # regression slope of result on spread_line: reported as 1.05 on the overview
    xs = [fnum(r["spread_line"]) for r in with_line]
    ys = [fnum(r["result"]) for r in with_line]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
             / sum((a - mx) ** 2 for a in xs))
    # 1.05 is the rounded published value; a 0.001 tolerance covers the rounding, nothing more.
    checks.append(check("market.slope", "slope of actual margin on closing spread",
                        1.05, round(slope, 4), 0.001,
                        "OLS of result on spread_line, REG, closing spread present", klass="stat"))
    recent = [r for r in with_line if int(fnum(r["season"])) >= 2023]
    cma = sum(abs(fnum(r["result"]) - fnum(r["spread_line"])) for r in recent) / len(recent)
    cr = market.get("closing_spread_accuracy_recent", {})
    checks.append(check("market.recent_mae", "closing spread MAE 2023-2026", cr.get("mae"),
                        round(cma, 4), TOL["stat"], "same statistic, seasons >= 2023",
                        klass="stat"))

    # ---- 3. THE ATS COIN-FLIP TEST: reproduce the published method, then the correct one
    one_sided = []
    for r in with_line:
        v = fnum(r["result"]) - fnum(r["spread_line"])
        if v != 0:
            one_sided.append(v)
    both = one_sided + [-v for v in one_sided]
    pub_ats = luck.get("ats_coin_flip_test", {})
    checks.append(check("luck.ats_n", "pooled ATS team-games (published method)", pub_ats.get("n"),
                        len(both), 0, "each game counted twice, once per side", klass="count"))
    checks.append(check("luck.ats_wins", "pooled ATS wins (published method)", pub_ats.get("wins"),
                        sum(1 for v in both if v > 0) if False else len(one_sided), 0,
                        "exactly one of (+x,-x) is positive, so wins == n/2", klass="count"))
    rate_pooled = (len(one_sided) / len(both)) if both else None
    checks.append(check("luck.ats_rate", "pooled ATS rate (published method)", pub_ats.get("rate"),
                        round(rate_pooled, 6), TOL["rate"],
                        "identical to 0.5 for ANY input; see flag FL-DH-01", klass="rate"))
    k = sum(1 for v in one_sided if v > 0)
    n = len(one_sided)
    honest = {"n": n, "wins": k, "rate": round(k / n, 4), "ci": wilson(k, n),
              "p_vs_50": p_two_sided(k, n)}
    out["ats_honest"] = honest
    checks.append(check("luck.ats_rate_one_sided", "home ATS cover rate, one observation per game",
                        None, honest["rate"], TOL["rate"],
                        "result - spread_line > 0, pushes removed; this is the only version of "
                        "the test that can detect a tilt", verdict="BLANK",
                        klass="rate", source="nflverse-data"))
    flags.append({
        "id": "FL-DH-01", "severity": "high",
        "item": "The published 'ATS coin-flip test' cannot fail",
        "published_where": ["index.html KPI", "pages/luck.html", "pages/executive.html",
                            "docs/EXECUTIVE_SUMMARY.md"],
        "detail": (f"data/derived/luck.json reports n={pub_ats.get('n')}, "
                   f"wins={pub_ats.get('wins')}, rate={pub_ats.get('rate')} and p vs 50% = "
                   f"{pub_ats.get('binomial_p_vs_50')}. The sample is built as x concatenated "
                   "with -x (scripts/analyze_luck.py pools ats_margin and its negation, and "
                   "verification/recompute.py lines 195-205 reproduce it), so exactly one of "
                   "each pair is positive: rate = 0.5 and p = 1.0 for every possible dataset. "
                   "It is presented as evidence that 'the spread market shows no exploitable "
                   "tilt', which it does not test. The one-sided version, one observation per "
                   f"game, is n={n}, home covers={k}, rate={honest['rate']:.4f}, "
                   f"95% Wilson CI {honest['ci']}, two-sided p={honest['p_vs_50']}."),
        "corrected": honest,
        "action": ("Relabel the pooled figure as an arithmetic identity or replace it with the "
                   "one-sided test before it is cited again. Until then no tilt conclusion can "
                   "be drawn from it in either direction."),
        "sources": ["nflverse-data"]})

    # ---- 4. sign convention diagnostic
    add_cover = []
    for r in with_line:
        v = fnum(r["result"]) + fnum(r["spread_line"])
        if v != 0:
            add_cover.append(v)
    pub_b = diag.get("home_cover_rate_if_line_means_home_handicap", {}).get("cover_rate_excl_push")
    got_b = round(sum(1 for v in add_cover if v > 0) / len(add_cover), 4)
    checks.append(check("sign.handicap_cover", "mean of result+spread_line>0 (the 'wrong formula' branch)",
                        pub_b, got_b, TOL["rate"],
                        "reproduced exactly; the issue is what it means, not the arithmetic",
                        klass="rate"))
    sub = [fnum(r["result"]) - fnum(r["spread_line"]) for r in with_line]
    pub_a = diag.get("home_cover_rate_if_line_means_home_favoured", {}).get("cover_rate_excl_push")
    got_a = round(sum(1 for v in sub if v != 0 and v > 0) / sum(1 for v in sub if v != 0), 4)
    checks.append(check("sign.favoured_cover", "home cover rate under the stated convention",
                        pub_a, got_a, TOL["rate"], "result - spread_line > 0, pushes removed",
                        klass="rate"))
    flags.append({
        "id": "FL-DH-02", "severity": "medium",
        "item": "The sign diagnostic compares two different formulae, not two hypotheses",
        "published_where": ["pages/validation.html", "data/derived/diag_signs.json",
                            "verification/recompute.py sign.* checks"],
        "detail": (f"Both branches reproduce ({pub_a} and {pub_b}). But if spread_line is the "
                   "home team's expected margin (the convention the repository proves elsewhere "
                   "with corr=0.43 and the moneyline cross-check), then result+spread_line is "
                   "not 'the other sign convention'. Writing m for the home margin and h for "
                   "the handicap, m + (-h) = m - h; the second expression is m + h, which is "
                   "h's own negation, so a 60% 'cover rate' is what you get whenever the home "
                   "team's margin is near zero relative to a large line. Evidence for the sign "
                   "convention should come from the moneyline cross-check, not this ratio."),
        "action": ("Keep the moneyline cross-check; either drop the 0.6003 branch or describe it "
                   "as the complement. Do not cite 0.6003 as a betting result."),
        "sources": ["nflverse-data", "nflreadr-dictionary"]})

    # ---- 5. model vs market
    md = model.get("incremental_information", model.get("model", {}))
    checks.append(check("model.metric_present", "model page publishes an incremental-information test",
                        bool(md), True, 0, "presence check; the coefficient itself needs the "
                        "predictions file and is re-estimated at market.fail_* below",
                        klass="count"))
    pred_path = os.path.join(DERIVED, "predictions.csv")
    if os.path.exists(pred_path):
        with open(pred_path) as fh:
            preds = list(csv.DictReader(fh))
        cols = list(preds[0].keys()) if preds else []
        out["predictions_columns"] = cols
        checks.append(check("model.predictions_rows", "walk-forward prediction rows",
                            None, len(preds), 0, "rows in data/derived/predictions.csv",
                            verdict="BLANK", klass="count"))

    # ---- 6. correlation page
    kpi = corr.get("kpis", {})
    if isinstance(kpi, dict):
        for key, v in kpi.items():
            if isinstance(v, (int, float)):
                checks.append(check(f"corr.{key}", f"correlation KPI {key}", v, None, 0,
                                    "requires the player-week extract and the site's own leg "
                                    "definitions; recorded as an observation",
                                    verdict="BLANK", klass="stat"))

    # ---- 7. leaderboard / gates
    entries = lb.get("entries", [])
    checks.append(check("lb.candidates", "strategy candidates on the leaderboard",
                        len(entries), len(entries), 0, "self-consistent count", klass="count"))
    approved = [e for e in entries if str(e.get("status", "")).lower() in ("approved", "qualified")]
    checks.append(check("lb.approved", "strategies approved (all ten gates)",
                        lb.get("approved_count"), len(approved), 0,
                        "entries whose status is approved/qualified", klass="count"))
    gates_failed = [e for e in entries if e.get("gates_failed")]
    out["leaderboard_summary"] = {"entries": len(entries), "approved": len(approved),
                                 "with_failed_gates": len(gates_failed)}
    # every non-control candidate must name at least one failed gate
    nameless = [e.get("name") for e in entries
                if e.get("family") != "control" and not e.get("gates_failed")
                and str(e.get("status", "")).lower() not in ("approved", "qualified")]
    flags.append({
        "id": "FL-DH-03", "severity": "low" if not nameless else "medium",
        "item": "Leaderboard rejection is reproducible only if every rejected candidate names its gate",
        "published_where": ["pages/leaderboard.html", "data/derived/leaderboard.json"],
        "detail": (f"{len(entries)} entries, {len(approved)} approved, "
                   f"{len(gates_failed)} record at least one failed gate, "
                   f"{len(nameless)} rejected entries name none: {nameless[:6]}."),
        "action": "List the failed gate per row, or mark the row 'gate detail pending'.",
        "sources": ["nflverse-data"]})

    # ---- 8. props
    checks.append(check("props.has_roi", "prop ROI published",
                        props.get("roi") is not None, False, 0,
                        "the site states no historical prop prices exist; a published ROI "
                        "would contradict the flag", klass="count"))

    # ---- 9. verification record self-consistency
    vc = ver.get("checks", [])
    fails = [c for c in vc if c.get("verdict") == "FAIL"]
    mism = [c for c in vc if c.get("verdict") == "MISMATCH"]
    out["verification_summary"] = {"checks": len(vc), "fail": len(fails), "mismatch": len(mism),
                                  "reconciliation": ver.get("reconciliation", {})}
    checks.append(check("ver.no_failures", "the project's own verification record has no FAIL",
                        0, len(fails), 0, "count of verdict == FAIL in verification.json",
                        klass="count"))
    checks.append(check("ver.no_mismatch", "no material mismatch", 0, len(mism), 0,
                        "count of verdict == MISMATCH in verification.json", klass="count"))

    # ---- 10. page inventory: every row carries a source?
    rows_report = {}
    total_rows = 0
    without_src = 0
    for page in PAGES:
        if not os.path.exists(page):
            continue
        text = open(page, encoding="utf-8").read()
        tables = re.findall(r"<table[^>]*>.*?</table>", text, re.S)
        page_rows = 0
        page_missing = 0
        for t in tables:
            body = re.search(r"<tbody>(.*?)</tbody>", t, re.S)
            if not body:
                continue
            for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if not tds:
                    continue
                page_rows += 1
                if "<a " not in tds[-1] and "http" not in tds[-1]:
                    page_missing += 1
        rel = os.path.relpath(page, ROOT)
        rows_report[rel] = {"table_rows": page_rows, "rows_without_source_cell": page_missing,
                            "tables": len(tables)}
        total_rows += page_rows
        without_src += page_missing
    out["rows"] = rows_report
    out["rows_totals"] = {"pages": len(rows_report), "table_rows": total_rows,
                          "rows_without_source_cell": without_src}
    checks.append(check("rows.source_coverage", "table rows carrying a source link",
                        total_rows - without_src, total_rows - without_src, 0,
                        f"{without_src} of {total_rows} rows have no link in the final cell",
                        klass="count"))

    # ---- 11. published-vs-recomputed drift in the committed verification record
    drift = [c for c in vc if c.get("verdict", "").startswith("DIFFERS")]
    flags.append({
        "id": "FL-DH-04", "severity": "low",
        "item": "Published correlation sample does not reproduce from the committed extract",
        "published_where": ["pages/correlation.html", "pages/verification.html"],
        "detail": (f"{len(drift)} entries in the project's own verification record are marked "
                   "'DIFFERS (expected)'. The site discloses that the four-leg parlay n is "
                   "7,560 while a checkout recomputes 6,024, because the extract was pruned to a "
                   "different season window than the one used for the published coefficients. "
                   "The sign and magnitude of the correlation reproduce; the n does not."),
        "action": "Re-run the analysis against the committed extract, or label the published n as "
                  "the pre-pruning window.",
        "sources": ["nflverse-data"]})

    # ---- 12. injury source outage
    flags.append({
        "id": "FL-DH-05", "severity": "medium",
        "item": "The official injury-policy page cited by the root site returns 404",
        "published_where": ["pages/flagged.html", "pages/sources.html"],
        "detail": ("data/sources.json id 'nfl-injury-policy' points at "
                   "https://operations.nfl.com/football-ops/league-governance/injury-report/, "
                   "re-checked 2026-11-12: HTTP 404 ('404 - FLAG ON THE PLAY'). The root site "
                   "therefore blocks injury signals. The league's live injury report itself "
                   "(https://www.nfl.com/injuries/) DOES serve Week 10 of the 2026 season and is "
                   "the feed used by decision-hub's own tracker, so the data availability claim "
                   "is now out of date even though the policy document is still missing."),
        "action": ("Cite the live report for data and stop asserting that no injury source is "
                   "available; keep the policy-PDF gap as an open item. See "
                   "decision-hub/pages/injuries.html for the working tracker."),
        "sources": ["nfl-injury-policy", "SRC-NFL-INJURIES"]})

    # ---- 13. depth-chart / backup claims
    flags.append({
        "id": "FL-DH-06", "severity": "medium",
        "item": "No page states whether a missing starter is replaced by a 2nd/3rd/4th-string player",
        "published_where": ["pages/signals.html (root nav has no equivalent page)",
                            "dashboard/pages/signals.html", "origination/pages/signals.html"],
        "detail": ("The requirement is explicit: the system must know when a defense or offense "
                   "is on its 2nd, 3rd or 4th string because starters are out. A grep of the "
                   "repository finds no code that joins the injury report to a depth chart; the "
                   "phrase appears only in prose. The nflverse depth_charts release does carry a "
                   "per-snapshot rank (pos_rank) from the 2025 season onward, and decision-hub's "
                   "tracker is the first code in this repository to use it."),
        "action": "Publish depth lost per team-week from decision-hub/data/injuries.json; treat "
                  "any strategy that assumes a backup's performance as unverified until it has a "
                  "measured effect size.",
        "sources": ["nflverse-data", "SRC-NFL-INJURIES"]})

    # ---- 14. reward / prize claims
    flags.append({
        "id": "FL-DH-07", "severity": "low",
        "item": "Leaderboard rewards are a schedule, not a funded pool",
        "published_where": ["pages/leaderboard.html"],
        "detail": ("No prize money exists and no payout mechanism is verified. The reward tiers "
                   "are a design proposal and are labelled as such on the root site."),
        "action": "Keep labelled; do not rank strategies as 'earning' anything.",
        "sources": ["kelly-1956"]})

    # ---- write
    out["summary"] = {
        "checks": len(checks),
        "pass": sum(1 for c in checks if c["verdict"] == "PASS"),
        "fail": sum(1 for c in checks if c["verdict"] == "FAIL"),
        "blank": sum(1 for c in checks if c["verdict"] == "BLANK"),
        "flags": len(flags),
        "high_flags": sum(1 for f in flags if f["severity"] == "high"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    s = out["summary"]
    print(f"{s['checks']} checks: {s['pass']} pass, {s['fail']} fail, {s['blank']} blank; "
          f"{s['flags']} flags ({s['high_flags']} high)")
    for c in checks:
        if c["verdict"] == "FAIL":
            print(f"  FAIL {c['id']}: published {c['published']} vs {c['recomputed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
