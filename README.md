# NFL line origination, strategy leaderboard and validation gates

We originate our own NFL spread, total and moneyline for every game, turn the disagreements into betting
strategies, and then try to break those strategies before trusting them.

- **Live site:** https://karagemop466-tech.github.io/Korea2/
- **Executive summary:** [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
- **Requirements, line by line:** [REQUIREMENTS.md](REQUIREMENTS.md)
- **Data provenance and checksums:** [data/PROVENANCE.md](data/PROVENANCE.md)
- **Flagged irregularities:** [pages/flagged.html](pages/flagged.html)
- **Session task board:** [COORDINATION.md](COORDINATION.md)

## Headline

Nothing cleared all ten validation gates, and the site says so with the arithmetic attached. The control that
backs every home team against the spread returns −5.40% on 3,054 held-out tickets — the bookmaker's margin —
while the best-looking rule (+9.22%) sits on 225 tickets with a confidence interval that straddles zero and a
Benjamini-Hochberg q of 0.32.

## What is here

| Path | What it is |
|---|---|
| `pipeline/` | The whole analysis: fetch → features → origination → strategies → gates → props → correlation → verification → site |
| `site_data/` | Machine-readable outputs (JSON + CSV). Every figure on the site comes from here. |
| `pages/`, `index.html`, `assets/` | The static site served by GitHub Pages |
| `data/PROVENANCE.md` | Pinned commit SHAs and SHA-256 for every upstream file |
| `EXECUTIVE_SUMMARY.md`, `REQUIREMENTS.md`, `COORDINATION.md` | Findings, requirement status, task board |

## Reproduce

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python pipeline/fetch_data.py        # pinned downloads, writes data/PROVENANCE.md
python pipeline/fetch_data.py --check # re-verify every SHA-256
python pipeline/run_all.py           # ~5 minutes end to end
```

## Sources

- Game results and closing prices: `nflverse/nfldata` (pinned commit, hashed).
- Player-game statistics 2009-2017: `ryurko/nflscrapR-data` (pinned commit, hashed).
- Cross-check of player aggregates: `nflverse/nflverse-pfr`.
- Official league spot checks: [NFL.com](https://www.nfl.com/schedules/).

No figure on the site is hand-typed; `pipeline/build_site.py` renders the HTML from `site_data/*.json`.
