# The briefing

`briefing.html` is the source. `render_pipeline_page.py` inserts the
domestic-pipeline page from `site/data/domestic_pipeline.json`, renumbers
every footer, section heading and in-text cross-reference, and writes the PDF
to `~/usds_china_reports/`.

## Why the HTML is the source

The generator that first produced this report lived in a scratch directory
and was lost when that directory was cleared. Only the rendered HTML had been
copied out. It survived intact -- fourteen pages, ten charts, all inline SVG
-- so it became the source and now lives here, in the repository, where it
cannot vanish again.

The cost is that pages are no longer regenerated from data on every build.
Figures already in the HTML are fixed at the values they were rendered with;
`build_domestic_pipeline.py` and the other dataset scripts remain the record
of how each number was derived.

## Rebuilding

    python3 report/render_pipeline_page.py

Idempotent: it replaces its own page rather than adding a second, and the
cross-reference shift is guarded by a marker so a second run does not move
the references twice.
