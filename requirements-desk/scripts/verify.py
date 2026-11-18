#!/usr/bin/env python3
"""Strict checks for the Requirements Desk.

Fails loudly (exit 1) on any of:
  1. a page missing a <title>;
  2. a broken internal link, asset or in-page anchor;
  3. a table row without a source link;
  4. an external link that is not https;
  5. a register whose row count disagrees with the committed CSV;
  6. a capture manifest missing any register hash;
  7. a requirement row missing a status, gate or clearance condition.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requirements as rq  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # requirements-desk/
SITE = os.path.dirname(ROOT)          # repository root == GitHub Pages root

EXPECTED_ROWS = {
    "injury_report_2026_w10": 347,
    "results_2026_w10": 14,
    "schedule_2026_w11": 13,
    "standings_2026": 32,
    "absent_clubs_2026_w10": 4,
    "injury_page_news_2026": 20,
}

HUB = "requirements-desk/"

REQUIRED_PAGES = [
    HUB + "index.html", HUB + "pages/executive.html", HUB + "pages/requirements.html",
    HUB + "pages/suggestions.html", HUB + "pages/questions.html", HUB + "pages/injuries.html",
    HUB + "pages/results.html", HUB + "pages/schedule.html", HUB + "pages/standings.html",
    HUB + "pages/luck.html", HUB + "pages/correlations.html", HUB + "pages/verification.html",
    HUB + "pages/flagged.html", HUB + "pages/sources.html",
]


class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self.tables = 0
        self.bad_rows: list[int] = []
        self._in_title = False
        self._in_tbody = False
        self._cell_has_link = False
        self._row_index = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "title":
            self._in_title = True
        if tag == "table":
            self.tables += 1
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self._row_index += 1
            self._cell_has_link = False
        if tag == "a" and self._in_tbody:
            self._cell_has_link = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "tbody":
            self._in_tbody = False
        if tag == "tr" and self._in_tbody:
            if not self._cell_has_link:
                self.bad_rows.append(self._row_index)

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def main() -> int:
    errors: list[str] = []
    docs: dict[str, Doc] = {}

    files = []
    for base, _, names in os.walk(ROOT):
        if ".git" in base:
            continue
        for n in names:
            if n.endswith(".html"):
                files.append(os.path.relpath(os.path.join(base, n), SITE))
    files.sort()

    for f in files:
        with open(os.path.join(SITE, f), encoding="utf-8") as fh:
            d = Doc()
            d.feed(fh.read())
        docs[f] = d
        if not d.title.strip():
            errors.append(f"{f}: missing <title>")

    for f, d in docs.items():
        for href in d.links:
            if href.startswith(("http://", "https://", "mailto:")):
                if href.startswith("http://"):
                    errors.append(f"{f}: insecure external link {href}")
                continue
            if href.startswith("#"):
                if href[1:] and href[1:] not in d.ids:
                    errors.append(f"{f}: broken anchor {href}")
                continue
            target, _, anchor = href.partition("#")
            # Links inside this hub are resolved against the *site* root, because
            # sibling hubs (line-desk/, price-desk/...) live one level above.
            path = os.path.normpath(os.path.join(SITE, os.path.dirname(f), target))
            if not os.path.exists(path):
                errors.append(f"{f}: broken internal link {href} -> {path}")
            elif anchor:
                rel = os.path.relpath(path, SITE)
                if rel not in docs or anchor not in docs[rel].ids:
                    errors.append(f"{f}: broken anchor {href} on {rel}")
        if d.bad_rows:
            errors.append(f"{f}: {len(d.bad_rows)} table row(s) with no source link "
                          f"(rows {d.bad_rows[:5]})")

    for req in REQUIRED_PAGES:
        if req not in docs:
            errors.append(f"missing required page {req}")

    # register row counts and hashes
    data = os.path.join(ROOT, "data")
    manifest_path = os.path.join(data, "capture_manifest.json")
    if not os.path.exists(manifest_path):
        errors.append("missing capture_manifest.json")
    else:
        man = json.load(open(manifest_path))
        if not man.get("capture_utc"):
            errors.append("manifest: missing capture_utc")
        for key, exp in EXPECTED_ROWS.items():
            reg = man.get("registers", {}).get(key)
            if not reg:
                errors.append(f"manifest: missing register {key}")
                continue
            if not reg.get("sha256"):
                errors.append(f"manifest: register {key} has no sha256")
            if not reg.get("source_url", "").startswith("https://"):
                errors.append(f"manifest: register {key} has no https source_url")
            csv_path = os.path.join(data, os.path.basename(reg["file"]))
            if not os.path.exists(csv_path):
                errors.append(f"manifest: register {key} points at a missing file")
                continue
            with open(csv_path, newline="", encoding="utf-8") as fh:
                n = sum(1 for _ in csv.DictReader(fh))
            if n != exp:
                errors.append(f"register {key}: {n} rows, expected {exp}")
            if n != reg.get("rows"):
                errors.append(f"register {key}: manifest says {reg.get('rows')}, CSV has {n}")

    # requirement register integrity
    seen = set()
    for r in rq.REQUIREMENTS:
        if r["id"] in seen:
            errors.append(f"duplicate requirement id {r['id']}")
        seen.add(r["id"])
        if r["status"] not in ("verified", "partial", "blocked", "not started"):
            errors.append(f"{r['id']}: bad status {r['status']!r}")
        for field in ("gate", "clears", "ev", "ev_url"):
            if not str(r.get(field, "")).strip():
                errors.append(f"{r['id']}: empty {field}")
        if r["cat"] not in rq.CATEGORY_ORDER:
            errors.append(f"{r['id']}: category {r['cat']!r} not in CATEGORY_ORDER")

    print(f"checked {len(files)} pages, {sum(d.tables for d in docs.values())} tables, "
          f"{sum(len(d.links) for d in docs.values())} links, "
          f"{len(rq.REQUIREMENTS)} requirements, {len(EXPECTED_ROWS)} registers")
    if errors:
        print(f"\nFAILED with {len(errors)} issue(s):")
        for e in errors[:40]:
            print(" -", e)
        return 1
    print("all requirements-desk checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
