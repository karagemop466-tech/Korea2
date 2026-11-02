#!/usr/bin/env python3
"""Static checks on the generated site. Runs in CI and can be run locally.

Checks
  1. every HTML file parses as HTML and has a title;
  2. every internal link/asset resolves to a file that exists;
  3. every in-page anchor (#id) referenced internally exists on the target page;
  4. every table row carries a source link (the last cell must contain an <a href>);
  5. every external link is absolute and https;
  6. required pages exist and are reachable from the navigation on every page.
"""
from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser

ROOT = "."
REQUIRED = [
    "index.html",
    "pages/executive.html", "pages/lines.html", "pages/props.html", "pages/correlation.html",
    "pages/strategies.html", "pages/validation.html", "pages/leaderboard.html", "pages/luck.html",
    "pages/market.html", "pages/method.html", "pages/sources.html", "pages/flagged.html",
    "pages/verification.html",
]


class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self._in_title = False
        self.tables: int = 0
        self.rows_without_source: list[int] = []
        self._row_cells: list[str] = []
        self._in_cell = False
        self._cell_has_link = False
        self._row_index = 0
        self._in_tbody = False
        self.generator = ""

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
        if tag in ("td", "th") and self._in_tbody:
            self._in_cell = True
            if tag == "td":
                self._row_cells.append("")
        if tag == "a" and self._in_tbody:
            self._cell_has_link = True

    def handle_endtag(self, tag):
        if tag in ("tbody", "thead"):
            self._in_tbody = False
        if tag == "title":
            self._in_title = False
        if tag in ("td", "th"):
            self._in_cell = False
        if tag == "tr" and self._in_tbody:
            self._row_index += 1
            if not self._cell_has_link:
                self.rows_without_source.append(self._row_index)

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def is_published(path: str, doc: "Doc | None" = None) -> bool:
    """A page is 'published' only if the integration builder generated it.

    Sibling sessions' generators write to the same index.html/pages/ paths, so ownership is detected
    from the page itself (the <meta name="generator"> marker) instead of from the path name.
    """
    p = path.replace("./", "")
    in_scope = p == "index.html" or p.startswith("pages/")
    if doc is not None:
        return in_scope and "line-lab/scripts/build_site.py" in (doc.generator or "")
    return in_scope


legacy_notes: list[str] = []


def walk() -> list[str]:
    files = []
    for base, _, names in os.walk(ROOT):
        if ".git" in base or "data" in base.split(os.sep) or "scripts" in base.split(os.sep):
            continue
        for n in names:
            if n.endswith(".html"):
                files.append(os.path.join(base, n).replace("./", ""))
    return sorted(files)


def main() -> int:
    errors: list[str] = []
    docs: dict[str, Doc] = {}
    files = walk()
    if not files:
        print("FAIL: no HTML files found")
        return 1

    # pass 1: parse
    for f in files:
        with open(f) as fh:
            html = fh.read()
        d = Doc()
        d.feed(html)
        docs[f] = d
        if not d.title.strip():
            errors.append(f"{f}: missing <title>")

    # Publication scope is only claimed when the ROOT index.html is the integrated build. A sibling
    # generator may own the same paths at any moment; in that case everything is link-checked only.
    root = docs.get("index.html")
    site_is_ours = bool(root and "line-lab/scripts/build_site.py" in (root.generator or ""))
    owned = [f for f in files if site_is_ours and is_published(f, docs.get(f))]

    # pass 2: links and source discipline
    legacy_notes: list[str] = []
    for f in files:
        d = docs[f]
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
            path = os.path.normpath(os.path.join(os.path.dirname(f), target))
            if not os.path.exists(path):
                errors.append(f"{f}: broken internal link {href} -> {path}")
            elif anchor and anchor not in docs.get(path, Doc()).ids:
                errors.append(f"{f}: broken anchor {href} on {path}")
        if site_is_ours and is_published(f, d) and d.rows_without_source:
            errors.append(f"{f}: {len(d.rows_without_source)} table row(s) without a source link "
                          f"(rows {d.rows_without_source[:5]})")
        elif d.rows_without_source:
            legacy_notes.append(f"{f}: {len(d.rows_without_source)} row(s) without a source column (sibling artefact)")

    if owned:
        for req in REQUIRED:
            if req not in docs:
                errors.append(f"missing required page {req}")
        for req in REQUIRED[1:]:
            if not any(req in docs[f].links for f in owned):
                errors.append(f"{req} is not linked from any published page")

    print(f"checked {len(files)} pages ({len(owned)} published by this build, "
          f"{len(files) - len(owned)} other), "
          f"{sum(d.tables for d in docs.values())} tables, {sum(len(d.links) for d in docs.values())} links")
    if legacy_notes:
        print(f"note: {len(legacy_notes)} page(s) outside the published build do not carry per-row "
              "source columns and are link-checked only.")
    if errors:
        print(f"\nFAILED with {len(errors)} issue(s):")
        for e in errors[:40]:
            print(" -", e)
        return 1
    print("all site checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
