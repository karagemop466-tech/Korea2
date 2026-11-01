# COORDINATION.md — Shared Task Board

Repo: `karagemop466-tech/Korea2` — Project: **NFL Line Origination & Skill-Based Strategy Research**

This file is the shared task board for parallel agent sessions. Claim a task by writing your
session ID and file scope below, then commit and push that claim immediately. Never start a
task another session has claimed. Keep scopes non-overlapping. If a task needs a file owned by
another session, log the request here instead of editing it. Make small, frequent commits and
run `git pull --rebase` before every push. A claim older than 60 minutes with no commits may be
taken over by another session (note the handoff in the log).

## Session registry

| Session ID | Branch | Status | Notes |
| --- | --- | --- | --- |
| `arena-29806afc` | `arena/29806afc-korea2` | active | Only session detected at start (2026-11-01). Repo contained only `README.md` ("# Korea2") at commit `414eeca`. |

## Task board

| Task ID | Task | Status | Owner session | Files touched |
| --- | --- | --- | --- | --- |
| T1 | Research & verify official sources (NFL league/data, sportsbook terms, regulators, stats methodology) | in progress | arena-29806afc | `data/sources.json`, `data/league_facts.json` |
| T2 | Signal catalog & strategy framework (line origination, bet types, parlays/props, correlation, validation gates, leaderboard design) | unclaimed → claimed by arena-29806afc | arena-29806afc | `data/signals.json`, `data/strategies.json`, `data/bet_types.json`, `data/validation_gates.json`, `data/correlations.json`, `data/leaderboard.json`, `docs/EXECUTIVE_SUMMARY.md` |
| T3 | Repo line-by-line review with findings & irregularities | claimed | arena-29806afc | `docs/REPO_REVIEW.md`, `data/repo_review.json` |
| T4 | GitHub Pages site (landing + category subpages, dashboard UI, tables with per-row source links) | claimed | arena-29806afc | `index.html`, `pages/*.html`, `assets/*`, `data/*.json` (site reads), `.nojekyll` |
| T5 | Automated verification (data validator + internal link checker, CI workflows) | claimed | arena-29806afc | `scripts/validate_data.py`, `scripts/check_links.py`, `.github/workflows/validate.yml`, `.github/workflows/pages.yml` |
| T6 | Flagged-for-review register (unverified values left blank, with reasons + source links) | claimed | arena-29806afc | `data/flagged.json`, `pages/flagged.html` |
| T7 | Final integration: re-verify combined data line by line, build check, PR to main, merge, confirm Pages deploy, record results | claimed | arena-29806afc | `COORDINATION.md` (log), PR |

## Cross-session file requests

| Request | From session | To session | File | Status |
| --- | --- | --- | --- | --- |
| (none at start) | — | — | — | — |

## Log

- 2026-11-01 — Session `arena-29806afc` started. Repo reviewed at commit `414eeca`: only `README.md` (single line `# Korea2`), no `COORDINATION.md` existed, so this board was created. No other active sessions detected. All tasks T1–T7 claimed by `arena-29806afc` (sole session; integration role included). Research phase: every cited URL fetched/verified on 2026-11-01 against official domains (nfl.com, operations.nfl.com, media.nfl.com, nextgenstats.nfl.com, support.nfl.com, support.draftkings.com, sportsbook.draftkings.com, support.fanduel.com, gaming.nv.gov, itl.nist.gov, princeton.edu, pinnacle.com, kaggle.com, weather.gov, ncpgambling.org). See `data/sources.json` for the registry with per-URL verification notes.
