# NFL Line Origination & Strategy Lab

Originated NFL lines (spread / total / moneyline / player props), a gated strategy leaderboard,
empirical correlation tables, and a line-by-line verification register.

**Live site:** https://karagemop466-tech.github.io/Korea2/

| Start here | |
|---|---|
| Executive summary | `EXECUTIVE_SUMMARY.md` |
| Coordination / task board | `COORDINATION.md` |
| Method + gates | `methodology.html` |
| Sources & provenance | `sources.html` |
| Flagged / unverified | `flagged.html` |

## Reproduce

```bash
bash scripts/fetch_data.sh      # pull pinned raw data (GitHub only)
python3 scripts/build_dataset.py # parse + normalize -> data/processed/*.json
python3 scripts/build_site.py     # regenerate every HTML page from the JSON
python3 scripts/verify_official.py # recompute the verification register
```

No manual input is required and no value is typed by hand: every published number is produced
by these scripts from a source recorded in `data/sources.json`.
