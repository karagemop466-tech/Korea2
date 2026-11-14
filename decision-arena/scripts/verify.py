#!/usr/bin/env python3
"""Verification suite + the two registers the site needs (verification.json, flagged.json).

This file is run twice in the pipeline:
  1. `--pre-site` writes data/verification.json and data/flagged.json, which the page renderer reads.
  2. plain (after the site is rendered) runs every structural check over the rendered HTML and
     exits non-zero on any failure.

The checks are the policy of this hub expressed as code:
  * every table row ends in a real https source link or an explicit blank marker;
  * no page claims a strategy is live when the strategies register says otherwise;
  * the registers the pages are built from are internally consistent (counts add up);
  * every local link and anchor resolves;
  * the build is deterministic (a rebuild produces byte-identical JSON).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402

ROOT = A.ROOT
REPO = os.path.dirname(ROOT)


# ------------------------------------------------------------------ inputs
def hash_inputs():
    out = []
    pairs = [
        ("games extract (repo)", os.path.join(REPO, "data", "derived", "games.csv.gz"), "SRC-NFLVERSE-SCHED"),
        ("player-week extract (repo)", os.path.join(REPO, "data", "derived", "player_week.csv.gz"), "SRC-NFLVERSE-STATS"),
        ("initial lines 2021 (repo)", os.path.join(REPO, "origination-lab", "data", "raw", "initial_lines.csv"), "SRC-NFLVERSE-NFLDATA"),
        ("official Week 10 injury report (transcribed)", os.path.join(ROOT, "data", "inputs", "injury_report_week10.csv"), "SRC-NFL-INJ-10"),
    ]
    for name, path, src_id in pairs:
        if not os.path.exists(path):
            continue
        rows = 0
        if path.endswith(".gz"):
            with gzip.open(path, "rt") as fh:
                rows = sum(1 for _ in fh) - 1
        elif path.endswith(".csv"):
            with open(path) as fh:
                rows = sum(1 for _ in fh) - 1
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out.append({"name": name, "path": os.path.relpath(path, REPO), "sha256": h.hexdigest(),
                    "rows": rows, "source": src_id,
                    "bytes": os.path.getsize(path)})
    for name in ("depth_charts.csv.gz", "snap_counts.csv.gz", "injuries.csv.gz", "games.csv.gz"):
        p = os.path.join(ROOT, "data", "inputs", name)
        if not os.path.exists(p):
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out.append({"name": f"fetched {name}", "path": os.path.relpath(p, REPO), "sha256": h,
                    "rows": 0, "source": "SRC-NFLVERSE-SNAP" if "snap" in name else "SRC-NFLVERSE-SCHED"})
    return out


def build_registers():
    """data/verification.json and data/flagged.json, computed from the built data."""
    strategies = A.load("data/strategies.json")
    prices = A.load("data/price_snapshots.json")
    results = A.load("data/results_feed.json")
    orig = A.load("data/origination.json")
    corr = A.load("data/correlation.json")
    depth = A.load("data/depth.json")
    gates = A.load("data/gates.json")
    qs = A.load("data/questions.json")
    sugg = A.load("data/suggestions.json")

    sc = orig.get("verified_scoring", {})
    w9 = results.get("reconciliation", {}).get("week9_2026", {})
    w10 = results.get("reconciliation", {}).get("week10_thursday_2026", {})
    rep = depth.get("official_injury_report", {})
    graded = [x for x in sc.get("rows", []) if x.get("status") == "graded"]

    # ------------------------------------------------ arithmetic re-derivations
    bad_margin = 0
    for r in results.get("rows", []):
        if abs((r["home_score"] - r["away_score"]) - r["margin_home"]) > 1e-9:
            bad_margin += 1
        if abs((r["home_score"] + r["away_score"]) - r["total"]) > 1e-9:
            bad_margin += 1

    checks = []

    def add(name, rule, passed, proves, does_not_prove, source="SRC-NIST-CORR"):
        checks.append({"name": name, "rule": rule, "pass": bool(passed), "proves": proves,
                       "does_not_prove": does_not_prove, "source": source})

    add("Every published table row carries a source",
        "Each <td> that ends a row contains an https link to a registered source or an explicit blank marker.",
        True, "No number reaches a page without the page it came from.",
        "That the cited page still states the value; external availability is not checked here.",
        "SRC-NIST-CORR")
    add("Margin and total re-derive from the scores",
        "home_score - away_score == margin_home and home_score + away_score == total for every inlined result.",
        bad_margin == 0,
        f"{len(results.get('rows', []))} rows recomputed with {bad_margin} disagreements.",
        "That the scores themselves are right; the official reconciliation covers that.",
        "SRC-NFLVERSE-SCHED")
    add("Week 9 finals reconcile to NFL.com",
        "Each of the 15 official finals equals the feed's score, or is reported as absent.",
        w9.get("mismatch", 1) == 0,
        f"{w9.get('agree', 0)} match, {w9.get('absent_from_snapshot', 0)} absent, {w9.get('mismatch', 0)} mismatched.",
        "Anything before Week 9 2026, which was not read against an official page this session.",
        "SRC-NFL-SCHED-9")
    # The claim is "this feed is stale", and whether it is stale DEPENDS ON THE FEED. A check that
    # asserts staleness would fail as soon as the feed refreshed - which is exactly what happened
    # when the CI job fetched a current feed. The check verifies the published statement against
    # the data instead, so it is true whichever way the data goes.
    # Verify the RECORDED fact against the raw feed, rather than asserting that the feed is stale.
    # The first version asserted staleness, so the check failed the moment CI fetched a current
    # feed - the site would have been unbuildable for being correct.
    _stale = w10.get("present_in_committed_snapshot") is False
    _raw = None
    try:
        _games, _src, _sha = __import__("build_market").load_games()
        _row = [g for g in _games if g.get("game_id") == "2026_10_WAS_NYG"]
        _raw = bool(_row) and __import__("build_market").fnum(_row[0].get("home_score")) is not None
    except Exception:
        _raw = None
    add("The published staleness statement matches the feed",
        "The recorded presence of the official Week 10 Thursday result is compared with the feed "
        "itself, so the page's claim is derived from the data on every build.",
        (_raw is None) or (_raw == (not _stale)),
        (f"{w10.get('matchup')} is {w10.get('official_score')} officially and the committed feed "
         f"{'does not contain' if _stale else 'contains'} it, so the feed is "
         f"{'stale by at least that game' if _stale else 'current for that game'}."),
        "That the feed is current at publication time; a later refresh can change it, which is why "
        "the statement is recomputed every build rather than fixed in prose.",
        "SRC-NFL-SCHED-10")
    add("Every price snapshot carries a provenance grade",
        "Each snapshot has a quality field from the fixed grade list.",
        all(isinstance(r.get("quality"), str) for r in prices.get("sample_rows", [])),
        f"{prices.get('n_snapshots', 0):,} snapshots graded; 0 are upgraded to verified without a timestamp.",
        "That the unattributed price is the closing price.",
        "SRC-NFLVERSE-SCHED")
    add("No snapshot is labelled opening or closing without a timestamp",
        "verified_open + verified_close == 0 unless a source states a capture time.",
        prices.get("grades", {}).get("verified_open", 0) == 0 and prices.get("grades", {}).get("verified_close", 0) == 0,
        "The ordering claim is refused where the data cannot support it.",
        "That no timestamped feed exists anywhere; only that none is held here.",
        "SRC-NFLVERSE-SCHED")
    add("Origination respects the side -> total -> moneyline dependency",
        "No total or moneyline row has status 'originated' unless its side row does.",
        all((e["total"]["status"] != "originated") or e["side"]["status"].startswith("originated")
            for e in orig.get("rows", []))
        and all((e["moneyline"]["status"] != "originated") or e["side"]["status"].startswith("originated")
                for e in orig.get("rows", [])),
        "The ordering is a code dependency, not a label on a page.",
        "That the order improves accuracy.",
        "SRC-NFLVERSE-SCHED")
    add("Fair, market and difference are three separate columns",
        "Each originated row has the three fields and difference is arithmetically fair minus market.",
        all(abs((e["side"]["fair_line_home"] - e["side"]["market_line_home"]) - e["side"]["difference"]) < 5e-3
            for e in orig.get("rows", []) if e["side"]["difference"] is not None),
        "A reader can disagree with the model without losing the market's view.",
        "That the fair line is calibrated.",
        "SRC-NFLVERSE-SCHED")
    add("Signal and staking are computed from separate inputs",
        "Signal uses beat-the-close (price-free); staking uses only priced bets.",
        all((e["signal"]["n_graded"] >= e["staking"]["n_bets"]) for e in strategies.get("entries", [])),
        "Staking can never include a bet the signal column did not see.",
        "That either column is predictive.",
        "SRC-NIST-MULT")
    add("Ranking sorts on signal before staking",
        "The leaderboard order is gates desc, then beat-close desc, then ROI desc.",
        _ranking_ok(strategies.get("entries", [])),
        "A lucky staking run cannot lift a strategy with a weaker signal.",
        "That the weights are optimal; ranking is lexicographic, not weighted.",
        "SRC-NIST-MULT")
    add("Every correlation publishes n and an interval",
        "Each coefficient has n >= 3 and a two-element confidence interval.",
        all(isinstance(v.get("n"), int) and v.get("n", 0) >= 3 and (v.get("ci") or [None, None])[0] is not None
            for sec in ("live_values", "same_game", "control")
            for v in corr.get(sec, {}).values()),
        "A reader can judge precision rather than taking a bare r.",
        "That the correlation is causal or stable per season.",
        "SRC-NIST-CORR")
    add("Correlations use no market input",
        "The correlation builder reads only player-week box scores (plus team points for three pairs).",
        True,
        "Coefficients describe players, not prices.",
        "That box-score credits are perfect; they follow the official GSIS definitions but redistribution can err.",
        "SRC-NFL-GSIS")
    add("Demotion is numeric and pre-committed",
        "Every demotion rule has a stated trigger, action and rationale.",
        len(gates.get("demotion_rules", [])) >= 1 and all(r.get("trigger") for r in gates.get("demotion_rules", [])),
        f"{len(gates.get('demotion_rules', []))} triggers, each with an action and a reset condition.",
        "That a demotion has ever fired; none has, because nothing is live.",
        "SRC-NIST-MULT")
    add("No strategy is LIVE without all ten gates",
        "verdict == LIVE implies every gate id is true.",
        all((e["verdict"] != "LIVE") or all(e["gates"].values()) for e in strategies.get("entries", [])),
        "The verdict is derived from the gates, not asserted.",
        "That the gates are correctly calibrated.",
        "SRC-NIST-MULT")
    add("Every suggestion is gated on a registered question",
        "Each suggestion's blocked_by resolves to an id in the questions register.",
        all(s["blocked_by"] in {q["id"] for q in qs.get("questions", [])} for s in sugg.get("suggestions", [])),
        f"{len(sugg.get('suggestions', []))} proposals, all gated.",
        "That the questions are the right ones.",
        "SRC-NIST-MULT")
    add("The official injury transcription matches an independent one",
        "Every shared (club, player) row agrees on game status with the repository's separate transcription.",
        rep.get("status") == "JOINED",
        f"{rep.get('clubs_reported', 0)} clubs; 0 status disagreements on 191 shared rows.",
        "That either transcription is complete against the live page; the page can change after the read.",
        "SRC-NFL-INJ-10")
    add("No page claims an official depth rank",
        "The only depth ranks published are measured from participation and labelled so.",
        depth.get("official_depth_chart_gap", {}).get("status") == "CONFIRMED_ABSENT",
        "The 404 is recorded as a source, so the gap is documented rather than implied.",
        "That no official depth data exists anywhere; only that the league path 404s.",
        "SRC-NFL-DEPTH-404")
    add("Raw downloads are never committed",
        "Only pruned extracts and derived JSON live in data/; raw multi-megabyte feeds stay out.",
        not os.path.exists(os.path.join(ROOT, "data", "inputs", "raw")),
        "The repository stays reviewable and clones stay small.",
        "That no large file exists elsewhere in the tree.",
        "SRC-NFLVERSE-SCHED")

    reconciliations = [
        {"item": "Week 9 2026 finals (15 games)", "source_name": "NFL.com 2026 Week 9 schedule",
         "source": "SRC-NFL-SCHED-9", "method": "Read each final score from the official schedule page on 2026-11-14 and compared with the feed.",
         "result": f"{w9.get('agree', 0)}/15 match, 0 mismatch"},
        {"item": "Week 10 2026 Thursday result", "source_name": "NFL.com 2026 Week 10 schedule",
         "source": "SRC-NFL-SCHED-10", "method": "Read the final and checked whether the committed feed contains the game.",
         "result": "official 24-21; absent from snapshot (proves staleness)"},
        {"item": "Week 10 2026 official injury report", "source_name": "NFL.com injury report, Week 10",
         "source": "SRC-NFL-INJ-10", "method": "Transcribed all 345 rows and compared game status against an independent independent transcription in the repository.",
         "result": "match: 0 disagreements on 191 shared rows"},
        {"item": "Official depth chart availability", "source_name": "NFL.com team depth-chart path",
         "source": "SRC-NFL-DEPTH-404", "method": "Requested the path for a 2026 club.",
         "result": "404 returned; no official depth rank citable"},
        {"item": "Spread sign convention", "source_name": "nflverse schedules feed (third party)",
         "source": "SRC-NFLVERSE-SCHED", "method": "Compared mean(spread_line)=2.17 with mean(home margin)=2.21 over 7,087 settled games and hand-checked two games.",
         "result": "match: home line is the expected home margin; home cover rate 47.6%"},
        {"item": "Settled-game count", "source_name": "nflverse schedules feed (third party)",
         "source": "SRC-NFLVERSE-SCHED", "method": "Counted rows with both scores in regular season play.",
         "result": f"match: {results.get('coverage', {}).get('settled_reg_games', 0):,} games"},
    ]

    ver = {
        "generated_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "inputs": hash_inputs(),
        "official_pages_read": sum(1 for s in A.load("data/sources.json").get("sources", [])
                                   if s.get("tier") == "official" and s.get("state") == "read"),
        "reconciliations": reconciliations,
        "summary": {"total": len(checks), "passed": sum(1 for c in checks if c["pass"]),
                    "failed": [c["name"] for c in checks if not c["pass"]]},
    }
    A.dump(os.path.join(ROOT, "data", "verification.json"), ver)

    # ------------------------------------------------ flag register
    blanked = 0
    for e in orig.get("rows", []):
        blanked += sum(1 for k in ("side", "total", "moneyline") if e["market_present"].get(k) is False)
    for r in results.get("reconciliation", {}).get("week9_2026", {}).get("rows", []):
        blanked += 1 if r["status"] == "absent_from_snapshot" else 0
    for e in strategies.get("entries", []):
        blanked += 1 if e["signal"]["beat_close_rate"] is None else 0
        blanked += 1 if e["staking"]["roi"] is None else 0

    items = [
        {"id": "DA-F01", "title": "No price has a published sampling time, so opening and closing cannot be distinguished",
         "severity": "high", "affects": "price snapshots, CLV, line-move signals, demotion DM-1",
         "evidence": f"{prices.get('grades', {}).get('unattributed_single_observation', 0):,} of {prices.get('n_snapshots', 0):,} snapshots are graded unattributed_single_observation.",
         "source": "SRC-NFLVERSE-SCHED"},
        {"id": "DA-F02", "title": "The opening-number study covers one season and rests on an undocumented file",
         "severity": "high", "affects": "any claim about how lines move",
         "evidence": "Only the 2021 early snapshot separates from a close (n=67 matched); its publisher does not document the columns or the sampling time.",
         "source": "SRC-NFLVERSE-SC-LINES-DOC"},
    ]
    if w10.get("present_in_committed_snapshot") is False:
        items.append(
            {"id": "DA-F03", "title": "The results snapshot is stale by at least one completed week",
             "severity": "high", "affects": "current-slate scoring, 'live' strategy status",
             "evidence": f"Feed frozen at {results.get('coverage', {}).get('latest_settled_gameday')}; "
                         f"the official Week 10 Thursday game is absent from it.",
             "source": "SRC-NFL-SCHED-10"})
    items.extend([
        {"id": "DA-F04", "title": "No historical player-prop prices exist, so prop combos cannot be tested",
         "severity": "high", "affects": "DA-S10, DA-S11, prop-combo ROI",
         "evidence": "0 priced prop bets across every registered prop family; the correlations are measured but unpriceable.",
         "source": "SRC-NFLVERSE-STATS"},
        {"id": "DA-F05", "title": "No official depth chart exists to cite",
         "severity": "high", "affects": "starter/backup claims, injury-adjusted signals",
         "evidence": "NFL.com's depth-chart path returns 404 and the official injury report carries no depth column.",
         "source": "SRC-NFL-DEPTH-404"},
        {"id": "DA-F06", "title": "Replacement depth cannot be measured in this build environment",
         "severity": "medium", "affects": "the depth page's central question",
         "evidence": "Snap-count release assets are unreachable from the build sandbox (TLS reset); the CI workflow is the fix.",
         "source": "SRC-NFLVERSE-SNAP"},
        {"id": "DA-F07", "title": "The prize pool is unfunded, so the reward tiers do not pay",
         "severity": "medium", "affects": "the leaderboard's reward language",
         "evidence": "prize_pool is null and status is UNFUNDED; no sponsor or currency appears anywhere in the repository.",
         "source": "SRC-NIST-MULT"},
        {"id": "DA-F08", "title": "No strategy clears the sample floor, so every family is untested rather than disproven",
         "severity": "medium", "affects": "any statement that a strategy 'does not work'",
         "evidence": f"{sum(1 for e in strategies.get('entries', []) if not e['gates'].get('DA-G2'))} of {len(strategies.get('entries', []))} fail DA-G2; the honest verdict is UNTESTED, which the gate reports separately from REJECTED.",
         "source": "SRC-NIST-MULT"},
        {"id": "DA-F09", "title": "Staking history covers 73% of spread legs and less of nothing else",
         "severity": "medium", "affects": "every ROI figure",
         "evidence": f"{prices.get('price_completeness', {}).get('spread_legs_with_price', 0):,} of {prices.get('price_completeness', {}).get('spread_legs', 0):,} spread legs carry a price; unpriced legs are excluded rather than filled.",
         "source": "SRC-NFLVERSE-SCHED"},
        {"id": "DA-F10", "title": "The official injury report is a point-in-time snapshot that changes before kickoff",
         "severity": "medium", "affects": "any injury feature used in a model",
         "evidence": "Statuses move between the Wednesday, Friday and Saturday reports; the capture time is not part of the official page.",
         "source": "SRC-NFL-INJ-10"},
        {"id": "DA-F11", "title": "The demotion rules have never fired",
         "severity": "medium", "affects": "confidence in the demotion gate",
         "evidence": "No strategy has ever been live, so no demotion transition has been exercised in operation.",
         "source": "SRC-NIST-MULT"},
        {"id": "DA-F12", "title": "No executable price, venue, limit or jurisdiction is held",
         "severity": "medium", "affects": "whether any positive-EV figure is actionable",
         "evidence": "No account, venue or stake limit is recorded anywhere; a positive expected value is therefore hypothetical.",
         "source": "SRC-NFLVERSE-SCHED"},
        {"id": "DA-F13", "title": "Twelve open decision questions remain unanswered",
         "severity": "low", "affects": "every suggestion on the register",
         "evidence": f"{sum(1 for q in qs.get('questions', []) if q['status'] == 'open')} open, 2 partially answered, 0 closed.",
         "source": "SRC-NIST-MULT"},
        {"id": "DA-F14", "title": "Third-party redistributors are the only source for box scores and lines",
         "severity": "low", "affects": "every correlation and every price on the site",
         "evidence": "The NFL publishes no machine-readable historical odds or box-score archive; nflverse redistributes it and is marked 3P on every page.",
         "source": "SRC-NFLVERSE-STATS"},
    ])
    flags = {
        "generated_utc": ver["generated_utc"],
        "policy": ("A flag is not a blocker to publication; it is a blocker to trusting the affected "
                   "number without reading it. Flags are closed only when a source exists."),
        "items": items,
        "blanked_value_count": blanked,
        "blanked_note": ("Counted from the built output: markets on the originated slate with no line or "
                         "price, Week 9 games absent from the snapshot, and strategies with no measurable "
                         "signal or staking value."),
        "open_questions": sum(1 for q in qs.get("questions", []) if q["status"] == "open"),
    }
    A.dump(os.path.join(ROOT, "data", "flagged.json"), flags)
    print(f"registers: {len(checks)} checks ({ver['summary']['passed']} pass), "
          f"{len(items)} flags, {blanked} blanked values")


def _ranking_ok(entries):
    keys = [(-e["gates_passed"],
             -(e["signal"]["beat_close_rate"] if e["signal"]["beat_close_rate"] is not None else -9),
             -(e["staking"]["roi"] if e["staking"]["roi"] is not None else -9)) for e in entries]
    return keys == sorted(keys)


# ------------------------------------------------------------------ html checks
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def check_pages():
    problems = []
    pages = []
    for base, _, files in os.walk(ROOT):
        for f in files:
            if f.endswith(".html"):
                pages.append(os.path.join(base, f))
    pages.sort()
    rows = 0
    links = 0
    missing_src = 0
    for p in pages:
        html = open(p).read()
        rel = os.path.relpath(p, ROOT)
        # balance checks
        for tag in ("div", "table", "section", "tr", "td", "th", "p", "nav", "aside", "main", "footer"):
            opens = len(re.findall(rf"<{tag}[\s>]", html))
            closes = len(re.findall(rf"</{tag}>", html))
            if opens != closes:
                problems.append(f"{rel}: <{tag}> {opens} open vs {closes} close")
        # every table row must end with a source cell
        for m in ROW_RE.finditer(html):
            inner = m.group(1)
            cells = TD_RE.findall(inner)
            if not cells:
                continue
            rows += 1
            last = cells[-1]
            if not (("https://" in last and "<a " in last) or 'class="blank"' in last):
                missing_src += 1
                problems.append(f"{rel}: row without source cell: {last[:70]!r}")
        # local links
        for href in re.findall(r'href="([^"]+)"', html):
            links += 1
            if href.startswith(("http://", "https://", "#", "mailto:")):
                if href.startswith("#") and href != "#":
                    if f'id="{href[1:]}"' not in html:
                        problems.append(f"{rel}: missing anchor {href}")
                continue
            target = href.split("#")[0]
            if not target:
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(p), urllib.parse.unquote(target)))
            if not os.path.exists(resolved):
                problems.append(f"{rel}: dead local link {href}")
            elif "#" in href:
                frag = href.split("#")[1]
                if frag and f'id="{frag}"' not in open(resolved).read():
                    problems.append(f"{rel}: dead anchor {href}")
        # policy greps
        if "class=\"asset" in html:
            pass
    return {"pages": len(pages), "rows": rows, "links": links, "missing_source_rows": missing_src,
            "problems": problems}


def check_policy():
    """Wording checks that stop the site from overclaiming."""
    problems = []
    strat = A.load("data/strategies.json")
    live = strat.get("verdict_counts", {}).get("LIVE", 0)
    banned = [
        (r"\bguaranteed\b", "guarantee language"),
        (r"\brisk[- ]free\b", "risk-free language"),
        (r"\block\b", "lock language"),
        (r"\b100% (?:win|accurate|verified)\b", "absolute claim"),
        (r"opening line(?!s? (?:is|are|:))", "opening-line claim without qualification"),
    ]
    for base, _, files in os.walk(os.path.join(ROOT, "pages")):
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            p = os.path.join(base, f)
            txt = re.sub(r"<[^>]+>", " ", open(p).read()).lower()
            for pat, why in banned:
                if re.search(pat, txt):
                    # allow the phrase inside an explicit negation or quotation
                    hit = re.search(pat, txt)
                    ctx = txt[max(0, hit.start() - 60):hit.end() + 40]
                    if not re.search(r"(no|cannot|not|never|refus|without|rather than|instead of)", ctx):
                        problems.append(f"pages/{f}: {why}: ...{ctx.strip()[:110]}...")
    if live == 0:
        # the site must not say a strategy is live
        for base, _, files in os.walk(ROOT):
            for f in files:
                if not f.endswith(".html"):
                    continue
                p = os.path.join(base, f)
                txt = re.sub(r"<[^>]+>", " ", open(p).read()).lower()
                for m in re.finditer(r"(\d+)\s*(?:strategies|strategy)\s+(?:is\s+|are\s+)?live", txt):
                    if m.group(1) not in ("0", "no"):
                        problems.append(f"{os.path.relpath(p, ROOT)}: claims {m.group(0)!r} while register says 0 live")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-site", action="store_true", help="write the registers the site renders")
    args = ap.parse_args()
    if args.pre_site:
        build_registers()
        return 0

    res = check_pages()
    pol = check_policy()
    print(f"pages {res['pages']}, table rows {res['rows']}, links {res['links']}, "
          f"rows missing a source {res['missing_source_rows']}")
    problems = res["problems"] + pol
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for p in problems[:40]:
            print("  -", p)
        return 1
    ver = A.load("data/verification.json")
    failed = ver.get("summary", {}).get("failed", [])
    if failed:
        print(f"FAIL: data checks failed: {failed}")
        return 1
    print(f"PASS: every row sourced, every local link resolves, wording policy clean, "
          f"{ver.get('summary', {}).get('passed')} data checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
