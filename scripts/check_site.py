#!/usr/bin/env python3
"""Validate the static dashboard's local links and source-cited data rows."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted(ROOT.glob("*.html"))

class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.anchors = set()
        self.table_depth = 0
        self.row_depth = 0
        self.cell_depth = 0
        self.row_has_link = False
        self.rows_missing_source = 0
        self.in_thead = 0
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
            if self.row_depth and not self.in_thead:
                self.row_has_link = True
        if tag == "table":
            self.table_depth += 1
        elif tag == "thead":
            self.in_thead += 1
        elif tag == "tr" and self.table_depth:
            self.row_depth += 1
            self.row_has_link = False
        elif tag == "td" and self.row_depth:
            self.cell_depth += 1
        if attrs.get("id"):
            self.anchors.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.anchors.add(attrs["name"])

    def handle_endtag(self, tag):
        if tag == "td" and self.cell_depth:
            self.cell_depth -= 1
        elif tag == "tr" and self.row_depth:
            if not self.in_thead and not self.row_has_link:
                self.rows_missing_source += 1
            self.row_depth -= 1
        elif tag == "thead" and self.in_thead:
            self.in_thead -= 1
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1

def main():
    failures = []
    if not PAGES:
        print("FAIL: no top-level HTML pages found")
        return 1
    parsed = {}
    for page in PAGES:
        parser = AuditParser()
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        parsed[page.name] = parser
        if parser.rows_missing_source:
            failures.append(f"{page.name}: {parser.rows_missing_source} table body row(s) have no source link")
    for page in PAGES:
        for href in parsed[page.name].links:
            url = urlparse(href)
            if url.scheme or url.netloc or href.startswith("mailto:"):
                continue
            target_name = url.path or page.name
            target = (page.parent / target_name).resolve()
            if not target.exists():
                failures.append(f"{page.name}: broken local link {href}")
                continue
            if url.fragment and target.suffix.lower() == ".html":
                target_parser = parsed.get(target.name)
                if target_parser is None:
                    target_parser = AuditParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                if url.fragment not in target_parser.anchors:
                    failures.append(f"{page.name}: missing anchor in {href}")
    if failures:
        print("SITE CHECK FAILED")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"PASS: checked {len(PAGES)} HTML pages, internal links/anchors, and source links on every table body row.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
