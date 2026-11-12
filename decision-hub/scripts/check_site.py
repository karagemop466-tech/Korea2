#!/usr/bin/env python3
"""Static checks for the decision hub.

Fails on:
  * a broken internal link or asset reference;
  * a table row whose final cell has no source link;
  * an anchor link whose target id does not exist;
  * a literal 'None' or 'nan' rendered into a table cell;
  * a page in the navigation that does not exist, or a page on disk not reachable from it.

Exit code 0 only when every check passes. Run from the repository root:
    python decision-hub/scripts/check_site.py
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import unquote

HUB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NAV_PAGES = None


def html_files():
    out = []
    for root, _dirs, files in os.walk(HUB):
        for f in files:
            if f.endswith(".html"):
                out.append(os.path.join(root, f))
    return sorted(out)


def main() -> int:
    problems: list[str] = []
    files = html_files()
    by_rel = {os.path.relpath(p, HUB): p for p in files}
    ids_cache: dict[str, set[str]] = {}

    def ids_of(rel: str) -> set[str]:
        if rel not in ids_cache:
            text = open(by_rel[rel], encoding="utf-8").read()
            ids_cache[rel] = set(re.findall(r'\bid="([^"]+)"', text))
        return ids_cache[rel]

    # navigation consistency
    index = open(os.path.join(HUB, "index.html"), encoding="utf-8").read()
    nav_hrefs = re.findall(r'<nav aria-label="Main navigation">(.*?)</nav>', index, re.S)
    nav = re.findall(r'href="([^"]+)"', nav_hrefs[0]) if nav_hrefs else []
    for href in nav:
        if not os.path.exists(os.path.join(HUB, href.split("#")[0])):
            problems.append(f"nav target missing: {href}")
    for rel in by_rel:
        if rel == "index.html":
            continue
        if rel not in nav:
            problems.append(f"page not reachable from navigation: {rel}")

    rows_total = rows_missing_src = tables_total = 0
    for rel, path in by_rel.items():
        text = open(path, encoding="utf-8").read()
        base = os.path.dirname(rel)

        # links
        for href in re.findall(r'(?:href|src)="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            if href.startswith("#"):
                if href[1:] and href[1:] not in ids_of(rel):
                    problems.append(f"{rel}: missing anchor {href}")
                continue
            target_rel = os.path.normpath(os.path.join(base, unquote(href.split("#")[0])))
            if not os.path.exists(os.path.join(HUB, target_rel)):
                problems.append(f"{rel}: broken internal link {href}")
                continue
            if "#" in href and target_rel.endswith(".html") and "#" in href:
                frag = href.split("#", 1)[1]
                if frag and target_rel in by_rel and frag not in ids_of(target_rel):
                    problems.append(f"{rel}: missing anchor {href}")

        # tables: every body row must end in a source cell containing a link
        for t_i, table in enumerate(re.findall(r"<table[^>]*>.*?</table>", text, re.S)):
            tables_total += 1
            body = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
            if not body:
                continue
            for r_i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if not tds:
                    continue
                rows_total += 1
                last = tds[-1]
                if "<a " not in last:
                    rows_missing_src += 1
                    problems.append(f"{rel}: table {t_i} row {r_i} has no source link")
                if re.search(r"\bNone\b|>nan<|>None<", last) or last.strip() in ("None", "nan"):
                    problems.append(f"{rel}: table {t_i} row {r_i} renders None/nan")

    # A hand-written count in a data file is a defect waiting to happen: every figure shown on
    # the site must be derived from an array at build time.
    for name in ("suggestions.json", "questions.json"):
        path = os.path.join(HUB, "data", name)
        if os.path.exists(path):
            import json as _json
            meta = _json.load(open(path)).get("meta", {})
            if isinstance(meta.get("counts"), dict):
                problems.append(f"{name}: meta.counts is a stored tally; compute it at build time instead")

    print(f"checked {len(files)} pages, {tables_total} tables, {rows_total} table rows")
    if rows_total:
        print(f"rows with a source link: {rows_total - rows_missing_src}/{rows_total}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:60]:
            print(" -", p)
        if len(problems) > 60:
            print(f" ... and {len(problems) - 60} more")
        return 1
    print("all decision-hub checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
