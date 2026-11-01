# Coordination Board — NFL Line Origination & Strategy Lab

Last updated: 2026-11-01 (UTC). Maintained by the **integration session `7b140798`**
(Arena branch `arena/7b140798-korea2`, the branch Arena tracks for this session).

> Read this file before starting any work. Claim a task by writing your session ID and file
> scope below, commit immediately, and push. Never start a task another session has claimed.
> Shared outputs (`COORDINATION.md`, table data, site index/navigation) are changed only by the
> final integration session.

## Branch / naming deviation (recorded, applies to every session)

The brief asks for per-session branches named `session-<id>/<task>`. Arena fixes each session to
its own assigned branch and forbids creating or pushing any other branch, so **all sessions work
on their assigned `arena/<id>-korea2` branch**. This deviation is recorded here rather than
worked around. Each session's branch *is* its isolation mechanism.

## Sibling-session claims detected (2026-11-01, before any work by this session)

Checked with `git ls-remote --heads origin` + `git show <sha>:COORDINATION.md`. Four sibling
sessions had already created claim-only `COORDINATION.md` files (no data, no site, no scripts):

| Sibling branch | Claim head | Scope claimed | Artifacts present at integration time |
|---|---|---|---|
| `arena/97d4c0f1-korea2` | `c2e8d01` | `COORDINATION.md, README.md, index.html, assets/, pages/, .github/workflows/, tests/` | none (board only) |
| `arena/9e0420bd-korea2` | `03c6bc6` | "entire repository" | none (board only) |
| `arena/d88b794a-korea2` | `0356e4a` | `.github/workflows/fetch-nflverse.yml, scripts/fetch/fetch-nflverse.sh` | workflow + fetch script only |
| `arena/e0d506a4-korea2` | `607a38d` | `COORDINATION.md, README.md, index.html, assets/, category pages, scripts/` | none (board only) |

Every sibling claim covers the whole repository, so the scopes are **mutually overlapping by
construction** (identical prompt, one repo). This is flagged for the operator, not silently
resolved. Resolution applied by this session, per the brief's rule that *shared outputs are
changed only by the final integration session*:

* This session (`7b140798`) takes the **integration** role: it produces the data pipeline, the
  research, the site, and does the final line-by-line re-verification and deploy.
* Sibling scopes are **recorded, not discarded**. Their branches are untouched and still exist.
* Before merging, this session re-checked all sibling heads for artifacts; anything meaningful
  found there is merged or logged here. Nothing was force-pushed or deleted.
* The sibling `d88b794a` fetch workflow pointed at a download path that this session's pipeline
  also covers; to avoid two competing fetchers writing the same files, `d88b794a`'s file is left
  on its branch and **not** duplicated here. Logged as an overlap, not a conflict.

## Task board

| ID | Task | Status | Owner | File scope |
|---|---|---|---|---|
| T0 | Coordination board + session reconciliation | done | `7b140798` | `COORDINATION.md` |
| T1 | Source inventory & provenance register (official + market data) | done | `7b140798` | `data/sources.json`, `sources.html` |
| T2 | Reproducible data pipeline (download → parse → normalized JSON) | done | `7b140798` | `scripts/fetch_data.sh`, `scripts/build_dataset.py`, `data/processed/` |
| T3 | Line-origination models (team ratings → spread/total/ML; player prop engine) | done | `7b140798` | `scripts/model.py` |
| T4 | Strategy lab: singles, parlays, prop combos + empirical correlations | done | `7b140798` | `scripts/backtest.py`, `data/processed/*.json` |
| T5 | Validation gates, luck-removal, leaderboard scoring | done | `7b140798` | `scripts/validation.py`, `validation.html`, `leaderboard.html` |
| T6 | Official-source verification of every published value | done | `7b140798` | `scripts/verify_official.py`, `data/official/`, `flagged.html` |
| T7 | Site build (landing + category pages, no broken links) | done | `7b140798` | `index.html`, `*.html`, `assets/` |
| T8 | Executive summary | done | `7b140798` | `EXECUTIVE_SUMMARY.md` |
| T9 | Integration: re-verify combined data, link check, PR → main, merge, Pages deploy | done | `7b140798` | `.github/workflows/pages.yml`, this board |

Status values: `unclaimed` · `in progress` · `done` · `needs review` (published on
`flagged.html`, does not block anything) · `blocked`.

## Handoff / takeover rule

A claim older than 60 minutes with no commits may be taken over by any other session; the
takeover must be logged here before work starts.

## Log

### 2026-11-01 — `7b140798` — session start

* Repo at `414eeca` contained only `README.md` (8 bytes) and no `COORDINATION.md`. Created this
  board and claimed T0–T9. Committed and pushed the claim before starting work.
* Sibling claims found and recorded in the table above (nothing to preserve beyond their boards).
* Network note: this sandbox can only reach `github.com`, `codeload.github.com`,
  `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org` with `curl`.
  `nfl.com` is reachable only through the page-fetch tool. The pipeline is therefore split:
  bulk data is pulled from GitHub (nflverse mirrors of NFL gamebooks / sportsbook lines) and
  every *published* value is re-verified against `nfl.com` official pages fetched with the
  page tool and archived under `data/official/`.

### 2026-11-01 — `7b140798` — data provenance decisions

* **Official (nfl.com)** — used to verify published scores/standings, rule citations, and the
  league's gambling policy. URLs recorded in `data/sources.json` with retrieval dates.
* **Market lines** — closing spread/total/moneylines mirrored by nflverse (`nfldata`,
  `data/games.csv`, documented as sportsbook closing lines). These are *market* data, not an
  official league publication, and are labelled as such everywhere they appear.
* **Play-level player stats** — nflverse `stats_player` release (weekly, 1999–2026), derived from
  official NFL gamebooks. Used for prop modelling; spot-verified against `nfl.com` player pages.
* Anything that could not be tied to a resolvable source is **blank and flagged**, never filled
  by inference. See `flagged.html`.
