# Availability Sweep — 32-team official Week 10 register and dated capture series

Owner: session `arena/9fa8ea61-korea2` · As of 2026-11-18T03:55:37Z · Scope claimed in `COORDINATION.md` (AV-0…AV-6).

## What was done

1. **Full row-by-row transcription of the official NFL.com Week 10 injury report** (`https://www.nfl.com/injuries/league/2026/REG10`, read 2026-11-18T03:50–03:55Z in 8 chunks): **28 team tables, 347 rows**, each row with the report URL and the player's official page URL. This completes what the 2026-11-15 capture left partial (3 of 28 teams transcribed; flag F-W10-5).
2. **Bye verification** — the four clubs absent from the report (CHI, DEN, PHI, TB) are confirmed by the official schedule page's "Teams on Bye" section (closes flag F-W10-6). 28 + 4 = 32 clubs accounted for.
3. **Second dated capture + delta** — the 33 overlapping rows (DET, SEA, CIN) between the 2026-11-15T18:08:20Z capture and this capture are compared programmatically: **0 fields changed** (`data/delta_20261115_20261118.csv`). Per-team counts reconcile with the independent manual counts committed by the earlier session (all 28 match; both totals 347).
4. **Week 11 first-read attempt** — `https://www.nfl.com/injuries/league/2026/REG11` at capture time **served the Week 10 report** (canonical reg10): the Week 11 report was not yet published. No rows invented (flag AV-F1).
5. **Flags carried forward and new** — `data/flags.json` + `pages/flags.html`: Kenneth Walker III table-status vs official downgrade article (AV-F2), Henderson IR conflict (AV-F3), Nacua blank status (AV-F4), the unexplained 279 figure (AV-F5), no raw-byte hash (AV-F6), no daily practice history on the page (AV-F7), Maye post-game injury note (AV-F8), separator transformation disclosure (AV-F9).

## Data conventions

- Cells are verbatim transcriptions; **blank stays blank** (rendered as "blank" in HTML, empty in CSV).
- Multi-injury text uses `; ` in CSV where the page uses `, ` (CSV delimiter safety; otherwise identical — flag AV-F9). HTML tables render the comma form.
- Team codes follow the official pages: the report/schedule pages use `AZ` for the Cardinals (logo slugs and standings do too); the earlier session's manual-count register wrote `ARI`. The alias applies only inside `scripts/verify.py`'s reconciliation, not to the committed values.
- No raw HTTP bytes/hash were retained (fetch-tool read; shell cannot reach nfl.com) — flag AV-F6.
- Venue is recorded only where the schedule page states it (Munich International Game); other venues are left blank, not inferred.

## Files

| File | Contents |
|---|---|
| `data/week10_rows_20261118.csv` | 347 transcribed rows |
| `data/week10_team_counts_20261118.csv` | per-team counts (generated) |
| `data/week10_byes.csv` | 4 bye clubs with source |
| `data/week10_games.csv` | 14 Week 10 finals with game-centre links |
| `data/capture_log.csv` | 3 dated reads incl. the Week 11 attempt |
| `data/delta_20261115_20261118.csv` | 33-row comparison (0 changes) |
| `data/flags.json` | 9 flags with source links |
| `scripts/build_site.py` | deterministic page builder (`--check` mode) |
| `scripts/verify.py` | strict data verifier |

## Verify

```bash
python3 availability-sweep/scripts/build_site.py --check
python3 availability-sweep/scripts/verify.py
python3 tests/check_site.py
python3 scripts/check_links.py
```
