#!/usr/bin/env python3
"""Verification suite for verify-hub (run in CI and locally).

Checks
  1. every data/*.json file parses as strict JSON (no NaN/Infinity);
  2. every row in every rows-style list carries a non-empty "sources" array of
     ids that exist in sources.json;
  3. flagged rows have a BLANK value (never inferred) and a reason;
  4. every <tbody> table row in the generated HTML ends with a source cell that
     contains at least one <a href>;
  5. every internal link resolves to a file, every external link is https;
  6. the site build is deterministic (rebuild is byte-identical);
  7. no Python str(None)/'nan' leaks into the generated HTML.

Exit code 0 = pass, 1 = fail. Standard library only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ROW_KEYS = ("rows",)


class TableChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tbody = False
        self.row_has_link = False
        self.rows_without_source: list[int] = []
        self.row_index = 0
        self.links: list[str] = []
        self.current_row = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
            if self.current_row:
                self.row_has_link = True
        if tag == "tbody":
            self.in_tbody = True
        if tag == "tr" and self.in_tbody:
            self.current_row = True
            self.row_has_link = False

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody:
            self.row_index += 1
            if not self.row_has_link:
                self.rows_without_source.append(self.row_index)
            self.current_row = False
        if tag == "tbody":
            self.in_tbody = False


def strict_json(path: Path):
    def _fail(msg):
        raise ValueError(f"{path}: {msg}")

    def _pairs(pairs):
        return dict(pairs)

    text = path.read_text(encoding="utf-8")
    return json.loads(text, parse_constant=_fail, object_pairs_hook=_pairs)


def check_data(errors: list[str]) -> int:
    sources = strict_json(DATA / "sources.json")
    known = {s["id"] for s in sources["sources"]}
    rows = 0
    for path in sorted(DATA.glob("*.json")):
        try:
            doc = strict_json(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"strict JSON failed: {exc}")
            continue
        if path.name == "sources.json":
            continue
        for key in ROW_KEYS:
            for i, row in enumerate(doc.get(key, [])):
                rows += 1
                rid = row.get("id", f"{path.name}#{i}")
                srcs = row.get("sources")
                if not isinstance(srcs, list) or not srcs:
                    errors.append(f"{path.name}[{rid}]: missing sources array")
                    continue
                for sid in srcs:
                    if sid not in known:
                        errors.append(f"{path.name}[{rid}]: unknown source id {sid}")
                if path.name == "flagged.json":
                    if row.get("value", "") != "":
                        errors.append(f"{path.name}[{rid}]: flagged value must stay blank")
                    if not row.get("reason"):
                        errors.append(f"{path.name}[{rid}]: flagged row missing reason")
        # nested row lists used by the hub
        for key in ("cross_lab_rows", "correlation_rows", "gate_catalog_rows",
                    "reward_rows", "luck_rows", "gap_rows"):
            for i, row in enumerate(doc.get(key, [])):
                rows += 1
                rid = row.get("id", f"{path.name}#{key}#{i}")
                srcs = row.get("sources")
                if not isinstance(srcs, list) or not srcs:
                    errors.append(f"{path.name}[{rid}]: missing sources array")
                for sid in srcs or []:
                    if sid not in known:
                        errors.append(f"{path.name}[{rid}]: unknown source id {sid}")
        sample = doc.get("verified_week10_sample", {}).get("rows", [])
        for i, row in enumerate(sample):
            rows += 1
            srcs = row.get("sources")
            if not isinstance(srcs, list) or not srcs:
                errors.append(f"{path.name}[sample#{i}]: missing sources array")
            if row.get("string", "") not in ("", None):
                errors.append(f"{path.name}[sample#{i}]: depth string must stay blank")
    return rows


def check_html(errors: list[str]) -> tuple[int, int]:
    pages = 0
    rows = 0
    for path in sorted(ROOT.rglob("*.html")):
        pages += 1
        text = path.read_text(encoding="utf-8")
        if re.search(r">\s*(None|nan)\s*<", text):
            errors.append(f"{path.relative_to(ROOT)}: Python None/nan leaked into an HTML cell")
        doc = TableChecker()
        doc.feed(text)
        rows += doc.row_index
        if doc.rows_without_source:
            errors.append(
                f"{path.relative_to(ROOT)}: {len(doc.rows_without_source)} table row(s) without a source link")
        for href in doc.links:
            if href.startswith(("http://", "https://", "mailto:")):
                if href.startswith("http://"):
                    errors.append(f"{path.relative_to(ROOT)}: insecure link {href}")
                continue
            if href.startswith("#"):
                continue
            target = (path.parent / href.split("#")[0]).resolve()
            if not target.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken internal link {href}")
    return pages, rows


def check_deterministic(errors: list[str]) -> None:
    build = ROOT / "scripts" / "build_site.py"
    before = {p: p.read_bytes() for p in sorted(ROOT.rglob("*.html"))}
    before_md = (ROOT / "EXECUTIVE_SUMMARY.md").read_bytes()
    subprocess.run([sys.executable, str(build)], check=True, capture_output=True)
    for p, content in before.items():
        if p.read_bytes() != content:
            errors.append(f"build is not deterministic: {p.relative_to(ROOT)} changed on rebuild")
    if (ROOT / "EXECUTIVE_SUMMARY.md").read_bytes() != before_md:
        errors.append("build is not deterministic: EXECUTIVE_SUMMARY.md changed on rebuild")


def main() -> int:
    errors: list[str] = []
    rows = check_data(errors)
    pages, table_rows = check_html(errors)
    check_deterministic(errors)
    print(f"checked {len(list(DATA.glob('*.json')))} data files ({rows} rows), "
          f"{pages} pages ({table_rows} table rows)")
    if errors:
        print(f"\nFAILED with {len(errors)} issue(s):")
        for e in errors[:40]:
            print(" -", e)
        return 1
    print("all verify-hub checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
