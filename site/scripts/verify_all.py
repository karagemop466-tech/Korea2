#!/usr/bin/env python3
"""Verification suite for the Decision Desk section. Runs in CI and locally.

Checks
  1. every site/data/*.json parses as strict JSON (NaN / Infinity rejected);
  2. every source URL used in the data is absolute https;
  3. every table row on the eight decision pages carries an external https source link;
  4. the pages are byte-reproducible from the data (rebuilt and diffed, ignoring timestamps);
  5. the registers obey their own rules (allowed statuses, allowed question groups, ids unique,
     every suggestion has evidence and a recommended path);
  6. no page contains a placeholder that pretends to be data ("TBD", "TODO", "lorem");
  7. every page is reachable from the section hub (pages/decision-hub.html).

Exit code is non-zero if any check fails, so CI fails closed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(__file__).resolve().parents[1]
DATA = SITE / "data"
SCRIPTS = SITE / "scripts"

PAGES = [
    "decision-hub.html", "decision-suggestions.html", "decision-questions.html",
    "decision-injury-depth.html", "decision-signals.html", "decision-parlay.html",
    "decision-verify.html", "decision-summary.html",
]
TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
PLACEHOLDERS = ("TBD", "TODO", "lorem ipsum", "FIXME", "XXX")


class Rows(HTMLParser):
    """Collect, per table body row, whether it contains an external https link."""

    def __init__(self):
        super().__init__()
        self.rows: list[bool] = []
        self._in_tbody = False
        self._row_open = False
        self._has_ext = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._row_open, self._has_ext = True, False
        elif tag == "a" and self._row_open and str(a.get("href", "")).startswith("https://"):
            self._has_ext = True

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_tbody = False
        elif tag == "tr" and self._row_open:
            self.rows.append(self._has_ext)
            self._row_open = False


def strict_load(path: Path):
    def reject(token):
        raise ValueError(f"{path.name}: non-JSON token {token}")

    return json.loads(path.read_text(), parse_constant=reject)


def walk_urls(obj, out: list[str], key: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk_urls(v, out, k)
    elif isinstance(obj, list):
        for v in obj:
            walk_urls(v, out, key)
    elif isinstance(obj, str) and (key.endswith("source") or key.endswith("url")
                                   or key in ("source", "url")):
        out.append(obj)


def run(script: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / script)], check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL)


def main() -> int:
    errors: list[str] = []

    # 1 / 2 - data integrity
    docs = {}
    for p in sorted(DATA.glob("*.json")):
        try:
            docs[p.name] = strict_load(p)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"data: {exc}")
    if not docs:
        errors.append("data: no site/data/*.json files found")

    urls: list[str] = []
    for name, doc in docs.items():
        found: list[str] = []
        walk_urls(doc, found)
        for u in found:
            if not u.startswith("https://"):
                errors.append(f"{name}: non-https source {u[:80]}")
            urls.append(u)
    if len(set(urls)) < 10:
        errors.append(f"data: only {len(set(urls))} distinct source URLs - expected a real register")

    # 5 - register rules
    sug = docs.get("suggestions.json", {})
    statuses = set(sug.get("meta", {}).get("statuses", []))
    ids = set()
    for s in sug.get("suggestions", []):
        if s["id"] in ids:
            errors.append(f"suggestions: duplicate id {s['id']}")
        ids.add(s["id"])
        if s["review"] not in statuses:
            errors.append(f"suggestions: {s['id']} has unknown status {s['review']}")
        for field in ("title", "problem", "proposal", "effort", "payoff", "risk", "evidence",
                      "recommend", "source"):
            if not s.get(field):
                errors.append(f"suggestions: {s['id']} is missing {field}")
    if len(sug.get("suggestions", [])) < 10:
        errors.append("suggestions: fewer than 10 entries")

    qs = docs.get("questions.json", {})
    groups = set(qs.get("meta", {}).get("groups", []))
    qids = set()
    for q in qs.get("questions", []):
        if q["id"] in qids:
            errors.append(f"questions: duplicate id {q['id']}")
        qids.add(q["id"])
        if q["group"] not in groups:
            errors.append(f"questions: {q['id']} has unknown group {q['group']}")
        for field in ("question", "answer", "have", "missing", "decision_needed", "source"):
            if not q.get(field):
                errors.append(f"questions: {q['id']} is missing {field}")

    # 3 / 6 - page discipline
    total_rows = 0
    for name in PAGES:
        path = ROOT / "pages" / name
        if not path.exists():
            errors.append(f"pages: missing {name} (run site/scripts/build_site.py)")
            continue
        html = path.read_text()
        parser = Rows()
        parser.feed(html)
        total_rows += len(parser.rows)
        bad = [i + 1 for i, ok in enumerate(parser.rows) if not ok]
        if bad:
            errors.append(f"{name}: {len(bad)} table row(s) with no external https source "
                          f"(rows {bad[:5]})")
        low = html.lower()
        for ph in PLACEHOLDERS:
            if ph.lower() in low:
                errors.append(f"{name}: placeholder text {ph!r} found")
        if "content=\"line-lab/scripts/build_site.py\"" not in html:
            errors.append(f"{name}: not written by the site generator")

    # 4 - reproducibility
    run("reverify.py")
    run("registers.py")
    run("signal_lab.py")
    run("correlations.py")
    run("injury_depth.py")
    run("build_site.py")
    first = {n: TS.sub("<ts>", (ROOT / "pages" / n).read_text()) for n in PAGES}
    run("build_site.py")
    second = {n: TS.sub("<ts>", (ROOT / "pages" / n).read_text()) for n in PAGES}
    for n in PAGES:
        if first[n] != second[n]:
            errors.append(f"{n}: rebuild is not reproducible from site/data")

    # 7 - reachable from the dashboard navigation
    hub = ROOT / "pages" / "decision-hub.html"
    if hub.exists():
        hub_html = hub.read_text()
        for n in PAGES:
            if n != "decision-hub.html" and f"pages/{n}" not in hub_html:
                errors.append(f"pages/decision-hub.html: navigation does not link {n}")

    print(f"decision desk: {len(docs)} data files, {len(set(urls))} distinct source URLs, "
          f"{len(PAGES)} pages, {total_rows} table rows")
    if errors:
        print(f"FAILED with {len(errors)} issue(s):")
        for e in errors[:40]:
            print(" -", e)
        return 1
    print("all decision-desk checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
