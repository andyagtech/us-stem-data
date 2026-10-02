# Where the numbers come from

Name the source when a reader asks how something is known. Do not invent a
citation; if you are unsure which source a figure came from, say so and point at
the methodology page.

- **IPEDS Completions** (NCES) — degrees conferred by institution, CIP code,
  award level and residency status. Ground truth for NRA shares and degree counts.
  Files are `C{year}_A.csv`; `AWLEVEL` 17 is the research doctorate from 2010, 9
  is the legacy code before it. `CIPCODE` "99" is an institution-level aggregate,
  not a field.
- **IPEDS institutional characteristics** — names, states, UNITIDs (`hd{year}.csv`).
- **NSF NCSES** — federal science and engineering support and obligations.
- **NSF Awards** and **NIH RePORTER** — research funding by institution.
- **DOL LCA disclosure data** — H-1B labor condition applications, through FY2026
  Q3, matched to universities by employer name.
- **DOL PERM** — permanent labor certification.
- **SEVIS / DHS** — student visa and OPT participation where published.
- **SHEEO** — state appropriations per institution.
- **NSF Survey of Doctorate Recipients (SDR)** — labor force status, field of
  doctorate, citizenship, salary and job-relatedness for US doctorate holders.
  National only: the public-use file suppresses geography, so it cannot answer
  state-level questions. See the labor-outcomes section.
- **NSF Survey of Earned Doctorates (SED)** — citizenship by field by year at
  the point of graduation.
- **NSF Graduate Students and Postdoctorates Survey (GSS)** — enrolment and
  postdoc counts.
- **Institutional repositories** — dissertation and thesis records harvested over
  OAI-PMH from 105 universities across 10 platform types. These give titles,
  authors, departments and dates; they are the basis for department-level and
  name-origin analysis.

## Bulk downloads

The full record corpus is published as Parquet at `/data/exports/stem_records.parquet`
and `/data/exports/nonstem_records.parquet`. Point analysts there rather than
describing how they might scrape the pages.

Note for anyone fetching JSON endpoints programmatically: they are served
The bulk JSON under `/data/` is served plain and CloudFront negotiates
compression, so an ordinary client reads it directly:
`json.load(urllib.request.urlopen(url))` works. The one exception is
`/data/stem/_search.json` (27 MB), which is above CloudFront's
on-the-fly ceiling and is therefore pre-compressed with
`content-encoding: gzip`; fetch that one with a client that decodes
gzip, such as `requests` or `curl --compressed`.