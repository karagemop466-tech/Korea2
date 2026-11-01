# Independent source and quality audit

This directory is an independent review of the research dashboards and selected
parallel work, as observed on 2026-11-01. It is **not** a validated betting system.
The browser-facing report is [`index.html`](index.html). Links to unmerged branch
work are pinned to a reviewed commit; their current status may differ.

Run the offline checks from the repository root:

```sh
python3 -m unittest discover -s audit -p 'test_*.py'
python3 audit/check_site.py
```

The checker walks HTML files, checks local file targets and HTML anchors, and
requires each data row to link to an explicitly recognized primary publisher
or this repository's own GitHub pages for repository facts. It is intentionally
conservative; add a publisher only after its authority has been checked. A
recognized domain is not evidence that the particular claim is true. The script
does not access the network, validate external URLs, review source content,
reconcile statistics, or validate models. Those require separate human or
independent source review. It also does not claim a complete HTML conformance or
accessibility audit.

See the report and `COORDINATION.md` for primary-source links, reviewed values,
unresolved discrepancies, and the specific scope of each finding.
