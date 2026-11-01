"""Static link and sanity checker for the published site.

Standard library only, so it runs in CI with no install step.

Checks
------
1. Every relative href/src in every HTML file resolves to a file that exists.
2. Every in-page anchor (#id) in a relative link exists in the target file.
3. Every page declares a <title> and a main navigation bar.
4. Every site_data/*.json parses.
5. Optional: --external also issues HEAD requests to outbound links (skipped in CI,
   because the build network cannot reach most of them).

Exit code is non-zero if anything fails, which is what the CI job keys off.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "origination"
HTML_FILES = sorted([SITE / "index.html"] + list((SITE / "pages").glob("*.html")))
LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')


def is_external(url: str) -> bool:
    return url.startswith(("http://", "https://", "mailto:", "//"))


def check(external: bool = False) -> tuple[list[str], dict]:
    problems: list[str] = []
    stats = {"files": len(HTML_FILES), "links": 0, "external": 0, "internal": 0, "anchors": 0}
    external_seen: set[str] = set()

    for f in HTML_FILES:
        text = f.read_text()
        rel = f.relative_to(ROOT)
        if "<title>" not in text:
            problems.append(f"{rel}: missing <title>")
        if 'class="mainnav"' not in text:
            problems.append(f"{rel}: missing navigation")
        if not text.rstrip().endswith("</html>"):
            problems.append(f"{rel}: does not end with </html>")
        for url in LINK_RE.findall(text):
            stats["links"] += 1
            if is_external(url):
                stats["external"] += 1
                external_seen.add(url)
                continue
            stats["internal"] += 1
            path_part, _, anchor = url.partition("#")
            target = (f.parent / path_part).resolve() if path_part else f
            if path_part and not target.exists():
                problems.append(f"{rel}: broken link -> {url}")
                continue
            if anchor:
                stats["anchors"] += 1
                ids = set(ID_RE.findall(target.read_text())) if target.suffix == ".html" else set()
                if anchor not in ids:
                    problems.append(f"{rel}: missing anchor #{anchor} in {target.relative_to(ROOT)}")

    for jf in sorted((SITE / "site_data").glob("*.json")):
        try:
            json.loads(jf.read_text())
        except Exception as exc:  # noqa: BLE001
            problems.append(f"site_data/{jf.name}: invalid JSON ({exc})")

    if external:
        for url in sorted(external_seen):
            try:
                req = urllib.request.Request(url, method="HEAD",
                                             headers={"User-Agent": "korea2-linkcheck/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        problems.append(f"external {url}: HTTP {resp.status}")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"external {url}: {type(exc).__name__}")
    stats["unique_external"] = len(external_seen)
    return problems, stats


def main() -> int:
    external = "--external" in sys.argv
    problems, stats = check(external)
    print(f"checked {stats['files']} HTML files, {stats['links']:,} links "
          f"({stats['internal']:,} internal, {stats['external']:,} external, "
          f"{stats['unique_external']} unique external URLs), {stats['anchors']} anchors")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("no broken internal links, no missing titles or navigation, all JSON parses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
