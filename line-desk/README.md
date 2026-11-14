# Line Desk

Requirements desk for the 2026-11-14 brief: price-snapshot store, verified results feed,
origination order (side → total → moneyline) with fair/market/difference columns, a
signal-vs-staking leaderboard split, official-only correlations with n, a
replacement-depth store, and the promotion/demotion gate.

## Layout

- `index.html` + `pages/` — generated dashboard (15 pages); every table row ends in a source link.
- `data/` — committed registers; `official_*.json` are first-hand NFL.com/NIST transcriptions (2026-11-14).
- `scripts/compute.py` — derives all published numbers from the transcriptions and read-only repo inputs.
- `scripts/build_site.py` — deterministic renderer (`--check` fails if committed pages are stale).
- `scripts/verify.py` — the verification suite: strict JSON, blank-by-policy (market prices,
  untranscribed scores and depth tiers must be null), per-row source links, https links,
  recomputed correlations, deterministic rebuild.
- `EXECUTIVE_SUMMARY.md` — the one-page version.

## Rebuild and verify

```bash
python3 line-desk/scripts/compute.py
python3 line-desk/scripts/build_site.py
python3 line-desk/scripts/verify.py
python3 tests/check_site.py && python3 scripts/check_links.py
```

## Policy

A value that cannot be confirmed from an official source is left blank and flagged —
never inferred. Market prices are blank because the NFL's official betting feed is
distributed to operators (see `pages/sources.html`, LD-S10); depth tiers are blank
because the league depth-chart path 404s and the official report has no depth column.
