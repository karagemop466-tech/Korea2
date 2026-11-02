#!/usr/bin/env python3
"""Invariants for the integrated site's own derived data (data/derived/*.json).

Added by the integration/verification session `arena/652b0095-korea2` on 2026-11-02, after the
published site was found to contain a `-Infinity` token in a derived JSON file (rendered as "-inf"
in a table) and a table cell that read a key name the data did not have.

Checks
  1. every data/derived/*.json file parses as strict JSON - NaN, Infinity and -Infinity are rejected,
     because a browser's JSON.parse rejects them and no published number should be non-finite;
  2. data/derived/verification.json exists and reports zero material disagreements;
  3. every 2020 team in that file reconciles with NFL.com (the completed-season control);
  4. the published Verification page exists, is linked from every generated page's navigation, and
     carries the build's generator marker;
  5. finite-value rule for the fields the site prints as statistics.
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def strict_load(path: str) -> dict:
    def reject(token: str):
        raise ValueError(f"{os.path.basename(path)} contains the non-JSON token {token}")

    with open(path) as fh:
        return json.loads(fh.read(), parse_constant=reject)


def main() -> int:
    errors: list[str] = []

    # 1. strict JSON for everything the site renders
    derived = sorted(glob.glob(os.path.join(ROOT, "data", "derived", "*.json")))
    if not derived:
        errors.append("no data/derived/*.json files found")
    for path in derived:
        try:
            strict_load(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    # 2/3. the independent verification record
    vpath = os.path.join(ROOT, "data", "derived", "verification.json")
    if not os.path.exists(vpath):
        errors.append("missing data/derived/verification.json (run verification/recompute.py)")
    else:
        ver = strict_load(vpath)
        summary = ver.get("summary", {})
        if not summary.get("n_checks"):
            errors.append("verification.json has no checks")
        if summary.get("n_fail", 0):
            errors.append(f"verification.json reports {summary['n_fail']} material disagreement(s)")
        rows = ver.get("standings_2020", [])
        if len(rows) != 32:
            errors.append(f"standings_2020 has {len(rows)} teams, expected 32")
        bad = [r["team"] for r in rows if not r.get("match")]
        if bad:
            errors.append(f"2020 standings do not reconcile for: {', '.join(bad)}")
        if not summary.get("data_as_of_gameday"):
            errors.append("verification.json does not state the date the data ends")

    # 4. the verification page is published and reachable from the navigation
    page = os.path.join(ROOT, "pages", "verification.html")
    if not os.path.exists(page):
        errors.append("missing pages/verification.html")
    else:
        with open(page) as fh:
            html = fh.read()
        if 'content="line-lab/scripts/build_site.py"' not in html:
            errors.append("pages/verification.html was not written by the integrated generator")
        if "pages/verification.html" not in html:
            errors.append("pages/verification.html is not linked from its own navigation")
        for name in sorted(glob.glob(os.path.join(ROOT, "pages", "*.html"))):
            with open(name) as fh:
                body = fh.read()
            if 'content="line-lab/scripts/build_site.py"' in body and "verification.html" not in body:
                errors.append(f"{os.path.relpath(name, ROOT)}: navigation does not link the verification page")

    # 5. an orphan check: every generated page must be linked from at least one other generated page
    generated = [p for p in glob.glob(os.path.join(ROOT, "pages", "*.html")) + [os.path.join(ROOT, "index.html")]
                 if 'content="line-lab/scripts/build_site.py"' in open(p).read()]
    corpus = {p: open(p).read() for p in generated}
    for p in generated:
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        name = os.path.basename(p)
        linked = any(("href=\"" + name + "\"") in body or (rel in body)
                     for other, body in corpus.items() if other != p)
        if rel == "index.html":
            linked = any("index.html" in body for other, body in corpus.items() if other != p)
        if not linked:
            errors.append(f"{rel}: orphan page - no other generated page links to it")

    if errors:
        print("FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"PASS: {len(derived)} derived JSON files are strict JSON; verification record has "
          f"{len(ver.get('checks', []))} checks, 0 disagreements, 32/32 teams reconciled for 2020; "
          f"{len(generated)} generated pages are all linked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
