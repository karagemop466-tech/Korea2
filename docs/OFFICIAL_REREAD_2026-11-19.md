# Dated official re-read — 2026-11-19 (session arena/b245e313-korea2)

**Read at:** 2026-11-19 UTC, with the session's page-retrieval tool. The sandbox shell has no
network route to nfl.com, so no raw HTTP response bytes were retained; this records what the
retrieved text said, chunk by chunk, and compares it against the committed registers. Nothing
below is inferred. Where a fetch failed, the failure is recorded.

## Sources opened

| # | URL | Result |
|---|---|---|
| 1 | https://www.nfl.com/injuries/league/2026/REG10 | 8 chunks read. Title says "Week 11"; body heading says "Injuries - WEEK 10". |
| 2 | https://www.nfl.com/injuries/league/2026/REG11 | 7 chunks read (chunk 0 in full). Title and body both say Week 11. |
| 3 | https://www.nfl.com/schedules/2026/by-week/week-10 | 2 chunks read. |
| 4 | https://www.nfl.com/schedules/2026/by-week/week-11 | 3 chunks read. |
| 5 | https://www.nfl.com/standings/division/2026/REG | 2 chunks read. |
| 6 | https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports | 1 chunk read. |
| 7 | https://www.weather.gov/documentation/services-web-api | 5 chunks (chunk 0 read). |
| 8 | https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm | 2 chunks (chunk 0 read). |
| 9 | https://www.nfl.com/legal/terms/ | 9 chunks (chunk 0 read). |
| 10 | https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/ | **Fetch failed.** No content recorded. Prior Game Book register links are unchanged. |

## Findings

### 1. Week 10 injury report (REG10) — still serves Week 10

- Body heading "Injuries - WEEK 10"; first fixture block "THURSDAY, NOVEMBER 12TH, 8:15 PM EST, Prime Video, WAS (3-5-1) vs NYG (5-3-1)".
- **Lions rows confirmed again:** Kerby Joseph (S, Knee, Did Not Participate In Practice, **Out**);
  Cade Mays (C, Ankle, Did Not Participate In Practice, **Out**); D.J. Reed (CB, Hip,
  Did Not Participate In Practice, **Out**). VR-08 / VR-12 confirmed a second time.
- **Title/body mismatch persists on REG10:** `<title>` says "Week 11 of the 2026 Season" while the
  body says WEEK 10. This is the FL-17 pattern (URL/title/body disagree). The committed register
  (347 rows, 28 club tables) is unaffected because it keys on the body, not the title.
- Linked news headlines on the page include "Sam Darnold ruled out for Seahawks' Week 10 game vs.
  Raiders; Drew Lock expected to start again" and "Ravens' Lamar Jackson (right thumb) out 6-9 weeks".
  These are headlines only; they do not populate any register column (per the blank policy).

### 2. Week 11 injury report (REG11) — now correctly serves Week 11

- Title and body both say Week 11; first block "THURSDAY, NOVEMBER 19TH, 8:15 PM EST, Prime Video,
  IND (3-7) vs HOU (3-6)".
- **FL-17 update:** the earlier observation that REG11 served the Week 10 report is no longer true.
  REG11 has rolled to Week 11. The REG10 title/body mismatch (above) remains.
- This session did **not** transcribe the Week 11 report into a register; only the first fixture
  block was read in full. No Week 11 injury rows are published from this read.

### 3. Week 10 schedule/results — 14/14 FINAL, matches the committed register

| Fixture | Score | Committed CSV |
|---|---|---|
| WAS @ NYG (Nov 12) | 24–21 | match |
| NE @ DET (Nov 15, Munich) | 10–35 | match |
| KC @ ATL | 35–13 | match |
| HOU @ CLE | 24–27 | match |
| MIN @ GB | 30–10 | match |
| MIA @ IND | 22–24 | match |
| CAR @ NO | 20–17 | match |
| BUF @ NYJ | 31–12 | match |
| JAX @ TEN | 40–23 | match |
| LAR @ AZ | 34–6 | match |
| SEA @ LV | 21–13 | match |
| SF @ DAL | 46–40 | match |
| PIT @ CIN (SNF) | 18–38 | match |
| LAC @ BAL (MNF, Nov 16) | 23–20 | match |

- **Teams on Bye (Week 10):** CHI (7-2), DEN (7-2), PHI (2-7), TB (3-6). Matches the committed
  absent-clubs register. F-W10-6 stays resolved.

### 4. Week 11 schedule — 13 fixtures, matches the committed register

- Thu Nov 19, 8:15 PM, PRIME: IND @ HOU (NRG Stadium).
- Sun Nov 22, 1:00 PM: MIA @ BUF (CBS, Highmark Stadium); BAL @ CAR (FOX, Bank of America Stadium);
  NO @ CHI (FOX, Soldier Field); TEN @ DAL (FOX, AT&T Stadium); TB @ DET (FOX, Ford Field);
  AZ @ KC (CBS, GEHA Field at Arrowhead Stadium); PIT @ PHI (CBS, Lincoln Financial Field).
- Sun Nov 22, 4:05 PM: NYJ @ LAC (FOX, SoFi Stadium). 4:25 PM: JAX @ NYG (CBS, MetLife Stadium);
  LV @ DEN (CBS, Empower Field at Mile High).
- Sun Nov 22, 8:20 PM, NBC, **Mexico City (neutral site)**: MIN @ SF.
- Mon Nov 23, 8:15 PM, ESPN: CIN @ WAS (FedEx Field).
- **Teams on Bye (Week 11):** ATL (3-7), CLE (6-4), GB (6-4), LAR (6-4), NE (5-5), SEA (6-4).
  Matches the committed register (6 clubs, 1 neutral-site game).

### 5. Standings — 32/32 match the committed register

All 32 rows (W/L/T, PCT, PF, PA, NET) match `requirements-desk/data/standings_2026.csv`, including
BUF 8-1 (287/199), SF 8-1 (281/196), DET/MIN/CHI 7-2, and AZ 3-7 (184/289). No change since the
2026-11-18 capture; the luck panel and official correlations (n=32) remain computed from these values.

### 6. Genius Sports — price-data policy blocker confirmed

The NFL.com announcement states Genius Sports "will remain the NFL's exclusive distributor of
real-time, official play-by-play statistics, proprietary Next Gen Stats (NGS) data and the NFL's
official sports betting data feed", through the end of the 2027-28 season, and "powers over 98% of
the legalized U.S. sports betting market with official NFL data". There is no official open/close
price archive on nfl.com. R01–R06 stay blocked/partial until a permitted feed is approved in writing.

### 7. NWS API — weather overlay route exists, not yet captured

The NWS API Web Service page documents open data at https://api.weather.gov (JSON-LD, free to use,
rate-limited, User-Agent required). No forecast grid has been captured for any fixture, so the
roof/wind/precipitation overlay (R57–R60) stays not-started/blocked. This read confirms the route,
not the data.

### 8. NIST correlation confidence limits — method confirmed

The NIST DATAPLOT reference gives the Fisher normal-approximation interval
`LCL=tanh(Z−Φ⁻¹(1−α/2)/√(n−3))`, `UCL=tanh(Z+Φ⁻¹(1−α/2)/√(n−3))` with `Z=atanh(r)`.
This is exactly the formula implemented in `requirements-desk/scripts/analyze.py` (`fisher_ci`).
The four published official correlations (n=32) stand.

### 9. NFL Terms §1.3 — public/private split required

NFL.com Terms (Updated May 16, 2024), §1.3: use is "solely for your own individual non-commercial
and informational purposes only"; "Systematic retrieval of data or other content from the Services,
whether to create or compile, directly or indirectly, a collection, compilation, database, or
directory, is prohibited absent our express prior written consent." The public site therefore keeps
derived analysis and links to official pages; raw row-level captures stay in the governed store
(R62–R64). No terms register has been committed yet.

## Irregularities flagged (none blocking)

- **IR-1 (FL-17 persists, narrowed):** REG10 `<title>` says Week 11, body says WEEK 10. REG11 now
  correctly serves Week 11, so the "REG11 serves Week 10" half of FL-17 is resolved; the REG10
  title mismatch remains. Published on the Flagged for Review page.
- **IR-2:** The official Game Book hub URL failed to fetch in this session. Prior Game Book links
  (WAS@NYG, BAL@BUF PDFs) are unchanged and were not re-fetched.
- **IR-3:** No Week 11 injury register was transcribed in this session. The Week 11 report exists
  (REG11) but publishing its rows requires a full transcription + hash, which is a separate task.
  Until then, Week 11 availability stays blank by policy.

## Verification performed

- Compared all 14 Week 10 scores, all 13 Week 11 fixtures (date/kickoff/network/venue/neutral-site),
  both bye lists (4 + 6 clubs), and all 32 standings rows against the committed CSVs: **0 mismatches**.
- Re-confirmed the three Lions designations (Out) from the retrieved text.
- Ran the full local suite (see COORDINATION.md B3): root + requirements-desk + line-desk +
  price-desk + review-board + decision-desk + verify-hub all pass.
