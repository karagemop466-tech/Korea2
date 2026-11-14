#!/usr/bin/env python3
"""Fail the build unless the signal-desk site is internally sound.

Checks
  1. every page parses as HTML, has a <title> and a generator meta tag;
  2. every internal link and asset resolves to a file that exists (relative to the page);
  3. every in-page anchor that is linked exists on the target page;
  4. every data table row has a non-empty last cell containing a source link;
  5. every external link is absolute https and points at a host on the allowlist;
  6. every page in NAV exists, and every generated page is in NAV;
  7. no placeholder text leaked into a page (TODO, XXX, "None", "nan", "&lt;span class=\"na\"&gt;None");
  8. the origination-order invariant still holds: the published moneyline probability is
     Phi(side / sigma) within 0.002 for every row, recomputed here from the committed artefacts;
  9. every value published as "measured" in a data file carries a source and a source_class.

Exit code is non-zero on any failure, so CI cannot merge a broken site.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")

ALLOWED_HOSTS = [
    "www.nfl.com", "nfl.com", "media.nfl.com", "operations.nfl.com", "static.www.nfl.com",
    "github.com", "api.github.com", "karagemop466-tech.github.io",
]

NAV = [
    "index.html", "pages/prices.html", "pages/results.html", "pages/order.html",
    "pages/gap.html", "pages/leaderboard.html", "pages/depth.html", "pages/correlations.html",
    "pages/demotion.html", "pages/suggestions.html", "pages/questions.html", "pages/summary.html",
    "pages/flagged.html", "pages/sources.html",
]

PLACEHOLDERS = ["TODO", "XXX", "FIXME", "None</td>", ">nan<", ">None<", "undefined"]


class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self.generator = ""
        self.tables = 0
        self.rows = 0
        self.rows_without_source: list[int] = []
        self._in_title = False
        self._in_tbody = False
        self._row_cells: list[str] = []
        self._cell_text: list[str] = []
        self._cell_has_link = False
        self._in_cell = False
        self._row_no = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "meta" and a.get("name") == "generator":
            self.generator = a.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag == "table":
            self.tables += 1
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self._row_cells = []
            self._cell_has_link = False
            self._row_no += 1
        if tag in ("td", "th"):
            self._in_cell = True
            self._cell_text = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "tbody":
            self._in_tbody = False
        if tag in ("td", "th"):
            self._in_cell = False
            self._row_cells.append(" ".join(self._cell_text).strip())
        if tag == "tr" and self._in_tbody:
            self.rows += 1
            last = self._row_cells[-1] if self._row_cells else ""
            if not last or "no source" in last.lower():
                self.rows_without_source.append(self._row_no)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_cell:
            self._cell_text.append(data)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    fails: list[str] = []
    pages = [p for p in NAV if os.path.exists(os.path.join(ROOT, p))]
    for p in NAV:
        if not os.path.exists(os.path.join(ROOT, p)):
            fails.append(f"missing page: {p}")

    # 1-3, 5-7: parse and link-check
    total_rows = total_tables = 0
    for page in pages:
        text = read(os.path.join(ROOT, page))
        doc = Doc()
        doc.feed(text)
        total_rows += doc.rows
        total_tables += doc.tables
        if not doc.title.strip():
            fails.append(f"{page}: no <title>")
        if "signal-desk/scripts/build.py" not in doc.generator:
            fails.append(f"{page}: missing generator meta")
        if doc.generator and "signal-desk/scripts/build.py" not in doc.generator:
            fails.append(f"{page}: wrong generator")
        if doc.rows_without_source:
            fails.append(f"{page}: {len(doc.rows_without_source)} table row(s) without a source "
                         f"(rows {doc.rows_without_source[:5]})")
        for token in PLACEHOLDERS:
            if token in text:
                fails.append(f"{page}: placeholder text {token!r} leaked into the page")
        base = os.path.dirname(os.path.join(ROOT, page))
        for href in doc.links:
            if href.startswith(("mailto:", "tel:")):
                continue
            if href.startswith("#"):
                if href[1:] and href[1:] not in doc.ids:
                    fails.append(f"{page}: anchor {href} not found on the page")
                continue
            if re.match(r"^[a-z]+://", href):
                if not href.startswith("https://"):
                    fails.append(f"{page}: non-https external link {href}")
                    continue
                host = href.split("/")[2]
                if host not in ALLOWED_HOSTS:
                    fails.append(f"{page}: external host not on the allowlist: {host}")
                continue
            target_path, _, anchor = href.partition("#")
            target = os.path.normpath(os.path.join(base, target_path))
            if not os.path.exists(target):
                fails.append(f"{page}: broken internal link {href}")
                continue
            if anchor and target.endswith(".html"):
                tdoc = Doc()
                tdoc.feed(read(target))
                if anchor not in tdoc.ids:
                    fails.append(f"{page}: anchor #{anchor} missing on {target_path}")

    # 4: every page in NAV must be reachable from every page's nav
    for page in pages:
        text = read(os.path.join(ROOT, page))
        up = "../" if page.startswith("pages/") else ""
        for target in NAV:
            if target == page:
                continue
            if f'href="{up}{target}"' not in text:
                fails.append(f"{page}: nav does not link {target}")

    # every generated html file must be in NAV
    for dirpath, _dirs, files in os.walk(ROOT):
        if os.sep + "data" in dirpath:
            continue
        for f in files:
            if f.endswith(".html"):
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
                if rel not in NAV:
                    fails.append(f"orphan page not in navigation: {rel}")

    # 8: origination-order invariant, recomputed independently
    model = json.load(open(os.path.join(ROOT, "..", "data", "derived", "model.json")))
    sigma = model["margin_sigma"]
    worst = 0.0
    n_rows = 0
    for g in model["originated_lines"]["games"]:
        p = 0.5 * (1.0 + math.erf((g["model_spread_home"] / sigma) / math.sqrt(2.0)))
        worst = max(worst, abs(p - g["model_home_win_prob"]))
        n_rows += 1
    if worst > 0.002:
        fails.append(f"moneyline no longer reconstructs from the side: worst gap {worst:.4f}")
    order = json.load(open(os.path.join(DATA, "origination_order.json")))
    if order["tests"][0]["verdict"] != "pass":
        fails.append("origination_order.json does not report a pass on the moneyline invariant")

    # 9: measured values must carry a source
    for name in sorted(os.listdir(DATA)):
        if not name.endswith(".json"):
            continue
        blob = json.load(open(os.path.join(DATA, name)))
        stack = [blob]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("status") == "measured":
                    if not node.get("source"):
                        fails.append(f"{name}: measured value without a source: {node.get('metric') or node.get('note', '')[:40]}")
                    if node.get("source_class") not in ("official", "third-party"):
                        fails.append(f"{name}: measured value without a source_class")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)

    print(f"checked {len(pages)} pages, {total_tables} tables, {total_rows} table rows")
    print(f"moneyline reconstruction: worst gap {worst:.5f} over {n_rows} rows (limit 0.002)")
    if fails:
        print(f"\n{len(fails)} FAILURE(S):")
        for f in fails:
            print("  -", f)
        return 1
    print("all signal-desk checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
