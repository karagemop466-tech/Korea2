#!/usr/bin/env python3
"""CV-4 verifier: strict checks on the coverage audit output and rendered pages.

Fails closed. Asserts that:
  * coverage/data/coverage.json exists and is well-formed;
  * there are no broken/insecure links anywhere in the audit;
  * the canonical root build and every active lab carry a source on every row;
  * the only unsourced rows are on legacy archive pages, and the legacy_review
    list matches the pages flagged;
  * the rendered coverage pages themselves put a source link on every table row.

Pure Python standard library.
"""
from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "coverage", "data", "coverage.json")


class RowCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = 0
        self.rows_without_source = 0
        self._in_tbody = False
        self._cell_has_link = False
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self.rows += 1
            self._cell_has_link = False
        if tag in ("td", "th") and self._in_tbody:
            self._in_cell = True
        if tag == "a" and self._in_cell:
            self._cell_has_link = True

    def handle_endtag(self, tag):
        if tag in ("tbody", "thead"):
            self._in_tbody = False
        if tag in ("td", "th"):
            self._in_cell = False
        if tag == "tr" and self._in_tbody:
            if not self._cell_has_link:
                self.rows_without_source += 1


def main() -> int:
    errors: list[str] = []
    if not os.path.exists(DATA):
        print("FAIL: coverage/data/coverage.json missing - run audit_coverage.py first")
        return 1
    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    m = data["meta"]

    if m["link_issues"] != 0:
        errors.append(f"{m['link_issues']} link issue(s) present; expected 0")
    for t in data["by_tier"]:
        if t["key"] in ("canonical", "active-lab") and t["rows_without_source"] != 0:
            errors.append(f"tier {t['key']} has {t['rows_without_source']} unsourced rows; expected 0")
    flagged = sum(1 for p in data["pages"] if not p["sourced"] and p["rows"] > 0)
    if flagged != len(data["legacy_review"]):
        errors.append(f"legacy_review lists {len(data['legacy_review'])} pages but "
                      f"{flagged} pages are flagged")
    for p in data["legacy_review"]:
        if not p["path"].startswith(("origination", "quant-lab", "nfl-lines",
                                     "nfl-research", "research-desk", "dashboard", "audit", "site")):
            errors.append(f"unexpected legacy review page: {p['path']}")

    # The rendered coverage pages must follow the same per-row source rule.
    for rel in ("index.html", "pages/coverage.html", "pages/legacy-review.html",
                "pages/links.html", "pages/method.html"):
        path = os.path.join(ROOT, "coverage", rel)
        if not os.path.exists(path):
            errors.append(f"missing rendered page coverage/{rel}")
            continue
        rc = RowCheck()
        with open(path, encoding="utf-8") as fh:
            rc.feed(fh.read())
        if rc.rows_without_source:
            errors.append(f"coverage/{rel}: {rc.rows_without_source} row(s) without a source link")

    if errors:
        print(f"FAIL with {len(errors)} issue(s):")
        for e in errors:
            print(" -", e)
        return 1
    print(f"coverage verifier PASS: {m['pages_total']} pages, {m['rows_total']} rows, "
          f"{m['rows_without_source']} unsourced (all legacy), {m['link_issues']} link issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
