#!/usr/bin/env python3
"""Link checker for the generated site.

  * internal page links must resolve to a file that exists in docs/
  * in-page anchors must resolve to an id on the target page
  * external http(s) links are probed with curl; hosts that the build sandbox
    cannot reach (documented in COORDINATION.md §5) are reported separately as
    "unreachable from sandbox" rather than silently passed

Exit code is non-zero if any internal link or anchor is broken.
Writes docs/link-check.json (used by the site footer/flagged page statistics).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
KNOWN_BLOCKED = {"www.nfl.com", "nfl.com", "operations.nfl.com"}

HREF = re.compile(r'(?:href|src)="([^"]+)"')
ID = re.compile(r'id="([^"]+)"')


def curl_status(url: str) -> int | None:
    try:
        out = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L",
                              "--max-time", "20", "-A", "Mozilla/5.0 (link-check)", url],
                             capture_output=True, text=True)
        return int(out.stdout.strip()[-3:])
    except Exception:
        return None


def main():
    pages = sorted(DOCS.glob("*.html"))
    if not pages:
        raise SystemExit("no pages found - run build_site.py first")
    ids = {p.name: set(ID.findall(p.read_text())) for p in pages}
    broken, external, blocked = [], {}, set()

    for p in pages:
        html = p.read_text()
        for ref in HREF.findall(html):
            if ref.startswith(("data:", "mailto:", "javascript:")):
                continue
            if ref.startswith("#"):
                if ref[1:] and ref[1:] not in ids[p.name]:
                    broken.append((p.name, ref, "missing anchor on same page"))
                continue
            if "://" in ref:
                u = urlparse(ref)
                if u.scheme in ("http", "https"):
                    external.setdefault(f"{u.scheme}://{u.netloc}", set()).add(ref)
                continue
            path, _, anchor = ref.partition("#")
            target = (DOCS / path).resolve()
            if not target.exists():
                broken.append((p.name, ref, "missing file"))
            elif anchor and anchor not in ids.get(target.name, set()):
                broken.append((p.name, ref, "missing anchor in target"))

    status = {}
    for host, urls in sorted(external.items()):
        hostname = host.split("://")[1]
        if hostname in KNOWN_BLOCKED:
            blocked.add(hostname)
            status[host] = {"checked": len(urls), "status": "unreachable-from-sandbox"}
            continue
        codes = sorted({curl_status(u) for u in sorted(urls) if curl_status(u) is not None})
        # one re-check for the advertised URL of each host
        status[host] = {"checked": len(urls), "codes": codes,
                        "status": "ok" if codes and all(c == 200 for c in codes) else "review"}

    report = {
        "pages": len(pages),
        "internal_links": sum(1 for _ in HREF.findall("".join(p.read_text() for p in pages))),
        "broken": broken,
        "external_hosts": status,
        "unreachable_from_sandbox": sorted(blocked),
        "anchors_checked": sum(len(v) for v in ids.values()),
    }
    (DOCS / "link-check.json").write_text(json.dumps(report, indent=1) + "\n")
    for k, v in status.items():
        print(f"  {k:45s} {v}")
    if broken:
        for b in broken:
            print(f"BROKEN {b[0]} -> {b[1]} ({b[2]})")
        raise SystemExit(f"{len(broken)} broken internal links")
    print(f"ok: {len(pages)} pages, no broken internal links, "
          f"{report['anchors_checked']} anchors")


if __name__ == "__main__":
    main()
