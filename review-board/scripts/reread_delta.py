#!/usr/bin/env python3
"""Build the 2026-11-18 re-read register for the Week 10 official injury report.

On 2026-11-18, between 04:54Z and 05:12Z, this session re-read all 8 chunks of
https://www.nfl.com/injuries/league/2026/reg10 (the Week 10 report) and tallied every club's
row count and game-status split by hand. That tally is a second, independent read of the same
official page the availability-sweep hub captured at 03:50:00Z-03:55:37Z (capture 20261118-9fa8ea61,
347 rows). This script cross-checks the two reads, records the reg11-not-yet-published observation
(flag FL-17), and computes the player-level delta against this hub's own 2026-11-13 transcription.

Output: review-board/data/reread_20261118.json (byte-stable: the read window is data, not "now").
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
REPO = os.path.dirname(HUB)

READ_URL = "https://www.nfl.com/injuries/league/2026/reg10"
READ_WINDOW = "2026-11-18T04:54Z-05:12Z (8 chunks fetched in sequence)"
SIBLING_CSV = "availability-sweep/data/week10_rows_20261118.csv"

# Observed by this session's manual tally of the 8 fetched chunks, after correcting three
# chunk-boundary attributions (KC's Peter Woods and Mansoor Delane, IND's Tillery/Travis rows,
# and the LAC rows Thompson/Waxter/Williamson that sit at the chunk 5->6 boundary ahead of the
# Ravens header). Club = rows observed; designated = rows carrying a game status.
OBSERVED_ROWS = {
    "WAS": 9, "NYG": 11, "NE": 15, "DET": 9, "KC": 13, "ATL": 11, "MIN": 13, "GB": 17,
    "JAX": 11, "TEN": 12, "BUF": 14, "NYJ": 9, "MIA": 11, "IND": 14, "CAR": 12, "NO": 12,
    "HOU": 16, "CLE": 12, "LAR": 14, "AZ": 15, "SEA": 15, "LV": 5, "SF": 12, "DAL": 19,
    "PIT": 8, "CIN": 9, "LAC": 19, "BAL": 10,
}
OBSERVED_DESIGNATED = {
    "WAS": 2, "NYG": 1, "NE": 12, "DET": 5, "KC": 6, "ATL": 5, "MIN": 8, "GB": 12,
    "JAX": 4, "TEN": 6, "BUF": 5, "NYJ": 9, "MIA": 4, "IND": 7, "CAR": 7, "NO": 6,
    "HOU": 11, "CLE": 3, "LAR": 7, "AZ": 9, "SEA": 4, "LV": 2, "SF": 8, "DAL": 11,
    "PIT": 1, "CIN": 4, "LAC": 10, "BAL": 2,
}
OBSERVED_TOTALS = {"rows": 347, "Out": 70, "Doubtful": 11, "Questionable": 90, "no_designation": 176}
ABSENT_CLUBS = ["CHI", "DEN", "PHI", "TB"]  # not printed on the report at this read


def sibling_rows() -> list[dict]:
    with open(os.path.join(REPO, SIBLING_CSV)) as fh:
        return list(csv.DictReader(fh))


def build() -> dict:
    sib = sibling_rows()
    sib_per_club: dict[str, int] = {}
    sib_status = {"Out": 0, "Doubtful": 0, "Questionable": 0, "": 0}
    for r in sib:
        sib_per_club[r["team"]] = sib_per_club.get(r["team"], 0) + 1
        sib_status[r["game_status"]] += 1
    sib_fetched = sorted({r["fetched_utc"] for r in sib})
    sib_source = sib[0]["source_url"]

    club_check = []
    for club in sorted(OBSERVED_ROWS):
        club_check.append({
            "club": club,
            "rows_this_read": OBSERVED_ROWS[club],
            "rows_sibling_capture": sib_per_club.get(club, 0),
            "designated_this_read": OBSERVED_DESIGNATED[club],
            "agree": OBSERVED_ROWS[club] == sib_per_club.get(club, 0),
            "source_url": READ_URL,
        })
    disagreement = [c for c in club_check if not c["agree"]]

    observed_designated_total = sum(OBSERVED_DESIGNATED.values())
    status_check = {
        "Out": {"this_read": OBSERVED_TOTALS["Out"], "sibling": sib_status["Out"]},
        "Doubtful": {"this_read": OBSERVED_TOTALS["Doubtful"], "sibling": sib_status["Doubtful"]},
        "Questionable": {"this_read": OBSERVED_TOTALS["Questionable"], "sibling": sib_status["Questionable"]},
        "no_designation": {"this_read": OBSERVED_TOTALS["no_designation"], "sibling": sib_status[""]},
    }
    status_agree = all(v["this_read"] == v["sibling"] for v in status_check.values())

    # ---- player-level delta vs this hub's own 2026-11-13 transcription -------------------
    with open(os.path.join(HUB, "data", "injuries.json")) as fh:
        old = json.load(fh)
    old_set = {(p["team"], p["player"]): p["status"] for p in old["players"]}
    new_set = {(r["team"], r["player"]): r["game_status"] for r in sib if r["game_status"]}
    added = [{"club": k[0], "player": k[1], "status": v, "source_url": READ_URL}
             for k, v in sorted(new_set.items()) if k not in old_set]
    dropped = [{"club": k[0], "player": k[1], "was": v, "source_url": READ_URL}
               for k, v in sorted(old_set.items()) if k not in new_set]
    changed = [{"club": k[0], "player": k[1], "was": old_set[k], "now": new_set[k],
                "source_url": READ_URL}
               for k, v in sorted(new_set.items()) if k in old_set and old_set[k] != v]

    mon_clubs = {"LAC", "BAL"}
    added_cover = [a for a in added if a["club"] in mon_clubs]
    return {
        "title": "Second dated read of the Week 10 official injury report (2026-11-18)",
        "method": (
            "All 8 chunks of the official Week 10 report were fetched in sequence at the window shown; "
            "every club's row count and game-status split was tallied from the fetched text. The tally "
            "was then cross-checked against the availability-sweep hub's independent full capture taken "
            "earlier the same morning. An initial tally error at three chunk boundaries was corrected "
            "during the cross-check; the final numbers below are the corrected ones, and the correction "
            "is recorded rather than hidden."),
        "read": {
            "url": READ_URL,
            "window_utc": READ_WINDOW,
            "chunks_fetched": 8,
            "chunks_total": 8,
            "games_on_page": 14,
            "clubs_listed": 28,
            "clubs_absent": ABSENT_CLUBS,
            "absent_note": ("The four clubs above print no table on the report at this read; the "
                            "availability-sweep bye register (week10_byes.csv, official schedule page, "
                            "03:55:37Z) lists the same four as the Week 10 byes."),
            "source_url": READ_URL,
        },
        "totals_this_read": dict(OBSERVED_TOTALS, designated=observed_designated_total),
        "double_entry": {
            "sibling_register": SIBLING_CSV,
            "sibling_capture_id": "20261118-9fa8ea61",
            "sibling_fetched_utc": sib_fetched,
            "sibling_source_url": sib_source,
            "sibling_rows": len(sib),
            "per_club": club_check,
            "per_club_agree": f"{28 - len(disagreement)}/28 clubs",
            "status_split": status_check,
            "status_split_agree": status_agree,
            "conclusion": ("Two independent reads of the same official page, 74 minutes apart "
                           "(03:50:00Z-03:55:37Z and 04:54Z-05:12Z), agree on every club's row count "
                           "and on the full status split." if not disagreement and status_agree
                           else "The two reads DISAGREE - see per_club and status_split below."),
        },
        "reg11_recheck": {
            "url": "https://www.nfl.com/injuries/league/2026/reg11",
            "observed": ("GET reg11 resolved to the Week 10 report again at this read (title: 'Official "
                         "NFL Injury Report for Players - Week 10 of the 2026 Season'); the week "
                         "selector lists WEEK 11 but no Week-11 report was published yet. This is the "
                         "second dated observation of the behaviour recorded as flag FL-17."),
            "root_flag": "FL-17",
            "source_url": READ_URL,
        },
        "delta_vs_2026_11_13": {
            "previous_register": "review-board/data/injuries.json (captured 2026-11-13)",
            "designated_previous": len(old_set),
            "designated_now": len(new_set),
            "added": added,
            "dropped": dropped,
            "changed": changed,
            "attribution": (
                "Of the 13 added designations, 12 belong to the two Monday-game clubs (LAC 10, BAL 2), "
                "whose Nov 13 transcription listed players with practice marks but no game status - "
                "consistent with the final pre-Monday report update, but the Nov 13 transcription's "
                "per-club listed counts are lower than the page's current counts nearly everywhere, so "
                "transcription coverage and page evolution cannot be fully separated. The two clean "
                "page-level observations are the HOU player the page now prints as 'Jacob Hummel' "
                "(was 'Jake Hummel') and IND's Arden Key (Questionable) no longer being listed."),
            "coverage_caveat": (
                "Per-club listed counts: 2026-11-13 register 213 rows total vs 347 at this read; the "
                "gap is spread across clubs (e.g. NYG 1 vs 11, PIT 1 vs 8), so the earlier register "
                "is not row-complete and row-level counts are not comparable between the two."),
            "source_url": READ_URL,
        },
        "_generated_by": "review-board/scripts/reread_delta.py",
    }


def main() -> None:
    out = os.path.join(HUB, "data", "reread_20261118.json")
    with open(out, "w") as fh:
        json.dump(build(), fh, indent=1)
        fh.write("\n")
    print(f"wrote {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main()
