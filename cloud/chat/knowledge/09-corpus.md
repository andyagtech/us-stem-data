# What the corpus is, and how it was built

## Scope

Dissertation and thesis records harvested over OAI-PMH from institutional
repositories at roughly a hundred US universities, across ten repository
platforms (bepress, DSpace in several versions, Hyrax, Figshare, EPrints,
Invenio, TIND, Blacklight, Esploro). Each record carries at minimum a title,
author, date and department; most carry a degree level.

This corpus supports **department-level and name-level** analysis, which IPEDS
cannot do — IPEDS reports institution by CIP code, never by department name or
individual. That is the reason the corpus exists.

## What it is not

It is **not** a census. A university's record count reflects what its repository
publishes and how completely the harvest reached it. Repositories differ in what
they expose, when they started, and whether they include master's work,
undergraduate honours theses, faculty articles, or datasets alongside
doctorates. Some records predate reliable metadata entirely.

For counts of degrees awarded, IPEDS is the authority and the corpus is not.
Never present a record count as a degree count, and never rank universities by
record count.

## Two independent measurements

The site carries two things that are easy to confuse because they sit on the
same pages:

1. **IPEDS-derived NRA shares** — federal, authoritative, visa status, available
   by institution and CIP field and year. Every headline share is this.
2. **Corpus-derived department and name analysis** — richer in grain, weaker in
   authority, and resting on name-origin estimation for anything demographic.

When both are on screen, be explicit about which one a number came from. When
they disagree, the IPEDS figure is the one to trust, and the disagreement is
usually a coverage artifact in the corpus rather than an error in either.

## Known coverage caveats

Some repositories were harvested before the pipeline captured issued dates
correctly, so their year distributions are under repair. Degree-level labels are
complete for most repositories and substantially incomplete for a few. Both
issues affect the corpus only — no IPEDS-derived figure depends on either.

`/quality.html` carries the current state of coverage. Send readers there rather
than reciting caveats from memory, because coverage changes as harvests improve
and this file does not.
