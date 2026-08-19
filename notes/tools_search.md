# tools_search.py — find_departments, search_records, similar_to

Module: `/Users/andy/usds_china/cloud/chat/tools_search.py`
Exports exactly `SCHEMAS` (3 dicts) and `IMPL` (3 callables). No shared file edited.
Second file created: `/Users/andy/usds_china/scripts/build_chat_search_index.py` (index builder;
the search tool needs a build step, and the tokenizer is imported from tools_search.py so the
index and the query path cannot drift).
Artifact produced: `cloud/chat/chat_data/search_index.bin`.

Conventions followed from tools.py: `_fn` and `_clamp` imported (not replicated), `ds` for all
reads, `UNTRUSTED` banner, `scope` / `searched` string on every result, errors returned not raised.

## Correction applied: IPEDS award level

The index `basis` column carries two values, measured:

    aw09  103,642 rows   1995-2009
    aw17  156,528 rows   2008-2025

2008 and 2009 carry BOTH — some institutions reported the new level early, and the early
aw17 coverage is partial (2009: aw17 24,742 awards vs aw09 37,461). Summing the column blind
double-counts those two years; preferring aw17 there undercounts. `find_departments` therefore
gates one basis per year, switching at the 2010 taxonomy change:

    _basis_for_year(y) = "aw17" if y >= 2010 else "aw09"

Measured effect on a window spanning the change (CIP 14.1001, 2007-2011):
naive sum 9,703 awards, gated sum 8,366 — the gate removes 16.0% inflation.

The note the tool returns says: level 17 is doctor's degree research/scholarship from 2010;
before 2010 it is level 9, doctor's degree, which 17 and 18 (professional practice) were split
out of in 2010, so pre-2010 years are slightly broader; MD and JD sat in a separate pre-2010
category (first-professional) and are in neither. The earlier wrong reason (that level 9
"also counted MD and JD") is not written anywhere in the module.

## search_records: the size decision, with the measurements

### What the corpus actually is

    site/data/{stem,nonstem}/*.json   99 MB   517,715 records, 105 universities, 1,374 departments
                                              (excludes _search.json, 27.8 MB of browser artifact)
    data/processed/stem_records.parquet  14 MB   — stale (Apr 20) and unreadable here:
                                                  no pandas/pyarrow in this environment
    record tuple: [dept, year, author, name_origin, confidence, title, url, degree]
    mean title length 76 chars; years 1966-2026; 71 records carry no year

Note: the brief said 517,386. That is the `data/processed/` copy, which is stale. `site/data/`
is the copy `build_chat_facts.py` already reads and it has 517,715. I used `site/data/`.

### What full-text at record level would cost (all measured, gzip -9 / lzma preset 6)

    packed TSV (uni, dept, year, title, degree)   56.75 MB raw   17.50 MB gzip
    titles alone                                  39.88 MB raw   15.20 MB gzip
    record-level inverted index, df>=5             6.24 MB raw    5.69 MB gzip
      (3.68 M postings — and this is before ANY table to render a hit from)

So record-level full-text search does not fit. Not "is awkward": the postings alone are 5.69 MB
against a ~6 MB total budget that already had 2.0 MB spent, and they cannot show you a title.

### What I shipped

`chat_data/search_index.bin` — 3.39 MB. An inverted index over title terms whose postings
resolve to (university, department, year) cells.

    cells       38,875        vocabulary  37,141 terms (df >= 5)
    postings    2,970,339     load time   165 ms cold, once per container
    header      48 kB JSON    memory      ~8 MB inflated

Two rounds of lossless shrinking, both worth recording:

  1. First build put the cell table and per-term offsets in the JSON header. 3.89 MB, and
     `json.loads` of the 1.4 MB header cost **2,066 ms** of cold start — 13x the LZMA inflate.
     Moved everything per-term and per-cell into binary sections read with `array.array`.
     Header dropped to 48 kB, load to **165 ms**, file to 3.82 MB.
  2. Postings were interleaved (delta, count, delta, count). 87.6% of all counts are 1, so the
     two streams have very different statistics and LZMA models them much better apart:
     split into contiguous `pdelta` / `pcount` sections. **3.82 -> 3.39 MB, identical answers.**

Verified exact after both changes, against a direct scan of all 517,715 titles:

    quantum           index 2894   scan 2894
    semiconductor     index  594   scan  594
    crispr            index  403   scan  403
    superconductivity index  103   scan  103

### Is there a cheaper index that keeps the same answers? No — measured

The tool answers: exact single-term record counts, broken down by university, department and
year, under any combination of those three filters. Every cheaper index loses one of those.
All figures below are the same builder, lzma preset 6, df>=5:

    grain                          size      what it costs you
    institution x dept x year      3.39 MB   (shipped) nothing
    institution x dept + year      2.93 MB   year can no longer be crossed with university or
      marginal                               field — "quantum at MIT since 2020" becomes
                                             unanswerable, only "quantum at MIT" or "quantum
                                             since 2020"
    institution x dept             2.56 MB   no year dimension at all, no time series
    three separate marginals       2.21 MB   no filter can be combined with any other
      (uni / dept / year)
    institution x dept, df>=15     2.23 MB   above, and 18,445 rarer terms become unsearchable

The 0.46 MB between the shipped index and the next one down buys the entire time dimension
under filters. I judged that the wrong 0.46 MB to save and did not take it, but the table is
here so you can overrule me — it is a one-line change to the cell key in the builder plus a
year-marginal section, roughly 30 lines.

Levers I checked and rejected: dropping high-frequency terms (the top 40 by document frequency
are `analysis`, `study`, `learning`, `design`, `control`, `health` — legitimate search terms,
and the top 200 are only 25.3% of occurrences anyway); raising df past 15 (postings are
concentrated in common terms, so 2.95 M postings at df>=5 only falls to 2.71 M at df>=20).

### Cost to the shared budget

My contribution is **3.39 MB**, the single largest item in chat_data/. Current total 8.86 MB across all four modules (mine 3.39, universities_compact.json 1.52, doctoral_race_by_cip.csv.gz 2.45, original 2.0).
If you need me under a number, the table above is the menu; 2.93 MB and 2.56 MB are both real
options and I can cut to either in one pass.

## The three schemas

    find_departments(min_share, max_share, min_total, cip, state, years, sort, limit)
      required: none.  years = [start, end] inclusive (default [2020, 2025]); a single value
      is one year; 3+ values are an explicit set.  sort in share | share_asc | total | nra.
      limit 1-60, default 25.  min_total default 20.

    search_records(query, university, field, year, limit)
      required: query.  university = site key; field = substring of a department label;
      year = [start, end] or a single year; limit 1-50 (ranks institutions and departments).

    similar_to(university, by, limit)
      required: university.  by in profile | field_mix | origins | scale (default profile).
      limit 1-20, default 5.

## Worked results (real output, this build)

### find_departments — the headline query, answered in one call

`{"min_share": 80, "min_total": 50, "years": [2021, 2025]}` -> **70 departments**, 20 ms warm.

    96.3%   81 tot   78 nra  Case Western Reserve      22.0203 American/U.S. Law/Jurisprudence
    93.4%   76 tot   71 nra  Florida International     14.0801 Civil Engineering, General
    92.5%   53 tot   49 nra  Washington State          14.1001 Electrical and Electronics Eng
    92.4%   66 tot   61 nra  Penn State Main           45.0603 Econometrics and Quantitative Econ
    92.0%   88 tot   81 nra  Florida State             27.0501 Statistics, General

    threshold: {effective_min_total 50, matched_at_this_threshold 70,
                matched_if_min_total_were_1 722, at_100_percent_if_min_total_were_1 240}

That threshold block is on every result. It is the answer to "the min_total threshold is the
whole ballgame": the same share filter admits 722 departments at a cohort of 1, and 240 of them
sit at exactly 100%. The brief's 4,992 figure reproduces exactly as the *unpooled* count —
institution x CIP x year cells at 100% with cohort >= 1, 2020-2025 (2021-2025 gives 4,140;
2015-2025 gives 8,663). Pooled over 2020-2025 the same count is 247.

Other verified calls:

    {} (defaults: 2020-2025, min_total 20)          6,804 departments
    {min_share 80, min_total 50, years 21-25, cip 14}   39 departments (engineering only)
    {min_share 85, min_total 30, state TX, years 20-25}  7 departments
    {max_share 5, min_total 100, sort share_asc}      339 — the low end, led by
       Northcentral University 13.0101 Education, 2,021 doctorates, 0 non-resident
    {min_share 99, min_total 500, years 24-25}          0, with "460 departments match the
       share filters at min_total=1" in the note
    {min_share 90, max_share 10}                     error, min_share above max_share
    {state ["ZZ"]}                                   error, no institution in that state
    {min_share "abc"}                                error, must be numbers

### search_records

`{"query": "semiconductor"}` -> **594 records, exact=true**, 0.115% of the corpus.
by_university: mit 48, utaustin 26, gatech 24, uarizona 22, ttu 18.
by_department: Physics 92, Electrical & Computer Eng 78, Chemistry 64, General 55,
Materials Science & Eng 47.

`{"query": "quantum", "university": "mit", "year": [2020, 2025]}` -> **156, exact=true**.
Checked against a direct scan of the source JSON: 15+10+31+46+29+25 = 156.

`{"query": "machine learning"}` -> 5,090, **exact=false**, with the result carrying:
"UPPER BOUND, not an exact count. Multiple terms are intersected at institution x department x
year grain, so a match means that cell contains records with every term, not that one title
contains them all." Top department Data Science 1,640.

**Searches that return nothing** — three distinct kinds, each says which kind it is:

    {"query": "zzzqqx"}                     matched_records 0, terms.not_in_index ["zzzqqx"],
      note: "None of ['zzzqqx'] appears in 517,715 titles at least 5 times... Terms below that
      frequency are not in the index and cannot be distinguished from terms that never occur."
      (This is the honest limit of a df>=5 index and the tool says so rather than implying zero.)

    {"query": "crispr", "university": "caltech", "year": [1970, 1980]}
      matched_records 0, exact true, note: "Terms are in the index but no record survives the
      filters." — the term exists (403 records), the filter is what empties it.

    {"query": "the of and"}                 error: "No searchable term in query 'the of and'."

    {"query": "tardigrade cryptobiology"}   partial: 5 records on `tardigrade`, with
      not_in_index ["cryptobiology"] and a note saying it was ignored, not that it was absent.

Errors: unknown university key and unknown field both return an error plus did_you_mean/hint.

### similar_to

`{"university": "mit"}` (profile) -> penn_state 0.83, utaustin 1.183, rice 1.278, ncstate 1.306,
iowa_state 1.381. Each neighbour carries its raw axis values AND `axis_gap_in_sd`, so the reader
can see which axis the closeness came from.

`{"university": "njit"}` -> nearest is Missouri S&T at **2.505 sd**. That large a nearest-neighbour
distance is itself the finding: NJIT is +2.0 sd on site NRA share, +2.2 on graduate enrolment NRA,
+2.7 on foreign-name share, +2.5 on Chinese-name share and -1.15 on size. It has no close analogue
among the 105, and the numbers in the result show why rather than asserting it.

`{"university": "mit", "by": "field_mix"}` -> vt 0.0791, iowa_state 0.1055, la_tech 0.1072.
`{"university": "njit", "by": "origins"}` -> uconn 0.0014, utk 0.0021, uky 0.0025.
`{"university": "mit", "by": "scale"}` -> utaustin 0.287, penn_state 0.341, bu 0.386 —
compared_over 101, `excluded_for_missing_axes: [cu_boulder, montana_state, uconn, uky]`
(no NSF HERD R&D figure in the digest for those four).
`{"university": "hogwarts"}` -> error with did_you_mean.

## similar_to: axes, chosen from what is actually in universities_compact.json

I checked coverage across all 105 before choosing. Coverage is 105/105 for every `profile` axis:

    nra_site_figure 105/105     enrollment_ipeds.nra_pct 105/105   faculty.nra_pct 105/105
    name_origins    105/105     departments 105/105                records 105/105
    funding.rd      101/105     lca.total_lcas 100/105             unitid 103/105
    state            0/105  (not in the digest at all; find_departments gets state from
                             hd_names.csv instead, which is why only that tool has a state filter)

    profile   (z-scored Euclidean, 6 axes) nra_site_figure, grad_enrolment_nra_pct,
              faculty_nra_pct, foreign_name_pct, chinese_name_pct, log10_records
    field_mix (cosine) department record-count vector, the site's top-25 departments
    origins   (cosine) classified name-origin counts
    scale     (z-scored Euclidean) log10 records, log10 doctorates/year, log10 R&D dollars

The result always returns `axes`, `distance_measure`, `compared_over`,
`excluded_for_missing_axes`, `target_axes`, `axis_mean` and `axis_sd`, so the ranking can be
recomputed by hand from the payload. That was the point of the requirement and I took it
literally.

Two corrections I made after seeing real output:

  1. **origins** originally included the `other` bucket, which is 52-90% of every university's
     names. That made all 105 vectors near-parallel and the ranking was decided by rounding on
     one dominant axis. Now it compares the mix among *classified* origins only, and says so.
  2. **rpi, utah_state and utdallas report exactly 0 non-resident instructional staff** against
     non-zero staff totals (utdallas: 0 of 914, with 279 Asian). That is non-reporting, not a
     true zero, and it pulls those universities together on the faculty axis — utdallas's
     nearest neighbour is rpi. The tool now attaches a `data_quality` note whenever the target
     or a returned neighbour is one of them, naming them and saying part of the closeness is a
     reporting artefact. It does not silently drop them.

## Privacy decision on search_records

**Decided: the tool answers about fields, institutions and time. It cannot return a person.**

What that means concretely:
  - the index stores term -> counts per (institution, department, year). No title string, no
    author name and no repository URL is in the shipped artifact at all, so there is nothing
    to leak even under a crafted query.
  - author names are not tokenized and not searchable. A query for a surname returns whatever
    that string does as a *title* word, which for most names is nothing.
  - every result carries `searched` ("Title text ... Author names, abstracts, repository URLs
    and full text are NOT indexed and NOT searched") and `privacy` ("It never returns an
    individual record, title or author name ... queryable at /query.html").

Why this and not record output: the site already publishes these records, so aggregate counts
are not new exposure — but a chat tool that returned title+author rows would be a people-finder
built on top of a demographic study, reachable in one sentence by anyone, which is a different
artifact from the one the project is. Pointing at /query.html keeps the records available to a
person who wants them without making the assistant the instrument. The size constraint pushed
the same way, so nothing was traded off to get this; it is the same design.

This also closes the largest untrusted-text surface in the project. `build_chat_facts.py`
already refused to ship these titles for exactly this reason; the index is consistent with that
decision rather than a hole in it. `UNTRUSTED` is on every payload and institution/department
names still go through `ds.clean_text`.

## What I could not source, and other caveats

  - **data/processed/stem_records.parquet was unreadable here** — no pandas and no pyarrow in
    this environment. It is also stale (Apr 20 vs Aug 18 for the JSON) and 329 records short.
    I used `site/data/`, which is what `build_chat_facts.py` already reads. The 14 MB parquet
    figure in the brief is real but I could not open the file to confirm its contents.
  - **71 records carry no usable year** (stored as 0). They are in the index and counted in
    unfiltered totals, but are excluded from any year-filtered result. The count is reported as
    `records_without_a_year` in every search result's `index` block. One consequence visible in
    testing: the only pre-1990 "quantum" title is one of them, so a 1966-1975 filter correctly
    returns 0 rather than 1.
  - **Terms below df=5 are indistinguishable from terms that never occur.** The tool says this
    in the zero-result note rather than reporting a bare 0.
  - **Multi-term queries are upper bounds**, flagged `exact: false`. Exact multi-term matching
    needs record-level postings, which is the 5.69 MB that does not fit.
  - `find_departments` has no `pooled` toggle — the window is always pooled, because that is
    what "50+ doctorates in the last five years" means. Stated in `query.pooling` on every
    result. I did not add the parameter since it was not in the brief.
  - **chat_data/.gitignore does not list search_index.bin.** I did not edit it (shared file,
    three agents writing to that directory). It should get one line so a 3.39 MB generated
    binary does not enter git; the whole directory is currently untracked, so nothing is staged
    yet. Rebuild command: `python3 scripts/build_chat_search_index.py` (~20 s).

## Performance

    cold (first call in a container)   search_records 189 ms | find_departments 226 ms
                                       similar_to 1 ms
    warm                               search_records 2 ms | find_departments 11-20 ms
    tool result payloads               4.1-6.9 kB of JSON

Cold cost is the one-time artifact load: 165 ms to inflate and map search_index.bin, ~210 ms
for ds.load_index(). Both are lazy, so a container that never searches never pays.

## Files

    cloud/chat/tools_search.py               new, the module (SCHEMAS + IMPL)
    scripts/build_chat_search_index.py       new, the index builder
    cloud/chat/chat_data/search_index.bin    new, 3.39 MB generated artifact

Not touched: tools.py, blocks.py, handler.py, prompt.py, data_store.py, site/chat-widget.js,
pipeline/. Nothing deployed, nothing committed.
