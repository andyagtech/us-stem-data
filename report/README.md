# The briefing

Everything the report is made of lives here, in the repository.

    report/pages/         one HTML fragment per page, numbered in render order
    report/pages/_style.css   the stylesheet
    report/generate.py    assembles the pages, renumbers, writes HTML and PDF
    report/builders.py    regenerates the data-driven pages from JSON

## Rebuilding

    python3 report/builders.py     # refresh data-driven pages
    python3 report/generate.py     # assemble -> briefing.html + the PDF

`generate.py --html` skips the PDF. The PDF is written to
`~/usds_china_reports/STEM_Pipeline_Briefing.pdf`.

## Why it is built this way

An earlier generator lived in a scratch directory and was destroyed when that
directory was cleared; only the rendered HTML had been copied out. Nothing
published was lost, because that file carried every page and chart as inline
SVG, but the means of rebuilding it was gone. Nothing about the report now
exists outside version control.

## Adding a page

Write a fragment into `report/pages/` with a number fixing its place, or add
a builder to `builders.py`. Then run `generate.py`. Do not type page numbers:

- **Footers** are written from render order on every build.
- **Section numbers** in the eyebrow are renumbered the same way; a page whose
  eyebrow says "(continued)" keeps its predecessor's number.
- **Cross-references** use anchors. A page claims a name with
  `<!-- ref:limits -->`; prose points at it with `{{page:limits}}`, and an
  unknown name fails the build rather than printing a wrong number.

Inserting one page shifts every footer, heading and reference after it. All
three are derived, so inserting a page requires editing nothing else.

## Known constraint

Pages carried over from the original generator hold their figures as rendered
text; only pages produced by `builders.py` re-read their data. The dataset
scripts under `scripts/` remain the record of how every number was derived.
