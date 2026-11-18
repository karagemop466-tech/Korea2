#!/usr/bin/env python3
"""Guards for the decision-readiness register, the official capture and the pages that render them.

Added by the integration session `arena/4c90e65f-korea2` (2026-11-18). Runs in CI (validate.yml) and
locally. It re-derives rather than re-reads: the correlation coefficients are recomputed here with
their own implementations, the capture is rebuilt from its generator and compared byte for byte, and
the rendered pages are rebuilt and compared. Nothing in this file asserts that an external page is
correct - the official reads behind the capture are recorded with their URLs and timestamps in
data/sources.json and data/derived/official_capture_2026-11-18.json.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE = os.path.join(ROOT, "data", "derived", "official_capture_2026-11-18.json")
CORRS = os.path.join(ROOT, "data", "derived", "official_correlations_2026-11-18.json")
READY = os.path.join(ROOT, "data", "derived", "readiness.json")
ALLOWED_STATUS = {"BUILT", "PARTIAL", "BLOCKED-SOURCE", "BLOCKED-DECISION", "NOT-STARTED",
                  "REJECTED", "ONGOING"}
OFFICIAL_HOSTS = re.compile(
    r"^https://([a-z0-9.-]+\.)?(nfl\.com|media\.nfl\.com|operations\.nfl\.com|static\.www\.nfl\.com"
    r"|itl\.nist\.gov|nist\.gov|weather\.gov|noaa\.gov|github\.com|colts\.com|archive\.org"
    r"|princeton\.edu|pinnacle\.com|kaggle\.com|massgaming\.com|gaming\.nv\.gov|aglc\.ca)\b")


def load(path: str):
    with open(path) as fh:
        return json.load(fh)


def check(cond: bool, msg: str, fails: list[str], detail: str = "") -> None:
    if not cond:
        fails.append(f"{msg}{(' -> ' + detail) if detail else ''}")


def test_capture(fails: list[str]) -> dict:
    cap = load(CAPTURE)
    checks = cap.get("checks", [])
    check(len(checks) >= 10, "the capture publishes its consistency checks", fails, str(len(checks)))
    bad = [c["id"] for c in checks if c["result"] != "PASS"]
    check(not bad, "every consistency check passes", fails, ",".join(bad))

    st = cap["standings"]
    check(len(st) == 32, "standings covers 32 clubs", fails, str(len(st)))
    check(len({r["abbr"] for r in st}) == 32, "one row per club", fails)
    for r in st:
        check(bool(r.get("source_url", "").startswith("https://")), f"row {r['abbr']} is sourced", fails)
        check(bool(r.get("read_at_utc")), f"row {r['abbr']} carries a clock time", fails)
        if r.get("points_for") is None:
            check(r.get("points_against") is None and r.get("point_differential") is None,
                  f"unverified {r['abbr']} row stays fully blank", fails)
    wins = sum(r["wins"] for r in st)
    losses = sum(r["losses"] for r in st)
    check(wins == losses, "league-wide win/loss parity", fails, f"{wins} vs {losses}")
    check(sum(r["ties"] for r in st) % 2 == 0, "tie parity", fails)

    games = cap["week10_results"]
    check(len(games) == 14, "Week 10 slate has 14 finals", fails, str(len(games)))
    for g in games:
        check(g["away_points"] != g["home_points"], f"{g['away']}@{g['home']} has a winner", fails)
        check(g["margin_home"] == g["home_points"] - g["away_points"], "margin matches the scores", fails)
        expected = g["home"] if g["home_points"] > g["away_points"] else g["away"]
        check(g["winner"] == expected, "winner derived from the scores", fails)
        check(bool(g["game_centre_url"]), "fixture links its game centre", fails)
    clubs = [c for g in games for c in (g["away"], g["home"])]
    check(len(clubs) == len(set(clubs)) == 28, "each club appears exactly once on the slate", fails, str(len(clubs)))
    byes = cap["week10_byes"]
    check(len(byes) == 4 and not set(byes) & set(clubs), "bye clubs are disjoint from the slate", fails)

    inj = cap["injury_report"]["rows"]
    check(len(inj) >= 10, "availability rows transcribed", fails, str(len(inj)))
    for r in inj:
        check(r.get("depth_rank") is None and r.get("snap_count") is None and r.get("replacement") is None,
              f"no depth inference on {r['player']}", fails)
        check(bool(r.get("read_at_utc")) and bool(r.get("source_url")), f"{r['player']} row is dated and sourced", fails)
    lions = {r["player"]: r["game_status"] for r in inj if r["team"] == "Detroit Lions"
             and r["player"] in ("Kerby Joseph", "Cade Mays", "D.J. Reed")}
    check(len(lions) == 3 and all(v == "Out" for v in lions.values()),
          "the three Lions rows the brief lists as blank now carry a status", fails, json.dumps(lions))
    return cap


def test_correlations(fails: list[str], cap: dict) -> None:
    doc = load(CORRS)
    rows = doc["rows"]
    check(len(rows) == 5, "five official-only coefficients published", fails, str(len(rows)))
    st = [r for r in cap["standings"] if r["points_for"] is not None]
    n = len(st)
    for r in rows:
        check(r["n"] == n, f"{r['id']} reports its n as the readable rows", fails, f"{r['n']} vs {n}")
        check(OFFICIAL_HOSTS.match(r["source_url"]), f"{r['id']} cites an official domain", fails, r["source_url"])
        check(-1.0 <= r["ci95_low"] <= r["r"] <= r["ci95_high"] <= 1.0,
              f"{r['id']} interval brackets its estimate", fails, json.dumps([r["ci95_low"], r["r"], r["ci95_high"]]))
    # independent recomputation of CR-01 (point differential vs wins), different code path on purpose
    net = [r["points_for"] - r["points_against"] for r in st]
    wins = [float(r["wins"]) for r in st]
    mx, my = sum(net) / n, sum(wins) / n
    sxx = sum((x - mx) ** 2 for x in net)
    syy = sum((y - my) ** 2 for y in wins)
    sxy = sum((x - mx) * (y - my) for x, y in zip(net, wins))
    r01 = sxy / math.sqrt(sxx * syy)
    published = [x for x in rows if x["id"] == "CR-01"][0]["r"]
    check(abs(round(r01, 4) - published) < 1e-9, "CR-01 recomputes independently", fails, f"{r01} vs {published}")
    z = math.atanh(r01)
    lo, hi = math.tanh(z - 1.959963985 / math.sqrt(n - 3)), math.tanh(z + 1.959963985 / math.sqrt(n - 3))
    published_row = [x for x in rows if x["id"] == "CR-01"][0]
    check(abs(round(lo, 4) - published_row["ci95_low"]) < 1e-9
          and abs(round(hi, 4) - published_row["ci95_high"]) < 1e-9,
          "CR-01 Fisher interval recomputes independently", fails,
          f"{lo},{hi} vs {published_row['ci95_low']},{published_row['ci95_high']}")


def test_readiness(fails: list[str]) -> dict:
    doc = load(READY)
    rows = doc["rows"]
    meta = doc["meta"]
    check(meta["row_count"] == len(rows), "register row count matches its rows", fails)
    check(len(rows) >= 60, "register covers the brief (>= 60 requirements)", fails, str(len(rows)))
    ids = [r["id"] for r in rows]
    check(len(ids) == len(set(ids)), "requirement ids are unique", fails)
    for r in rows:
        check(r["status"] in ALLOWED_STATUS, f"{r['id']} uses a defined status", fails, r["status"])
        check(bool(r.get("requirement", "").strip()), f"{r['id']} states the requirement", fails)
        check(bool(r.get("blocking_gate", "").strip()), f"{r['id']} names a gate or a reason", fails)
        if r["status"] != "BUILT":
            check(bool(r.get("clears_when", "").strip()), f"{r['id']} states the number that clears it", fails)
            check(bool(r.get("next_action", "").strip()), f"{r['id']} states a discovery/next action", fails)
        ev = r.get("evidence", [])
        check(len(ev) >= 1, f"{r['id']} links evidence", fails)
        for e in ev:
            url = e.get("url", "")
            if url.startswith("http"):
                check(OFFICIAL_HOSTS.match(url), f"{r['id']} evidence host is official", fails, url)
            else:
                for base in (ROOT, os.path.join(ROOT, "pages")):
                    if os.path.exists(os.path.normpath(os.path.join(base, url.split("#")[0]))):
                        break
                else:
                    check(False, f"{r['id']} evidence link resolves", fails, url)
    totals = meta["status_totals"]
    check(sum(totals.values()) == len(rows), "status totals reconcile", fails)
    blocked = sum(v for k, v in totals.items() if k.startswith("BLOCKED")) + totals.get("NOT-STARTED", 0)
    check(blocked > 0, "the register reports its blockers rather than hiding them", fails)
    return doc


def test_rendering(fails: list[str], ready: dict) -> None:
    idx = open(os.path.join(ROOT, "index.html")).read()
    check("Decision readiness: one row per requirement" in idx,
          "the landing page carries the decision-readiness table", fails)
    for row in ready["rows"]:
        check(row["id"] in idx, f"{row['id']} appears on the landing page", fails)
    reg = open(os.path.join(ROOT, "pages", "readiness.html")).read()
    check("One row per requirement" in reg, "the full register page renders", fails)
    live = open(os.path.join(ROOT, "pages", "live-checks.html")).read()
    check("FC Bayern Munich Stadium" in live, "the venue read is published", fails)
    check("2026 NFL Schedule Announced (May 14, 2026)" in live, "the dated schedule announcement sits beside the slate", fails)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from lib import site as L
    items = [item for _, group in L.nav_groups() for item in group]
    hrefs = [h for h, _ in items]
    labels = [t for _, t in items]
    dup_href = sorted({h for h in hrefs if hrefs.count(h) > 1})
    dup_label = sorted({t for t in labels if labels.count(t) > 1})
    check(not dup_href, "no navigation target is linked twice", fails, ",".join(dup_href[:3]))
    check(not dup_label, "no navigation label is duplicated", fails, ",".join(dup_label[:3]))
    for hub in ("line-desk", "price-desk", "price-store", "review-board", "verify-hub", "injury-report-w10"):
        check(f"{hub}/index.html" in hrefs, f"{hub} is linked from the shared navigation", fails)
    for name in sorted(n for n in os.listdir(ROOT)
                       if os.path.isdir(os.path.join(ROOT, n)) and not n.startswith((".", "_"))
                       and os.path.exists(os.path.join(ROOT, n, "index.html"))):
        check(f"{name}/index.html" in hrefs, f"{name}/ has a navigation entry", fails)


def test_determinism(fails: list[str]) -> None:
    """Both generators must be reproducible; the site must match its committed output."""
    for cmd in (["scripts/official_snapshot.py"], ["scripts/build_readiness.py"]):
        out = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True,
                             env={**os.environ, "PYTHONPATH": "scripts"})
        check(out.returncode == 0, f"{cmd[0]} runs clean", fails, out.stderr.strip()[:200])
    before = {p: open(os.path.join(ROOT, p)).read()
              for p in ("data/derived/official_capture_2026-11-18.json",
                        "data/derived/official_correlations_2026-11-18.json",
                        "data/derived/readiness.json", "index.html",
                        "pages/readiness.html", "pages/live-checks.html")}
    with open(os.devnull, "w") as devnull:
        subprocess.run([sys.executable, "scripts/official_snapshot.py", "--write"], cwd=ROOT,
                       stdout=devnull, stderr=devnull, check=True, env={**os.environ, "PYTHONPATH": "scripts"})
        subprocess.run([sys.executable, "scripts/build_readiness.py", "--write"], cwd=ROOT,
                       stdout=devnull, stderr=devnull, check=True, env={**os.environ, "PYTHONPATH": "scripts"})
        subprocess.run([sys.executable, "scripts/build_site.py"], cwd=ROOT, stdout=devnull,
                       stderr=devnull, check=True, env={**os.environ, "PYTHONPATH": "scripts"})
    after = {p: open(os.path.join(ROOT, p)).read() for p in before}
    drifted = [p for p in before if before[p] != after[p]]
    check(not drifted, "committed data and pages are byte-reproducible", fails, ", ".join(drifted))


def main() -> int:
    fails: list[str] = []
    cap = test_capture(fails)
    test_correlations(fails, cap)
    ready = test_readiness(fails)
    test_rendering(fails, ready)
    test_determinism(fails)
    if fails:
        print(f"FAIL: {len(fails)} problem(s)")
        for f in fails[:30]:
            print(" -", f)
        return 1
    print(f"PASS: capture ({len(cap['checks'])} checks, {len(cap['week10_results'])} finals, "
          f"{len(cap['standings'])} standings rows), register ({len(ready['rows'])} requirements, "
          f"{ready['meta']['status_totals'].get('BUILT')} built), pages and navigation consistent, "
          f"outputs byte-reproducible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
