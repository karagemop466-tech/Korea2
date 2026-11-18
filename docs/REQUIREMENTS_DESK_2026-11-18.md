# Requirements Desk — dated record, 2026-11-18

Session `arena/2ca76106-korea2`. This document records exactly what was retrieved, what was
computed from it, what was verified, and what could not be established. It is the audit trail for
the [`requirements-desk/`](../requirements-desk/index.html) hub.

## 1. Scope of the capture

All four pages below were opened with the session's page-retrieval tool at **2026-11-18T03:52Z**.

| Source | URL | Chunks read | Register produced |
|---|---|---|---|
| Week 10 2026 injury report | https://www.nfl.com/injuries/league/2026/REG10 | 8 | `injury_report_2026_w10.csv`, 347 rows |
| Week 10 2026 schedule | https://www.nfl.com/schedules/2026/by-week/week-10 | 2 | `results_2026_w10.csv`, 14 rows; `absent_clubs_2026_w10.csv`, 4 rows |
| Week 11 2026 schedule | https://www.nfl.com/schedules/2026/by-week/week-11 | 3 | `schedule_2026_w11.csv`, 13 rows |
| 2026 division standings | https://www.nfl.com/standings/division/2026/REG | 2 | `standings_2026.csv`, 32 rows |

A fifth register, `injury_page_news_2026.csv` (20 rows), records the dated NFL.com news headlines the
injury-report page itself links. They are recorded as headlines only and populate no computed column.

**Capture limitation, stated first.** The sandbox shell has no network route to nfl.com; only the
page-retrieval tool could read it. No raw HTTP response body could therefore be retained. The SHA-256
values in `capture_manifest.json` cover the canonical register rows as written to CSV, not the NFL
response bytes. Published as flag F-01 on the hub's Flagged page.

**Week 11 report not available.** At 03:52 UTC on 2026-11-18 the canonical NFL.com injury page still
displayed Week 10. The latest official report captured is therefore Week 10, which is post-kickoff.
Published as flag F-02.

## 2. Transcription rules applied

1. A blank cell on the official page is stored as an empty string and rendered as an explicit blank.
2. Practice status and game status are reproduced verbatim, including "Not injury related - resting player"
   and "Not injury related - personal matter" in the injury column.
3. Club abbreviations are the ones the official page prints beside each table.
4. Where the page prints no table for a club, no row is invented. The club is recorded in
   `absent_clubs_2026_w10.csv` with the reason the source gives.
5. No value is derived from a third-party feed, and nothing is inferred from jersey number, experience,
   salary or roster order.

## 3. Findings

### 3.1 Row counts

The Week 10 report contains **347 listed-player rows across 28 club tables**, with no club table left
empty. Two figures quoted earlier in the project brief — 254 rows and 279 rows — do not reproduce.
The 347 figure is a complete transcription, not a sample or an estimate.

**171 of 347 rows carry a game designation** (Questionable 90, Out 70, Doubtful 11); 176 are blank.
This supersedes the brief's statement that only 6 rows carry a designation.

### 3.2 Specific claims from the brief

| Claim | Verdict | Detail |
|---|---|---|
| VR-08 / VR-12 — Kerby Joseph, Cade Mays and D.J. Reed are blank but should read Out | **Confirmed** | All three read Out on the captured page (knee, ankle, hip respectively). |
| VR-05 — Seattle lists 15 players | **Confirmed** | 15 rows in the Seattle table. |
| VR-06 — Cincinnati lists 4 players | **Not confirmed** | 9 rows. 4 of them carry a game status. |
| VR-04 / VR-07 — 254 rows / 279 rows, and 2 or 4 no-injury sections | **Neither reproduced** | 347 rows; 0 club tables without rows. |
| "Only 6 of 254 rows carry a game designation" | **Out of date** | 171 of 347. |
| VR-25 / VQ-06 — Malik Willis absent because he is on IR | **Absence confirmed; reason not from this page** | Not in the Miami table. The report does not state IR status; the IR context comes from a linked NFL.com news headline, recorded as a headline only. |
| VR-17 / VR-26 / VQ-07 — Lamar Jackson absent, moved to IR | **Absence confirmed; reason not from this page** | Not in the Baltimore table. Same sourcing caveat. |
| F-W10-6 (prior session) — CHI, DEN, PHI, TB absent; bye unverified | **Resolved** | The official Week 10 schedule page lists all four under "Teams on Bye". |
| VR-21 / VR-23 / VQ-08 — shared and empty depth slots | **Not testable on this source** | The injury report publishes no depth chart and no depth slots. |

### 3.3 Statistics computed from the official registers

**Correlations** — all at n=32, 95% intervals by Fisher z-transform:

| Pair | r | 95% CI | n |
|---|---|---|---|
| Win pct vs points for | +0.657 | [+0.400, +0.818] | 32 |
| Win pct vs points against | −0.670 | [−0.826, −0.419] | 32 |
| Win pct vs net points | +0.875 | [+0.758, +0.938] | 32 |
| Win pct vs Pythagorean expected wins | +0.872 | [+0.752, +0.936] | 32 |

These are team-standings relationships. They are not player-prop, injury or parlay-leg correlations and
must not be transferred to those uses.

**Luck panel** — computed from the official points-for and points-against columns only. Pythagorean
exponent 2.65 is a stated assumption, not an NFL figure. Luck standard deviation across the 32 clubs is
**1.076 wins**. Whether luck persists from season to season is **not** tested; one season cannot answer it.

**Week 10 results** — 14 of 14 games printed FINAL with both scores. Home teams won 8 of 14 decided games.
Mean total 45.9 (median 46.0, range 28 to 86). Mean absolute margin 12.9.

**Week 11 fixtures** — 13 games; 6 clubs on bye (ATL, CLE, GB, LAR, NE, SEA); 1 neutral-site game
(Vikings-49ers, labelled Mexico City on the official page).

## 4. Requirement register

74 requirements, grouped in eight categories. Each row records a status, the gate that blocks it, and a
clearance condition written as a countable threshold.

| Status | Count | Meaning |
|---|---|---|
| Verified | 13 | A published value is confirmed against an official source. |
| Partial | 36 | Structure built; values blank or flagged per the blank policy. |
| Blocked | 17 | Impossible without information that does not exist yet. |
| Not started | 8 | No structure exists in the repository. |

## 5. What is deliberately blank

| Column / value | Why |
|---|---|
| Replacement named (all clubs) | The injury report does not name replacements. |
| Replacement string tier (all clubs) | No official source ranks depth. Jersey order, experience and salary are explicitly rejected. |
| Starters out (all clubs) | The report does not identify starters; inferring them is forbidden by the brief. |
| Player-prop and parlay-leg correlations | No official joint distribution has been captured. |
| Closing-line value, market residual, price ROI | No official opening or closing price archive. The strict official-only store has 0 rows. |
| Designation play rates | No official inactives list has been captured. |
| Roof, surface, wind, precipitation | Not published on the schedule page; the NWS and stadium-roof captures do not exist. |

## 6. Verification performed

| Command | Result |
|---|---|
| `python3 requirements-desk/scripts/verify.py` | **pass** — 14 pages, 24 tables, 1,052 links, 74 requirements, 6 registers |
| `python3 tests/check_site.py` | **pass** — 246 pages, 608 tables, 14,612 links |
| `python3 scripts/check_links.py` | **pass** — 5,072 local references, no broken internal links |
| `python3 requirements-desk/scripts/official_capture.py` | 347 / 14 / 13 / 32 / 4 / 20 rows written, hashes recorded |
| `python3 requirements-desk/scripts/analyze.py` | 4 correlations, luck panel, results and fixture panels |
| `python3 requirements-desk/scripts/build_site.py` | 14 pages regenerated deterministically |

The hub verifier enforces, and fails on:

1. a page with no `<title>`;
2. a broken internal link, asset or in-page anchor;
3. any `<tr>` inside a `<tbody>` without a source link;
4. an external link that is not https;
5. a register whose row count disagrees with the committed CSV or the manifest;
6. a register missing a SHA-256 or an https source URL;
7. a requirement row missing a status, gate or clearance condition;
8. a duplicate requirement id or an unrecognised status or category.

## 7. Honest limits of this session

- One capture, not a series. A surprise term, a weekly diff and a designation-reliability study all need
  at least two captures in the same week, and this session produced one.
- No raw bytes, therefore no byte-level immutability claim.
- Week 10 results only. The pre-registered 136-game corpus needs official results for every game in its
  window; Weeks 1 to 6 remain uncaptured.
- No price of any kind, so nothing in this hub computes CLV, residual or ROI.
- No depth, inactives or snap counts, so no availability feature is built and no ablation is run.

All of the above are published on the hub's
[Flagged for review](../requirements-desk/pages/flagged.html) page with source links.
