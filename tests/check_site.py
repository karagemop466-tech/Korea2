"""Static checks that must pass before the site is published.

1. Every local link resolves to a file that exists.
2. Every table body row carries at least one https source link.
3. Every page has the shared navigation, a title, and the stylesheet.
4. No unrendered template or missing-value sentinel leaks into the HTML.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SENTINELS = ("None</td>", ">nan<", "NaN</td>", "{", "}", "undefined")

NAV_HREFS = [
    "index.html", "pages/executive.html", "pages/market.html", "pages/strategies.html",
    "pages/validation.html", "pages/leaderboard.html", "pages/correlation.html",
    "pages/props.html", "pages/lines.html", "pages/verification.html",
    "pages/sources.html", "pages/flagged.html",
]


class Check(HTMLParser):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.in_body = False
        self.row = None
        self.rows = 0
        self.external_links = 0
        self.errors: list[str] = []
        self.has_nav = False
        self.has_style = False
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "tbody":
            self.in_body = True
        if tag == "tr" and self.in_body:
            self.row = False
            self.rows += 1
        if tag == "nav":
            self.has_nav = True
        if tag == "link" and a.get("rel") == "stylesheet" and "style.css" in a.get("href", ""):
            self.has_style = True
        if tag in ("a", "link"):
            href = a.get("href", "")
            if tag == "a" and href.startswith("https://"):
                if self.row is not None:
                    self.row = True
                self.external_links += 1
            if href and not urlsplit(href).scheme and not href.startswith("#"):
                target = (self.path.parent / urlsplit(href).path).resolve()
                if not target.is_file():
                    self.errors.append(f"broken local link: {href}")

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "tr" and self.row is not None:
            if not self.row:
                self.errors.append("table row missing https source link")
            self.row = None
        if tag == "tbody":
            self.in_body = False


def main() -> int:
    errors: list[str] = []
    pages = [ROOT / "index.html", *sorted((ROOT / "pages").glob("*.html"))]
    if len(pages) < 12:
        errors.append(f"expected at least 12 pages, found {len(pages)}")
    total_rows = 0
    for path in pages:
        if not path.is_file():
            errors.append(f"missing page: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        parser = Check(path)
        parser.feed(text)
        rel = path.relative_to(ROOT)
        errors += [f"{rel}: {e}" for e in parser.errors]
        total_rows += parser.rows
        if not parser.has_nav:
            errors.append(f"{rel}: missing navigation")
        if not parser.has_style:
            errors.append(f"{rel}: missing stylesheet link")
        if not parser.title.strip():
            errors.append(f"{rel}: missing <title>")
        if "not betting advice" not in text:
            errors.append(f"{rel}: missing research disclaimer")
        for sentinel in SENTINELS:
            if sentinel in text:
                errors.append(f"{rel}: unrendered value {sentinel!r}")
        slot = "" if str(rel) == "index.html" else "../"
        for nav in NAV_HREFS:
            if f'href="{slot}{nav}"' not in text:
                errors.append(f"{rel}: nav missing {nav}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(pages)} pages, {total_rows} table rows, every row has an https source link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
