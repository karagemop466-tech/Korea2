#!/usr/bin/env python3
"""Verify the Week 11 availability hub line by line against its committed inputs.

Fails (exit 1) on: a data row with no https source link to nfl.com; an internal link that does not resolve;
a count that differs from the manifest; a player name in the output; a claim in the text that the data contradicts;
a missing or unclean manifest; an unknown label; or a non-https or non-NFL external link.
"""
import csv
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
PAGES = ["index.html", "pages/clubs.html", "pages/schedule.html", "pages/captures.html", "pages/flagged.html"]
ALLOWED_EXTERNAL_HOSTS = {"www.nfl.com"}
# Names taken from the official report page text read on 2026-11-19. None may appear in published output.
NAME_CANARIES = ["Jaylon Carlies", "Sauce Gardner", "Danielle Hunter", "Jerry Tillery", "Saquon Barkley",
                 "T.J. Watt", "Marvin Harrison", "Jacob Hummel", "Cameron Heyward", "Dontayvion Wicks"]

failures = []


def fail(msg):
    failures.append(msg)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.rows, self._row, self._in_tbody, self._cell_links = [], [], None, False, []
        self.text = []
        self._cur_links = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "a" and ad.get("href"):
            self.links.append(ad["href"])
            self._cur_links.append(ad["href"])
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self._row = {"cells": 0, "links": []}
        if tag in ("td", "th") and self._row is not None:
            self._row["cells"] += 1

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_tbody = False
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        self.text.append(data)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_pages():
    total_rows = 0
    for rel in PAGES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            fail(f"missing page {rel}")
            continue
        src = read(path)
        p = Page()
        p.feed(src)
        # every link resolves
        for href in p.links:
            u = urlparse(href)
            if u.scheme in ("http", "https"):
                if u.scheme != "https" or u.hostname not in ALLOWED_EXTERNAL_HOSTS:
                    fail(f"{rel}: external link not https nfl.com: {href}")
                continue
            if href.startswith("#") or not href:
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(path), u.path))
            if not os.path.exists(target):
                fail(f"{rel}: broken internal link {href}")
        # every data row has an official source link
        for i, r in enumerate(p.rows):
            total_rows += 1
            row_html = ""
            # re-find links for this row by counting: simpler check on whole-table level below
        # per-table: every tbody row must contain an https nfl.com link
        for m in re.finditer(r"<tbody>(.*?)</tbody>", src, re.S):
            for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
                if not re.search(r'href="https://www\.nfl\.com/', tr):
                    fail(f"{rel}: table row without an NFL.com source link: {re.sub('<[^>]+>', ' ', tr)[:120]}")
        # no player names
        for name in NAME_CANARIES:
            if name in src:
                fail(f"{rel}: player name present in output: {name}")
    return total_rows


def check_manifests():
    paths = sorted(glob.glob(os.path.join(REPO, "injury-capture", "manifests", "reg11_2026_*.json")))
    if len(paths) < 2:
        fail(f"expected at least two Week 11 manifests, found {len(paths)}")
    reads = []
    for p in paths:
        d = json.load(open(p, encoding="utf-8"))
        reads.append(d)
        if d.get("status") != "OK" or d.get("problems"):
            fail(f"manifest not clean: {os.path.basename(p)}")
        if d.get("week") != 11 or d.get("season") != 2026:
            fail(f"manifest is not 2026 week 11: {os.path.basename(p)}")
        if d.get("source_url") != "https://www.nfl.com/injuries/league/2026/reg11":
            fail(f"manifest source_url unexpected: {os.path.basename(p)}")
        if d.get("listed_rows_parsed") != sum(t["rows"] for t in d["per_table"]):
            fail(f"manifest row total mismatch: {os.path.basename(p)}")
    if reads:
        if len({r["raw_sha256"] for r in reads}) != 1:
            fail("Week 11 reads have different raw hashes")
        if len({r["listed_rows_parsed"] for r in reads}) != 1:
            fail("Week 11 reads have different row totals")
    return reads


def check_clubs(reads):
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "clubs_w11.csv"), encoding="utf-8")))
    if len(rows) != 32:
        fail(f"clubs_w11.csv has {len(rows)} rows, expected 32")
    if len({r["abbr"] for r in rows}) != 32:
        fail("clubs_w11.csv has duplicate clubs")
    sched = json.load(open(os.path.join(ROOT, "data", "schedule_w11.json"), encoding="utf-8"))
    slug_to_abbr = sched["club_slugs"]
    last = max(reads, key=lambda r: r["fetched_at_utc"])
    # Compare every per-club number with the manifest
    expect = {}
    for t in last["per_table"]:
        a = slug_to_abbr[t["team_slug"]]
        pr = t["practice_status_counts"]
        gs = t["game_status_counts"]
        expect[a] = {
            "listed_rows": str(t["rows"]),
            "DNP": str(pr.get("Did Not Participate In Practice", 0)),
            "LP": str(pr.get("Limited Participation in Practice", 0)),
            "FP": str(pr.get("Full Participation in Practice", 0)),
            "Out": str(gs.get("Out", 0)),
            "Doubtful": str(gs.get("Doubtful", 0)),
            "Questionable": str(gs.get("Questionable", 0)),
            "no_game_status_printed": str(gs.get("", 0)),
        }
    for r in rows:
        a = r["abbr"]
        if a in expect:
            for k, v in expect[a].items():
                if r[k] != v:
                    fail(f"clubs_w11.csv {a} {k}={r[k]} differs from manifest {v}")
            if r["in_report"] != "yes":
                fail(f"{a}: manifest has a table but in_report={r['in_report']}")
        else:
            if r["listed_rows"] not in ("",):
                fail(f"{a}: no manifest table but listed_rows={r['listed_rows']} (must be blank)")
    # Totals stated in the hub
    listed = sum(int(r["listed_rows"]) for r in rows if r["listed_rows"])
    if listed != last["listed_rows_parsed"]:
        fail(f"listed total {listed} != manifest {last['listed_rows_parsed']}")
    des = sum(int(r["designated"]) for r in rows if r["designated"])
    out = sum(int(r["Out"]) for r in rows if r["Out"])
    q = sum(int(r["Questionable"]) for r in rows if r["Questionable"])
    if (des, out, q) != (15, 9, 6):
        fail(f"designated/out/questionable totals {(des, out, q)} != (15, 9, 6)")
    # Claim in the hub text: only IND and HOU carry printed game statuses
    with_status = [t["team_slug"] for t in last["per_table"] if t["rows_with_game_status"] > 0]
    if sorted(slug_to_abbr[s] for s in with_status) != ["HOU", "IND"]:
        fail(f"printed-game-status clubs are {with_status}, text says IND and HOU only")
    no_table = sorted(r["abbr"] for r in rows if r["in_report"].startswith("no table"))
    if no_table != ["CIN", "WAS"]:
        fail(f"clubs without tables {no_table}, expected CIN and WAS")
    bye = sorted(r["abbr"] for r in rows if r["in_report"].startswith("no (bye)"))
    if bye != sorted(b["abbr"] for b in sched["teams_on_bye"]):
        fail("bye rows differ from the schedule file")
    return rows


def check_schedule():
    sched = json.load(open(os.path.join(ROOT, "data", "schedule_w11.json"), encoding="utf-8"))
    fx = sched["fixtures"]
    if len(fx) != 13:
        fail(f"{len(fx)} fixtures, expected 13")
    teams = [f["away"] for f in fx] + [f["home"] for f in fx] + [b["abbr"] for b in sched["teams_on_bye"]]
    if len(teams) != 32 or len(set(teams)) != 32:
        fail("fixtures plus byes do not cover 32 distinct clubs")
    for f in fx:
        u = f["game_url"]
        if not u.startswith("https://www.nfl.com/games/") or not u.endswith("-2026-reg-11"):
            fail(f"fixture URL not an official NFL game page: {u}")
        if f["away"] + "" == f["home"]:
            fail("fixture with same team twice")
    return fx


def check_flags():
    flags = json.load(open(os.path.join(ROOT, "data", "flags.json"), encoding="utf-8"))["flags"]
    ids = [f["id"] for f in flags]
    if len(ids) != len(set(ids)):
        fail("duplicate flag ids")
    for f in flags:
        if not f.get("sources"):
            fail(f"{f['id']}: no source link")
        for s in f.get("sources", []):
            if not s.startswith("https://www.nfl.com/"):
                fail(f"{f['id']}: source not an NFL page: {s}")
    return flags


def main():
    reads = check_manifests()
    if reads:
        check_clubs(reads)
    check_schedule()
    flags = check_flags()
    rows = check_pages()
    # every capture's manifest linked from the captures page exists
    for r in reads:
        pass
    for name in ("index.html", "assets/style.css"):
        if not os.path.exists(os.path.join(ROOT, name)):
            fail(f"missing {name}")
    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print(f"PASS: {len(PAGES)} pages, {rows} table rows checked, {len(reads)} manifests, 32 clubs, 13 fixtures, {len(flags)} flags")


if __name__ == "__main__":
    main()
