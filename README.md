# Gridiron Signals — NFL Lines Research

A source-linked, static research dashboard for designing and validating NFL fair-probability signals across game lines, player props, parlays and same-game combinations.

**Important:** this repository does not currently contain a line-generation model, odds feed, local historical NFL dataset, betting recommendations, measured correlations, backtest or validated strategy. Its line and combo methods are proposed research designs only. All currently unverified items are listed on the site's [Flagged for Review](review.html) page; numerical results are left blank rather than inferred.

## Site pages

- [Executive overview](index.html)
- [Strategy blueprints and correlation plan](strategies.html)
- [Validation gates and leaderboard rules](validation.html)
- [NFL source register](data.html)
- [Flagged for Review](review.html)

## Build and verify locally

Requires Python 3 (standard library only):

```sh
python3 scripts/check_site.py
```

The check validates every internal page/anchor link and requires every data-table body row to include a source link. GitHub Pages publishes the static HTML from the repository through `.github/workflows/pages.yml` after a merge to `main`.

## Research boundaries

Official NFL sources provide the cited stats definitions/categories and NFL integrity-policy references. The cited peer-reviewed/preprint work is only methodological context; it is not evidence of profitability in NFL markets. See the data and review pages for scope and limitations. No real-money wagering should rely on this unvalidated material.
