#!/usr/bin/env python3
"""Build readiness/index.html from readiness/data/requirements.json.

Fails loudly (exit 1) when:
  * a row has an unknown status, a duplicate id, or a missing required field;
  * a non-Built row lacks a 'now' or 'needed' value;
  * an evidence path does not exist in the repository;
  * an official-source label has no mapped URL, or the mapped URL is not on an allowlisted official host.

Nothing is fetched from the network. Official URLs are the ones already recorded in committed
registers (see the 'basis' note in requirements.json); they are linked for manual review only.
"""
from __future__ import annotations

import html
import json
import os
import sys
from collections import Counter
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "..", "data", "requirements.json")
OUT = os.path.join(HERE, "..", "index.html")
REPO_WEB = "https://github.com/karagemop466-tech/Korea2"

STATUSES = {"Built", "Partial", "Not built", "Blocked", "Not met", "Not located"}
REQUIRED = ["id", "group", "requirement", "status", "evidence", "gate", "now", "needed", "official_sources", "note"]
OFFICIAL_HOSTS = {"www.nfl.com", "nfl.com", "static.www.nfl.com", "www.weather.gov", "www.itl.nist.gov"}

# Official sources: label -> URL. Every URL here is one already recorded in a committed register.
OFFICIAL_URLS = {
    "NFL.com 2025 standings": "https://www.nfl.com/standings/division/2025/REG",
    "NFL.com 2026 standings": "https://www.nfl.com/standings/division/2026/REG",
    "NFL.com 2026 standings (regular season)": "https://www.nfl.com/standings/division/2026/REG",
    "NFL.com 2026 schedule, Week 10": "https://www.nfl.com/schedules/2026/by-week/week-10",
    "NFL.com Week 10 2026 injury report": "https://www.nfl.com/injuries/league/2026/REG10",
    "NFL Game Book, WAS@NYG (week 10 2026, as cited in the repo)": "https://static.www.nfl.com/image/upload/v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf",
    "NFL.com: Drew Lock, no injury designation": "https://www.nfl.com/news/drew-lock-no-injury-designation-seahawks-raiders",
    "NFL.com: Malik Willis on IR, McCord in line to start": "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start",
    "NFL.com: Malik Willis on IR": "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start",
    "NFL.com: news roundup, Nov 14 (Henderson IR)": "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14",
    "NWS NOWData FAQ": "https://www.weather.gov/climateservices/nowdatafaq",
    "NIST correlation interval reference": "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm",
}

STATUS_CLASS = {
    "Built": "ok", "Partial": "warn", "Not built": "idle", "Blocked": "bad", "Not met": "bad", "Not located": "bad",
}


class BuildError(Exception):
    pass


def validate(doc: dict) -> list[dict]:
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise BuildError("no rows found in requirements.json")
    seen: set[str] = set()
    errors: list[str] = []
    for r in rows:
        rid = r.get("id", "<no id>")
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        for key in REQUIRED:
            if key not in r:
                errors.append(f"{rid}: missing field '{key}'")
        if r.get("status") not in STATUSES:
            errors.append(f"{rid}: unknown status {r.get('status')!r}")
        if r.get("status") != "Built":
            for key in ("now", "needed", "gate"):
                if not str(r.get(key, "")).strip():
                    errors.append(f"{rid}: '{key}' is blank for status {r.get('status')}")
        for ev in r.get("evidence", []):
            if not os.path.exists(os.path.join(ROOT, ev)):
                errors.append(f"{rid}: evidence path does not exist: {ev}")
        for label in r.get("official_sources", []):
            url = OFFICIAL_URLS.get(label)
            if not url:
                errors.append(f"{rid}: official source label has no mapped URL: {label!r}")
                continue
            host = urlparse(url).hostname or ""
            if host not in OFFICIAL_HOSTS:
                errors.append(f"{rid}: mapped URL is not on an official host: {url}")
    if errors:
        raise BuildError("\n".join(errors))
    return rows


def repo_link(path: str) -> str:
    full = os.path.join(ROOT, path)
    kind = "tree" if os.path.isdir(full) else "blob"
    return f"{REPO_WEB}/{kind}/main/{path}"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def official_cell(labels: list[str]) -> str:
    if not labels:
        return '<span class="unv">unverified: no official source recorded</span>'
    parts = []
    for label in labels:
        parts.append(f'<a href="{esc(OFFICIAL_URLS[label])}" rel="noopener">{esc(label)}</a>')
    return "<br>".join(parts)


def evidence_cell(paths: list[str]) -> str:
    if not paths:
        return '<span class="unv">none in repo</span>'
    return "<br>".join(f'<a href="{esc(repo_link(p))}" rel="noopener"><code>{esc(p)}</code></a>' for p in paths)


def status_badge(status: str) -> str:
    return f'<span class="badge {STATUS_CLASS[status]}">{esc(status)}</span>'


def render(doc: dict, rows: list[dict]) -> str:
    meta = doc["meta"]
    counts = Counter(r["status"] for r in rows)
    order = ["Built", "Partial", "Not built", "Blocked", "Not met", "Not located"]
    cards = "".join(
        f'<div class="card"><div class="n">{counts.get(s, 0)}</div><div class="l">{esc(s)}</div></div>' for s in order
    )
    groups: list[str] = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])

    body_rows = []
    for g in groups:
        body_rows.append(f'<tr class="grp"><td colspan="7">{esc(g)}</td></tr>')
        for r in (x for x in rows if x["group"] == g):
            note = f'<div class="note">{esc(r["note"])}</div>' if r.get("note") else ""
            body_rows.append(
                "<tr>"
                f'<td class="id">{esc(r["id"])}</td>'
                f'<td>{esc(r["requirement"])}</td>'
                f'<td>{status_badge(r["status"])}</td>'
                f'<td>{esc(r["gate"])}</td>'
                f'<td><div><b>Now:</b> {esc(r["now"])}</div><div><b>Clears when:</b> {esc(r["needed"])}</div>{note}</td>'
                f'<td>{evidence_cell(r["evidence"])}</td>'
                f'<td>{official_cell(r["official_sources"])}</td>'
                "</tr>"
            )

    flagged = [r for r in rows if r["status"] in {"Not met", "Not located", "Blocked"} or "Mis-reference" in r.get("note", "")]
    flag_rows = "".join(
        f'<tr><td class="id">{esc(r["id"])}</td><td>{esc(r["requirement"])}</td><td>{status_badge(r["status"])}</td>'
        f'<td>{esc(r["gate"])}</td><td>{esc(r["note"]) or "&mdash;"}</td></tr>'
        for r in flagged
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decision readiness | NFL research</title>
<style>
  :root {{ --ink:#1b2430; --muted:#5b6674; --line:#dfe4ea; --bg:#f6f8fa; --ok:#1f7a4d; --warn:#a15c00; --bad:#b42318; --idle:#55606e; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink); background:#fff; }}
  header {{ background:var(--bg); border-bottom:1px solid var(--line); padding:20px 24px; }}
  header h1 {{ margin:0 0 4px; font-size:22px; }}
  header p {{ margin:0; color:var(--muted); max-width:920px; }}
  nav {{ margin-top:10px; font-size:14px; }}
  nav a {{ margin-right:14px; color:#1d4ed8; }}
  main {{ padding:20px 24px 48px; }}
  .cards {{ display:flex; flex-wrap:wrap; gap:10px; margin:6px 0 18px; }}
  .card {{ border:1px solid var(--line); border-radius:8px; padding:10px 16px; min-width:118px; }}
  .card .n {{ font-size:24px; font-weight:600; }}
  .card .l {{ color:var(--muted); font-size:13px; }}
  h2 {{ font-size:18px; margin:26px 0 8px; }}
  .wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; }}
  table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
  th, td {{ text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th {{ background:var(--bg); position:sticky; top:0; font-weight:600; }}
  tr.grp td {{ background:#eef2f6; font-weight:600; color:var(--muted); }}
  td.id {{ white-space:nowrap; font-weight:600; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; color:#fff; }}
  .badge.ok {{ background:var(--ok); }} .badge.warn {{ background:var(--warn); }}
  .badge.bad {{ background:var(--bad); }} .badge.idle {{ background:var(--idle); }}
  .unv {{ color:var(--bad); font-style:italic; }}
  .note {{ color:var(--muted); margin-top:4px; }}
  code {{ font-size:12px; }}
  a {{ color:#1d4ed8; }}
  .basis {{ background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:12px 16px; font-size:14px; }}
  footer {{ color:var(--muted); font-size:13px; margin-top:28px; }}
</style>
</head>
<body>
<header>
  <h1>Decision readiness: one row per requirement</h1>
  <p>Each requirement from the brief, its status measured against this repository, the gate that blocks it, and the number that would clear it.</p>
  <nav>
    <a href="../">Home</a>
    <a href="data/requirements.json">Register (JSON)</a>
    <a href="{REPO_WEB}/blob/main/readiness/scripts/build.py">Build script</a>
    <a href="{REPO_WEB}/blob/main/COORDINATION.md">Coordination board</a>
  </nav>
</header>
<main>
  <div class="basis"><b>Basis.</b> {esc(meta["basis"])}<br><b>Prepared:</b> {esc(meta["prepared_on"])} &middot; <b>Session:</b> {esc(meta["session"])} &middot; <b>Rows:</b> {len(rows)}</div>
  <p><b>Policy.</b> {esc(meta["policy"])}</p>
  <div class="cards">{cards}</div>
  <h2>Requirements</h2>
  <div class="wrap"><table>
    <thead><tr><th>ID</th><th>Requirement</th><th>Status</th><th>Blocking gate</th><th>Number that clears it</th><th>Repo evidence</th><th>Official source (recorded)</th></tr></thead>
    <tbody>{"".join(body_rows)}</tbody>
  </table></div>
  <h2>Flagged for review</h2>
  <p>Rows that fail the requirement, cannot be located, or are blocked, plus mis-references. Listed so the owner can request changes.</p>
  <div class="wrap"><table>
    <thead><tr><th>ID</th><th>Requirement</th><th>Status</th><th>Blocking gate</th><th>Note</th></tr></thead>
    <tbody>{flag_rows}</tbody>
  </table></div>
  <footer>Generated by <code>readiness/scripts/build.py</code> from <code>readiness/data/requirements.json</code>. Repository evidence links point to the main branch. Official links were recorded by earlier sessions and were not re-opened in this build; nothing was fetched from the network.</footer>
</main>
</body>
</html>
"""


def main() -> int:
    with open(DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    try:
        rows = validate(doc)
    except BuildError as exc:
        print("FAIL: readiness register does not validate\n" + str(exc), file=sys.stderr)
        return 1
    page = render(doc, rows)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    counts = Counter(r["status"] for r in rows)
    print(f"PASS: {len(rows)} rows; " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
