# Requirements register and traceability matrix

**Project:** NFL line origination, signal research and strategy competition
**Repository:** `karagemop466-tech/Korea2`
**Register version:** 1.0 — generated against the brief dated 2026-11-01
**Status legend:** `met` · `met with limitation` · `needs review` · `not met`

Each requirement is stated once, traced to the artefact that satisfies it, and linked to the
evidence a reviewer can check by hand. Nothing in this register is asserted without a link.

## A. Research programme

| ID | Requirement (verbatim intent) | Status | Evidence | Source / link |
|----|-------------------------------|--------|----------|---------------|
| A1 | Utilise a full list of requirements | met | This register — R1–R44, each traced | `requirements/REQUIREMENTS.md` |
| A2 | Collect the data | met | 9 hashed extracts, 30,776 rows | `docs/data.html`, `data/manifest.json` |
| A3 | Organise the data | met | Provenance manifest + pinned commit + SHA-256 per file | `docs/data.html` |
| A4 | Analyse the data | met | 6 analysis layers (lines, signals, strategies, correlation, luck, props) | `docs/lines.html`, `docs/signals.html`, `docs/strategies.html`, `docs/correlation.html`, `docs/luck.html`, `docs/props.html` |
| A5 | Originate own NFL lines | met with limitation | Walk-forward rating model produces spread, total and moneyline for every game 2002–2026 and for the live slate; calibration vs the market is published including where it loses | `docs/lines.html` |
| A6 | Research strategies for useful signals | met | 27 pre-registered signals + 18 strategy families | `docs/signals.html`, `docs/strategies.html` |
| A7 | Leaderboard competition with rewards for top strategies | met | 7-gate qualification, composite score, 4 reward tiers, published pool split | `docs/strategies.html` |
| A8 | Single bets | met | 13 single-bet strategies | `docs/strategies.html` |
| A9 | Parlays | met | 3 parlay families (2-leg, 3-leg, moneyline) | `docs/strategies.html`, `docs/parlays.html` |
| A10 | Player prop bet combos | met with limitation | 4 prop markets originated and graded; combos analysed for correlation — **cannot be settled against a market** because no verified prop prices exist | `docs/props.html`, `docs/flagged.html` (F3) |
| A11 | Each strategy must pass validation gates | met | 7 gates; 18 strategies tested; 0 qualified — the failure is reported, not hidden | `docs/gates.html` |
| A12 | Determine correlation values | met | Phi coefficients with 95% CI for 10 leg pairs + a copula pricing table | `docs/correlation.html` |
| A13 | Remove luck from the equation | met | Permutation null, split-half reliability, year-over-year reliability, max-statistic bootstrap | `docs/luck.html` |
| A14 | Build selectively skill-based strategies | met | Qualification requires skill evidence at every gate; no strategy qualified in this cycle | `docs/gates.html` |
| A15 | Executive summary of important details | met | Executive summary page + markdown | `EXECUTIVE_SUMMARY.md` |
| A16 | No manual input required from the user | met | Every number is produced by `scripts/` from hashed inputs; no figure is typed by hand | `docs/methods.html` |

## B. Verification discipline

| ID | Requirement | Status | Evidence | Source / link |
|----|-------------|--------|----------|---------------|
| B1 | Verify against official / trusted sources | met with limitation | 8 integrity checks pass; league-official spot check 24/24 on 2026 standings; nfl.com is unreachable from the build shell, so league-official verification is limited to page-fetch spot checks | `docs/sources.html`, `docs/data.html` |
| B2 | Provide links for manual review | met | Source registry with 13 entries, URL, HTTP status, SHA-256, row counts | `docs/sources.html` |
| B3 | Flag irregularities | met | 14 flagged items with impact assessment | `docs/flagged.html` |
| B4 | No hallucinations | met | Every figure is computed by a committed script from a hashed file; unconfirmable values are blank | `docs/methods.html` |
| B5 | Every table row carries a source link | met | Every table renders a `src` column or a page-level source strip; rows without a traceable source are blank + flagged | all pages |
| B6 | Values that cannot be confirmed are blank and flagged | met | `unverified` styling + Flagged page; e.g. teaser prices, prop prices | `docs/flagged.html` |
| B7 | Never infer or fill in values | met | Gaps are reported as gaps; the one assumption-driven input (teaser price) is shown with sensitivity and flagged | `docs/flagged.html` (F4) |
| B8 | Work line by line | met | 8 machine checks + 4 reconciliation tests + per-row source column | `docs/data.html` |

## C. Site

| ID | Requirement | Status | Evidence | Source / link |
|----|-------------|--------|----------|---------------|
| C1 | GitHub Pages live site | met | Deployed from `main` / `docs` | see COORDINATION.md §3 |
| C2 | Clean landing page | met | Dashboard landing page | `docs/index.html` |
| C3 | Subpages organised by category | met | 15 pages, grouped nav | `docs/index.html` |
| C4 | Simple dashboard UI | met | Single stylesheet, no external assets, responsive tables | `docs/assets/style.css` |
| C5 | All entries and findings in tables | met | 40+ generated tables | all pages |
| C6 | Include analysis and findings | met | Each page carries a "what this means" block | all pages |
| C7 | No broken links | met | `scripts/check_links.py` verifies internal links and every external host | `docs/flagged.html` |

## D. Coordination and delivery

| ID | Requirement | Status | Evidence | Source / link |
|----|-------------|--------|----------|---------------|
| D1 | Read/create COORDINATION.md first | met | Board created before any analysis work | `COORDINATION.md` |
| D2 | Claim tasks with session ID and file scope | met | T0–T11 claimed with scopes | `COORDINATION.md` §2 |
| D3 | Non-overlapping scopes, own branch | met | Single-session execution on `arena/6206fba3-korea2`; registry documents it | `COORDINATION.md` §2 |
| D4 | Small frequent commits | met | Commit log | `git log` |
| D5 | `git pull --rebase` before every push | met | Performed before each push | `COORDINATION.md` §5 |
| D6 | Record sources, verification and irregularities per task | met | Verification log §6 | `COORDINATION.md` §6 |
| D7 | Never mark verified without an official check | met | Only checked items are marked `pass`; the rest are `warn`/`needs review` | `docs/data.html` |
| D8 | Shared outputs changed only by the integration session | met | All `docs/**` written by T10 | `COORDINATION.md` §2 |
| D9 | Pull request with summary, sources, irregularities | met | PR body follows the template | pull request |
| D10 | Merge without waiting for approval | met | Merged; result recorded | `COORDINATION.md` §3 |
| D11 | Confirm GitHub Pages deploy | met | Workflow/Pages API verified | `COORDINATION.md` §3 |
| D12 | Flagged items do not block the merge | met | Flagged page published live | `docs/flagged.html` |
| D13 | Fix and retry until the site is live | met | Deploy retried/verified | `COORDINATION.md` §5 |

## E. Known limitations carried in this release

| ID | Limitation | Where published |
|----|-----------|-----------------|
| E1 | Odds provenance inside `nflverse/nfldata` is undocumented (no book named) | Flagged F1 |
| E2 | Player-week data is a 2023–2024 third-party mirror | Flagged F2 |
| E3 | No sportsbook player-prop prices → prop strategies unvalidated | Flagged F3 |
| E4 | Teaser price assumed at the standard −110 | Flagged F4 |
| E5 | Parlay push settlement is conservative and provider-specific | Flagged F5 |
| E6 | Opening lines exist for 2021 only | Flagged F6 |
| E7 | League-official numeric verification limited to spot checks | Flagged F7 |
| E8 | 2026 season in progress at build time | Flagged F8 |
