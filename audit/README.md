# Independent source and quality audit

This directory is an independent review of the research dashboards and selected
parallel work, as observed on 2026-11-01. It is **not** a validated betting system.
The browser-facing report is [`index.html`](index.html). Links to unmerged branch
work are pinned to a reviewed commit; their current status may differ.

Run the offline checks from the repository root:

```sh
python3 -m unittest discover -s audit -p 'test_*.py'
python3 audit/check_site.py
# Optional strict provenance gate (exits nonzero for source-domain flags):
python3 audit/check_site.py --strict-sources
```

The checker walks static HTML, checks local targets and anchors, and inspects
source IDs in the JSON data rendered by `dashboard/`. It reports rows lacking an
explicitly recognized publisher link, including this repository's GitHub pages
for repository facts. The default exits nonzero for broken links or unreadable
JSON; source-domain and ID findings are printed as nonblocking review flags.
`--strict-sources` makes those findings fail too. It is intentionally conservative;
add a publisher only after its authority has been checked.

A recognized domain is not evidence that the particular claim is true. The script
does not access the network, render the runtime DOM, validate external URLs,
review source content, reconcile statistics, or validate models. Those require
separate independent source review. It does not claim complete HTML conformance
or accessibility testing.

See the report and `COORDINATION.md` for primary-source links, reviewed values,
unresolved discrepancies, and the specific scope of each finding.
