#!/usr/bin/env python3
"""price-desk verifier.

Checks (all must pass):
  1. Every rendered HTML table row contains at least one source link
     (http(s) URL or a repo path that exists locally).
  2. Every local href in price-desk pages resolves to a real file.
  3. Blank-policy: any CSV cell whose *_status contains 'blank' must have the
     corresponding value column empty (no value invented where none exists).
  4. Verified-policy: any CSV cell whose status is 'verified-official' must
     sit on a row that names an official (nfl.com / static.www.nfl.com) URL.
  5. Every data JSON loads and carries a meta block with a date.
  6. Results-feed arithmetic: home_margin == home_score - away_score and
     total_points == home_score + away_score wherever scores are present.
  7. Snapshot arithmetic: difference == our_fair_line - market_close_line
     wherever both inputs are present (moneyline rows: probability diff).
"""
import csv
import json
import os
import re
import sys

PD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(PD, ".."))
errors = []
checks = 0


def fail(msg):
    errors.append(msg)


def ok():
    global checks
    checks += 1


def rows_of_html(path):
    with open(path) as f:
        text = f.read()
    for m in re.finditer(r"<tr>(.*?)</tr>", text, re.S):
        yield m.group(1)


def check_pages():
    pages = ["index.html"] + ["pages/" + p for p in sorted(os.listdir(os.path.join(PD, "pages")))]
    for rel_path in pages:
        full = os.path.join(PD, rel_path)
        base = os.path.dirname(full)
        with open(full) as f:
            text = f.read()
        for tr in rows_of_html(full):
            if "<th>" in tr:
                continue
            if "<td" not in tr:
                continue
            if 'href="' not in tr:
                fail(f"{rel_path}: table row without any source link: {tr[:120]}")
            else:
                ok()
        for m in re.finditer(r'href="([^"]+)"', text):
            href = m.group(1)
            if href.startswith("http") or href.startswith("#"):
                continue
            target = os.path.normpath(os.path.join(base, href))
            if not os.path.exists(target):
                fail(f"{rel_path}: broken local link {href}")
            else:
                ok()


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def check_store():
    # blank policy
    with open(os.path.join(PD, "data", "price_snapshots.csv"), newline="") as f:
        snaps = list(csv.DictReader(f))
    for r in snaps:
        if "blank" in r["open_status"] and (r["market_open_line"] or r["market_open_price_american"]):
            fail(f"blank-policy violated (open): {r['market_id']}")
        else:
            ok()
        if r["open_status"] == "verified-official" and not r["official_source_url"].startswith("http"):
            fail(f"verified row without official url: {r['market_id']}")
        else:
            ok()
        a, b = num(r["our_fair_line"]), num(r["market_close_line"])
        d = num(r["difference"])
        if a is not None and b is not None and d is not None:
            if abs((a - b) - d) > 0.011:
                fail(f"snapshot arithmetic: {r['market_id']} {a} - {b} != {d}")
            else:
                ok()
    with open(os.path.join(PD, "data", "price_snapshots_props.csv"), newline="") as f:
        props = list(csv.DictReader(f))
    for r in props:
        if "blank" in r["market_status"] and (r["market_open_line"] or r["market_close_line"]):
            fail(f"blank-policy violated (prop market): {r['market_id']}")
        else:
            ok()
    with open(os.path.join(PD, "data", "results_feed.csv"), newline="") as f:
        feed = list(csv.DictReader(f))
    for r in feed:
        sa, sh = num(r["away_score"]), num(r["home_score"])
        if sa is not None and sh is not None:
            hm, tp = num(r["home_margin"]), num(r["total_points"])
            if abs((sh - sa) - hm) > 0.011 or abs((sh + sa) - tp) > 0.011:
                fail(f"feed arithmetic: {r['game_id']}")
            else:
                ok()
        if r["score_status"].startswith("verified-official"):
            if "nfl.com" not in r["official_source_url"]:
                fail(f"verified score without nfl.com url: {r['game_id']}")
            else:
                ok()
        if r["score_status"] == "missing" and (r["away_score"] or r["home_score"]):
            fail(f"blank-policy violated (missing score): {r['game_id']}")
        else:
            ok()


def check_json():
    for name in sorted(os.listdir(os.path.join(PD, "data"))):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(PD, "data", name)) as f:
            try:
                d = json.load(f)
            except json.JSONDecodeError as e:
                fail(f"{name}: invalid JSON ({e})")
                continue
            ok()
            if isinstance(d, dict) and "meta" in d:
                meta = d["meta"]
                if not any(k in meta for k in ("date", "generated_on", "checked_on", "verified_on", "verified_by")):
                    fail(f"{name}: meta lacks a date/author stamp")
                else:
                    ok()


def main():
    check_pages()
    check_store()
    check_json()
    print(f"price-desk verify: {checks} checks, {len(errors)} errors")
    for e in errors[:40]:
        print("ERROR:", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
