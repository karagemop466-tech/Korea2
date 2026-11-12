# Repo review — verification, irregularities, and manual-review links

**Session:** arena/cb5b61a7-korea2 &nbsp;|&nbsp; **Branch:** arena/cb5b61a7-korea2 &nbsp;|&nbsp; **Reviewed:** 2026-11-12
**Live site:** <https://karagemop466-tech.github.io/Korea2/>

This document is the line-by-line review requested in the brief. It records what was
verified against official/trusted sources, what could not be verified, and the
irregularities that need a human decision. No value is inferred where a source is missing.

---

## 1. Scope and method

- **Reviewed directly (this session):** repository structure, the published build's
  HTML/CSS, `tests/check_site.py` output, the new pages added this session
  (`pages/suggestions.html`, `pages/decision-questions.html`, `pages/injuries-depth.html`),
  and a set of official external sources retrieved live.
- **Not re-derived this session:** the statistical pipeline numbers (model MAE, correlations,
  gate results, leaderboard). They are produced by code in `scripts/` from the committed
  `data/` artefacts and are reproducible on GitHub Actions; the sandbox cannot fetch the
  underlying feed (nflverse) or run the full pipeline, so I did **not** recompute them.
  They are treated as *reproducible, not independently re-verified here*, and the repo's own
  `pages/verification.html` is the authority for their reconciliation.
- **Tooling result:** `python3 tests/check_site.py` → *all site checks passed* (100 pages,
  18 in the published build, 258 tables, 4167 links). Every published table row carries a
  source link; all internal links resolve; all external links are https.

---

## 2. What was verified against official sources (live retrieval, 2026-11-12)

| Claim / asset | Verification | Result | Link for manual review |
|---|---|---|---|
| NFL official standings 2026 (all 32 teams) | Retrieved division standings; records match the repo's stated reconciliation sample | Confirmed (sample: NE 5-4, DET 6-2, KC 6-2, NYG 5-2-1, WAS 2-5-1, ATL 3-6, BUF 7-1) | <https://www.nfl.com/standings/division/2026/REG> |
| NFL official injury report, Week 10 2026 | Retrieved; returns per-team player / practice / game status | Confirmed resolves | <https://www.nfl.com/injuries/league/2026/REG10> |
| DraftKings parlay settlement & correlation rules | Retrieved; confirms all-legs-must-win, push removes a leg and recalculates, and correlated outcomes may be restricted | Confirmed | <https://support.draftkings.com/dk?id=kb_article_view&sysparm_article=KB0010683> |
| nflverse data feed (third-party) | GitHub repo live; latest commit 2026-11-01 | Exists; **third-party, not official NFL** | <https://github.com/nflverse/nflverse-data> |
| Published build integrity | `tests/check_site.py` | Passed | `tests/check_site.py` |

---

## 3. Per-area findings

### 3.1 Site build & structure
- The repository is a static GitHub Pages site (legacy build serving `main` root). Root
  `index.html` plus `pages/` form the integrated "Line Lab" dashboard; sibling dashboards
  exist under `dashboard/`, `nfl-lines/`, `nfl-research/`, `research-desk/`, `quant-lab/`,
  `origination/`, `origination-lab/`, `skill-lab/`, `audit/`, `pipeline/`, `verification/`.
- `check_site.py` enforces: parseable HTML + title, resolving internal links, resolving
  in-page anchors, a source link on every published table row, https-only external links,
  and required-page reachability from the nav. All satisfied.

### 3.2 Data lineage
- `data/sources.json` is the source register; `data/derived/manifest.json` records per-file
  size + SHA-256 (per README). The feed is **nflverse** (third-party), not an official NFL
  endpoint — see irregularity IR-2.
- The pipeline downloads on GitHub Actions (README explains release-asset redirects are
  blocked from the sandbox). This is why I could not re-run it here.

### 3.3 Headline claims (spot-checked, not recomputed)
- "Closing line is hard to beat" (model MAE 10.39 vs market 10.25) and "0 of 7 strategies
  passed the 10 gates" are internally consistent with the leaderboard/validation pages and
  are reproducible from committed code+data. They were **not** recomputed by me; the repo's
  `pages/verification.html` is the reconciliation authority.
- Team-record reconciliation was spot-checked against live NFL.com standings (Section 2) and
  matches. Full 32/32 reconciliation is claimed by the repo, not independently re-checked
  team-by-team in this session.

### 3.4 Injury & depth handling (new this session)
- Verified the official injury report resolves per week; built a worked example from Week 10
  2026 (Patriots @ Lions) using only confirmed `OUT` statuses.
- **The official team depth-chart endpoint returns HTTP 404** (verified twice, with and
  without trailing slash). Therefore "starter vs 2nd/3rd/4th string" cannot be sourced from
  NFL.com. The page flags this and proposes a discovery path (nflverse depth + Next Gen snap
  counts). This is irregularity IR-1.

### 3.5 Strategies, leaderboard, validation, correlation, luck (existing)
- Design is sound and matches the brief: single bets, parlays, player-prop combos; a
  leaderboard with reward tiers; ten validation gates; measured correlations; explicit
  luck-removal framing. All retained and linked from the new pages.
- These pages were produced by prior sessions and are flagged on the site's
  `pages/flagged.html` for open caveats (see IR-3).

---

## 4. Flagged irregularities (do not block publication; need a human decision)

| ID | Severity | Finding | Recommended action | Link |
|---|---|---|---|---|
| IR-1 | Medium | Official NFL team depth-chart endpoint (`/teams/<team>/depth-chart`) returns 404; starter-vs-backup deficiency cannot be officially sourced | Use nflverse team depth + Next Gen snap counts; reconcile before trusting; keep deficiency severity blank until sourced | <https://www.nfl.com/teams/new-england-patriots/depth-chart> |
| IR-2 | Medium | The data feed (nflverse) is third-party, not an official NFL source | Document provenance/licensing; do not present its values as "official NFL" | <https://github.com/nflverse/nflverse-data> |
| IR-3 | Medium | Prior-session open caveats documented on `pages/flagged.html` (reversed correlation wording, ex-post WR1 selection, imputed −110 prices, week/schedule errors, holdout leakage) remain unresolved | Reviewer should read `pages/flagged.html` and request corrections per the linked issues | <https://karagemop466-tech.github.io/Korea2/pages/flagged.html> |
| IR-4 | High (for capital) | No opening lines / CLV in the feed → skill-vs-luck CLV is unmeasurable | Acquire timestamped opening+closing price history | `pages/flagged.html` |
| IR-5 | High (for capital) | No licensed historical player-prop prices → prop ROI unmeasurable | Acquire licensed prop feed | `pages/props.html` |
| IR-6 | High (legal) | No verified sportsbook access, limits, or license; no jurisdiction/legal assessment | Legal + compliance review before any stake | NCPG helpline |
| IR-7 | Low | Reward pool is a design, not funded | Budget decision by owner | `pages/leaderboard.html` |

---

## 5. Manual-review links (start here)

- Live site root: <https://karagemop466-tech.github.io/Korea2/>
- New this session — Suggestions: <https://karagemop466-tech.github.io/Korea2/pages/suggestions.html>
- New this session — Decision questions: <https://karagemop466-tech.github.io/Korea2/pages/decision-questions.html>
- New this session — Injury & depth: <https://karagemop466-tech.github.io/Korea2/pages/injuries-depth.html>
- Flagged for review: <https://karagemop466-tech.github.io/Korea2/pages/flagged.html>
- Official standings (verification): <https://www.nfl.com/standings/division/2026/REG>
- Official injury report (verification): <https://www.nfl.com/injuries/league/2026/REG10>

---

*Research and measurement, not betting advice. Values that could not be confirmed from an
official source are left blank and flagged; none are inferred.*
