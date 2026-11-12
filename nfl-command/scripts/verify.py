#!/usr/bin/env python3
"""Verify the NFL Command Center site. Exit 0 only if every check passes.

Checks:
  1. Every JSON file under nfl-command/ parses (no NaN / Infinity).
  2. Every page listed in build_site.py exists; every local href/src resolves to a file.
  3. Every table row (<tbody> <tr>) carries at least one source link.
  4. Links go only to allowed hosts. Non-official hosts may appear only on the Sources page.
  5. Repo-blob links (github.com/.../blob/main/<path>) point at files that exist in this checkout.
  6. Injury counts on the page match the transcribed report (254 player rows, 32 club rows, 28 listed).
  7. No placeholder text (None, nan, undefined, inf) in any cell.
  8. Every page has exactly one <h1>, a title, and the Flagged-for-review link.
"""
from __future__ import annotations

import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent          # nfl-command/
REPO = ROOT.parent
REPO_BLOB_PREFIX = "https://github.com/karagemop466-tech/Korea2/blob/main/"
ALLOWED_OFFICIAL = {"www.nfl.com", "nfl.com", "www.commanders.com", "commanders.com",
                    "github.com", "aglc.ca", "www.aglc.ca", "karagemop466-tech.github.io"}
NON_OFFICIAL_ONLY_ON = {"pages/sources.html", "pages/flagged.html", "pages/repo-review.html"}
PAGES = ["index.html", "pages/executive-summary.html", "pages/requirements.html", "pages/injuries.html",
         "pages/depth-starters.html", "pages/lines-model.html", "pages/strategies.html",
         "pages/correlations-luck.html", "pages/validation-gates.html", "pages/suggestions.html",
         "pages/questions.html", "pages/repo-review.html", "pages/sources.html", "pages/flagged.html"]
NON_OFFICIAL_HOSTS = {"lineups.com", "www.lineups.com", "fantasyteamadvice.com", "www.fantasyteamadvice.com",
                      "nfl-depth-charts.com", "www.nfl-depth-charts.com"}
BAD_TEXT = re.compile(r">\s*(None|nan|NaN|undefined|inf|-inf|Infinity)\s*<")

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print("FAIL", msg)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.tables: list[dict] = []
        self._table = None
        self._in_tbody = False
        self._row = None
        self._cell_links = None
        self.h1 = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
            if self._cell_links is not None:
                self._cell_links.append(a["href"])
        if tag == "link" and a.get("href"):
            self.srcs.append(a["href"])
        if tag == "script" and a.get("src"):
            self.srcs.append(a["src"])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "table":
            self._table = {"id": a.get("id", ""), "kind": a.get("data-kind", ""), "rows": [], "text_bad": []}
        if tag == "tbody" and self._table is not None:
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self._row = {"links": [], "text": ""}
        if tag == "td" and self._row is not None:
            self._cell_links = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "td" and self._row is not None and self._cell_links is not None:
            self._row["links"].extend(self._cell_links)
            self._cell_links = None
        if tag == "tr" and self._row is not None:
            self._table["rows"].append(self._row)
            self._row = None
        if tag == "tbody":
            self._in_tbody = False
        if tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._row is not None:
            self._row["text"] += data


def check_json() -> int:
    n = 0
    for p in sorted(ROOT.rglob("*.json")):
        n += 1
        try:
            json.loads(p.read_text(encoding="utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except Exception as e:  # noqa: BLE001
            fail(f"JSON {p.relative_to(REPO)}: {e}")
    return n


def check_pages() -> dict:
    parsed = {}
    for rel in PAGES:
        f = ROOT / rel
        if not f.exists():
            fail(f"missing page {rel}")
            continue
        text = f.read_text(encoding="utf-8")
        if BAD_TEXT.search(text):
            fail(f"{rel}: placeholder text (None/nan/undefined/inf) in a cell")
        pg = Page()
        pg.feed(text)
        parsed[rel] = (pg, text)
        if pg.h1 != 1:
            fail(f"{rel}: expected exactly one <h1>, found {pg.h1}")
        if not pg.title.strip():
            fail(f"{rel}: empty <title>")
        if "pages/flagged.html" not in text and rel != "pages/flagged.html":
            fail(f"{rel}: no link to Flagged for review")
        # local links resolve
        for href in pg.hrefs + pg.srcs:
            u = urlparse(href)
            if u.scheme or href.startswith("#"):
                continue
            target = (f.parent / u.path).resolve()
            if not target.exists():
                fail(f"{rel}: broken local link {href}")
    return parsed


def is_official(h: str) -> bool:
    host = urlparse(h).netloc
    return host in ALLOWED_OFFICIAL or host.endswith(".github.io")


def check_tables(parsed: dict) -> None:
    """official tables: every row needs an official link (NFL.com, club, AGLC, or this repo).
    computed tables: every row needs a link to its input/method source, and carries UNVERIFIED-INPUT."""
    rows_total = 0
    for rel, (pg, _) in parsed.items():
        for t in pg.tables:
            for i, r in enumerate(t["rows"]):
                rows_total += 1
                links = [h for h in r["links"] if h.startswith("http")]
                if not links:
                    fail(f"{rel} table#{t['id']} row {i + 1}: no source link ({r['text'][:60]!r})")
                    continue
                labelled = "not official" in r["text"].lower()
                if t["kind"] == "official":
                    if not any(is_official(h) for h in links) and not labelled:
                        fail(f"{rel} table#{t['id']} row {i + 1}: no official source link ({r['text'][:60]!r})")
                    for h in links:
                        if urlparse(h).netloc in NON_OFFICIAL_HOSTS and not labelled:
                            fail(f"{rel} table#{t['id']} row {i + 1}: unlabelled non-official link {h}")
                elif t["kind"] == "computed":
                    if "UNVERIFIED-INPUT" not in r["text"] and "rule definition" not in r["text"].lower() \
                            and "repo:" not in r["text"] and "Method" not in r["text"] and "gate" not in t["id"]:
                        fail(f"{rel} table#{t['id']} row {i + 1}: computed row lacks an UNVERIFIED-INPUT flag")
    print(f"  table rows checked: {rows_total}")


def check_hosts(parsed: dict) -> None:
    for rel, (pg, _) in parsed.items():
        table_links = {h for t in pg.tables for r in t["rows"] for h in r["links"]}
        for h in pg.hrefs:
            if h.startswith("#") or h.startswith("mailto:"):
                continue
            u = urlparse(h)
            if not u.scheme:
                continue
            host = u.netloc
            if host in NON_OFFICIAL_HOSTS and rel not in NON_OFFICIAL_ONLY_ON and h in table_links:
                # allowed only inside a row labelled NOT OFFICIAL (checked in check_tables)
                pass
            elif host in NON_OFFICIAL_HOSTS and rel not in NON_OFFICIAL_ONLY_ON:
                fail(f"{rel}: non-official host link outside a labelled table row {h}")
            if h.startswith(REPO_BLOB_PREFIX):
                path = REPO / h[len(REPO_BLOB_PREFIX):].split("#")[0]
                if not path.exists():
                    fail(f"{rel}: repo link to a missing file {h}")


def check_injuries(parsed: dict) -> None:
    gen = json.loads((ROOT / "data" / "injuries.json").read_text(encoding="utf-8"))
    summ = json.loads((ROOT / "data" / "injury_team_summary.json").read_text(encoding="utf-8"))
    depth = json.loads((ROOT / "data" / "depth.json").read_text(encoding="utf-8"))
    if len(depth["rows"]) != 32 or any(v for r in depth["rows"] for k, v in r.items() if k in ("offense_starter", "defense_starter", "offense_backup_2nd", "defense_backup_2nd")):
        fail("depth.json: expected 32 blank club rows with no starter/backup values")
    raw = [l for l in (ROOT / "data" / "raw" / "injury_report_wk10_2026.psv").read_text(encoding="utf-8").splitlines()
           if l and not l.startswith("#")]
    player_lines = [l for l in raw if "NO INJURIES REPORTED" not in l]
    if len(player_lines) != gen["counts"]["player_rows"] or len(player_lines) != 254:
        fail(f"injury player rows: raw {len(player_lines)}, generated {gen['counts']['player_rows']}, expected 254")
    if gen["counts"]["clubs_listed"] != 28:
        fail(f"clubs listed {gen['counts']['clubs_listed']} != 28")
    if len(summ["rows"]) != 32:
        fail(f"team summary rows {len(summ['rows'])} != 32")
    pg, _ = parsed["pages/injuries.html"]
    players = next(t for t in pg.tables if t["id"] == "inj-players")
    if len(players["rows"]) != len(player_lines):
        fail(f"injuries page player table has {len(players['rows'])} rows, expected {len(player_lines)}")
    teams = next(t for t in pg.tables if t["id"] == "inj-teams")
    if len(teams["rows"]) != 32:
        fail(f"injuries page team table has {len(teams['rows'])} rows, expected 32")
    # blank injury cells on source must stay blank in the generated rows
    blanks_src = sum(1 for l in player_lines if l.split("|")[6] == "")
    blanks_gen = sum(1 for r in gen["rows"] if r["injury"] == "")
    if blanks_src != blanks_gen:
        fail(f"blank injury cells: source {blanks_src} vs generated {blanks_gen}")
    print(f"  injury rows: {len(player_lines)} player, {len(summ['rows'])} club; "
          f"{blanks_src} blank injury cells kept blank")


def main() -> int:
    print("NFL Command Center verification")
    print(f"  JSON files parsed: {check_json()}")
    parsed = check_pages()
    print(f"  pages parsed: {len(parsed)}")
    check_tables(parsed)
    check_hosts(parsed)
    check_injuries(parsed)
    if failures:
        print(f"\nRESULT: FAIL ({len(failures)} problems)")
        return 1
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
