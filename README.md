# NFL Line Lab

Originating NFL lines, researching signals, and running a gated strategy competition on open data —
with the verification trail published alongside the results.

**Live site:** https://karagemop466-tech.github.io/Korea2/ (GitHub Pages, served from `main` / `docs`)

## What is here

| Path | Contents |
|---|---|
| `docs/` | the static dashboard site (GitHub Pages source) |
| `scripts/` | the whole pipeline: fetch → verify → model → test → site |
| `data/manifest.json` | SHA-256, row counts and pinned commit for every input |
| `data/derived/` | every published number, as JSON |
| `requirements/REQUIREMENTS.md` | the brief broken into 44 traced requirements |
| `EXECUTIVE_SUMMARY.md` | findings, evidence, and the four decisions requested |
| `COORDINATION.md` | shared task board, claims, verification log |

## Rebuild

```bash
python3 -m venv .venv && .venv/bin/pip install numpy pandas scipy
.venv/bin/python scripts/fetch_data.py     # needs network: github.com / api.github.com / codeload.github.com
.venv/bin/python scripts/build_all.py      # data + site + link check
```

## Headline result

The model lands within 10.69 points of the actual margin (the closing line: 10.26). Of 27 pre-registered
signals and 18 strategy families, **none** passed the seven validation gates. The reward pool is
unallocated, and the site publishes exactly why, strategy by strategy.

## Not betting advice

This is a research artefact built from hashed public datasets. See `docs/flagged.html` for the 14 items
that need human review, including the undocumented provenance of the odds columns.
