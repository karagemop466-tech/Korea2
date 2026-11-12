# NFL Command Center

Static GitHub Pages site (`nfl-command/`), published from `main` at
`https://karagemop466-tech.github.io/Korea2/nfl-command/`.

## What is here

| Path | Purpose |
|---|---|
| `index.html`, `pages/*.html` | The site: landing page, executive summary, injuries, depth, lines, strategies, correlations, gates, suggestions, questions, repo review, sources, flagged items |
| `assets/` | Shared CSS and JS (filters, decision recorder) |
| `data/raw/injury_report_wk10_2026.psv` | Transcribed NFL.com Week 10 injury report (one row per listed player) |
| `data/injuries.json`, `data/injury_team_summary.json` | Injury rows and club summary, generated from the transcription |
| `data/depth.json` | Starter and backup status per club. All value fields are blank: no official depth chart was reachable |
| `data/models.json` | Read-only copy of the committed Skill Lab outputs used by the site |
| `data/requirements.json`, `data/suggestions.json`, `data/questions.json` | Requirements, options for review (nothing implemented), and open questions |
| `data/sources.json`, `data/reconciliation.json`, `data/flagged.json`, `data/repo_review.json` | Source log, news vs report reconciliation, irregularities, repo checks |
| `scripts/build_site.py` | Rebuilds the pages and generated JSON. Standard library only |
| `scripts/verify.py` | Checks the site. Exit 0 only if every check passes |

## Rebuild and verify

```bash
python3 nfl-command/scripts/build_site.py
python3 nfl-command/scripts/verify.py
```

`verify.py` checks: every JSON file parses; every page exists and every local link resolves;
every table row carries a source link (official tables need an official link; computed tables need
a link and the UNVERIFIED-INPUT flag); non-official hosts appear only in rows labelled NOT OFFICIAL;
repo-file links point at files that exist; the injury counts match the transcription; blank injury
cells on the source stay blank; no placeholder text (None, nan, undefined, inf) appears.

## Rules the site follows

- Every table row links to a source. Unverified values are left blank and flagged, never inferred.
- Computed values (from Skill Lab inputs) carry an UNVERIFIED-INPUT badge.
- Suggestions are for review only. Nothing on the Suggestions page is implemented.
- Flagged items do not block a merge; they are listed on the Flagged for review page.
