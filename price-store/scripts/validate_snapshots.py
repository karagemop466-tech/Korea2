"""Validate price-store/data/snapshots.csv and price-store/data/results_feed.csv.

Exit status 0 = every rule passes. Exit status 1 = at least one rule fails (printed).
Standard library only. Run from anywhere: python3 price-store/scripts/validate_snapshots.py
"""
import csv
import os
import re
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

OFFICIAL_DOMAINS = {"nfl.com", "www.nfl.com", "operations.nfl.com", "support.nfl.com"}
MARKET_ORDER = {"spread": "1", "total": "2", "moneyline": "3"}
SNAP_COLS = ["snapshot_id", "game_id", "market", "side", "timing", "origination_order",
             "captured_utc", "book", "line", "price_american", "source_url", "verified",
             "verified_on", "note"]
RES_COLS = ["game_id", "season", "week", "game_date", "away_team", "away_score", "home_team",
            "home_score", "status", "source_url", "second_source_url", "verified", "verified_on",
            "nflverse_committed_snapshot", "note"]
GAME_ID = re.compile(r"^(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def official_https(url):
    p = urlparse(url)
    return p.scheme == "https" and p.netloc in OFFICIAL_DOMAINS


def read(name, cols):
    path = os.path.join(DATA, name)
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != cols:
            raise SystemExit(f"{name}: header mismatch: {rd.fieldnames}")
        return list(rd)


def check_snapshots(errors):
    rows = read("snapshots.csv", SNAP_COLS)
    ids = set()
    for i, r in enumerate(rows, start=2):
        where = f"snapshots.csv line {i}"
        if r["snapshot_id"] in ids:
            errors.append(f"{where}: duplicate snapshot_id")
        ids.add(r["snapshot_id"])
        if not GAME_ID.match(r["game_id"]):
            errors.append(f"{where}: bad game_id {r['game_id']!r}")
        if r["market"] not in MARKET_ORDER:
            errors.append(f"{where}: market must be spread|total|moneyline")
        elif r["origination_order"] != MARKET_ORDER[r["market"]]:
            errors.append(f"{where}: origination_order must be {MARKET_ORDER[r['market']]} for {r['market']}")
        if r["timing"] not in ("open", "close"):
            errors.append(f"{where}: timing must be open|close")
        if r["verified"] not in ("yes", "no"):
            errors.append(f"{where}: verified must be yes|no")
        if r["verified"] == "no":
            if r["line"] or r["price_american"]:
                errors.append(f"{where}: unverified row must leave line and price blank")
            if not r["note"]:
                errors.append(f"{where}: unverified row needs a note")
        else:
            if not UTC.match(r["captured_utc"]):
                errors.append(f"{where}: captured_utc must be YYYY-MM-DDTHH:MM:SSZ")
            if not official_https(r["source_url"]):
                errors.append(f"{where}: source_url must be https on an official NFL domain")
            if not DATE.match(r["verified_on"]):
                errors.append(f"{where}: verified_on must be YYYY-MM-DD")
    return len(rows)


def check_results(errors):
    rows = read("results_feed.csv", RES_COLS)
    for i, r in enumerate(rows, start=2):
        where = f"results_feed.csv line {i}"
        m = GAME_ID.match(r["game_id"])
        if not m:
            errors.append(f"{where}: bad game_id {r['game_id']!r}")
        else:
            season, week, away, home = m.groups()
            if (season, week.lstrip("0"), away, home) != (
                    r["season"], r["week"], r["away_team"], r["home_team"]):
                errors.append(f"{where}: game_id disagrees with season/week/teams")
        if r["verified"] == "yes":
            if not official_https(r["source_url"]):
                errors.append(f"{where}: source_url must be https on an official NFL domain")
            if r["second_source_url"] and not official_https(r["second_source_url"]):
                errors.append(f"{where}: second_source_url must be https on an official NFL domain")
            if r["status"] == "Final" and not (r["away_score"].isdigit() and r["home_score"].isdigit()):
                errors.append(f"{where}: Final game needs integer scores")
            if not DATE.match(r["verified_on"]):
                errors.append(f"{where}: verified_on must be YYYY-MM-DD")
        else:
            if r["away_score"] or r["home_score"]:
                errors.append(f"{where}: unverified row must leave scores blank")
    return len(rows)


def main():
    errors = []
    n_snap = check_snapshots(errors)
    n_res = check_results(errors)
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print(f"PASS: {n_snap} snapshot rows, {n_res} results rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
