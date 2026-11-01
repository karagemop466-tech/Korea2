#!/usr/bin/env python3
"""Internal link checker for the static site (run in CI before deploy).

Verifies that every local href/src in every HTML file points to a file that
exists in the repo (no broken internal links), and that every data/*.json file
referenced by the site's JavaScript exists. External links are NOT fetched here
(they are verified manually per data/sources.json with verification dates);
this script only guarantees the site itself builds with no broken local links.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = list(ROOT.glob("*.html")) + list(ROOT.glob("pages/*.html"))
ATTR = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"')


def main() -> int:
    errors = []
    checked = 0
    for page in HTML:
        text = page.read_text(encoding="utf-8")
        for m in ATTR.finditer(text):
            link = m.group(1)
            if link.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            if any(ch in link for ch in "'\"+{}<>"):  # JS-generated value, not a literal path
                continue
            target = link.split("#")[0].split("?")[0]
            if not target:
                continue
            checked += 1
            if not (page.parent / target).resolve().exists():
                errors.append(f"{page.relative_to(ROOT)}: broken local link -> {link}")
    # data files referenced from JS
    js = list(ROOT.glob("assets/js/*.js"))
    for j in js:
        for m in re.finditer(r'data/([a-z_]+\.json)', j.read_text(encoding="utf-8")):
            checked += 1
            if not (ROOT / "data" / m.group(1)).exists():
                errors.append(f"{j.relative_to(ROOT)}: missing data file data/{m.group(1)}")
    print(f"checked {checked} local references across {len(HTML)} HTML pages + {len(js)} JS files")
    if errors:
        for e in errors:
            print("ERROR", e)
        print(f"FAIL: {len(errors)} broken local link(s)")
        return 1
    print("PASS: no broken internal links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
