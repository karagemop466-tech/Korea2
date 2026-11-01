# Fourth & Signal

A static, source-linked NFL line-origination research brief and validation framework. The site is served by GitHub Pages: https://karagemop466-tech.github.io/Korea2/.

## Executive summary

Five proposed strategies cover single-game markets, player props, cross-game parlays and same-game combinations. Price full outcome distributions, use point-in-time information, and validate against a matched market benchmark. Do not multiply correlated leg probabilities without justification. Variance can be quantified but luck cannot be eliminated.

**Status:** no strategy has been trained, backtested, ranked, funded or validated. Verified point-in-time odds, matched outcomes, correlation estimates and rules snapshots have not been obtained. The site deliberately leaves these quantities blank and records the limitations on its Flagged for Review page. It is not a live data feed, automated betting system, financial advice or a promise of returns.

The source library links to the NFL, NWS, NIST, scikit-learn and the operator's own rules. Sources support the subject or methodology, not profitability of the proposed strategies. See the site and `COORDINATION.md` for the source audit and irregularities.

## Build and checks

Python 3.9+; no dependencies or package installation required:

```sh
python3 scripts/build.py
python3 scripts/check_site.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

The builder generates all six HTML pages. The checker verifies local file targets and an HTTPS source in each table body row; it does not validate changing external websites. The small pricing library supplies tested arithmetic primitives only. Its unit tests use synthetic numbers and do not produce empirical NFL results. For a local preview, run `python3 -m http.server 8000` and open `/Korea2/` only when served under that prefix, or `/` from the repository directory.
