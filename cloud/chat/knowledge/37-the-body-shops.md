# The firms that supply H-1B workers to other companies

## Why this file exists

Readers ask who actually uses H-1B, and the published "top employers" lists
answer Amazon, Google, Microsoft. That is true and it is not where the volume
sits. `/bodyshops.html` separates the firms whose business **is** supplying
workers from the firms that hire them for their own work -- and does it from
the employers' own answers on their own certified filings, not from anyone's
opinion about a company.

## What "body shop" means here, exactly

Trade slang, not a legal category, and on this site it is a **test with four
parts**. Every part is the employer's own answer, made under penalty of perjury
on a certified Labor Condition Application:

1. Its own six-digit industry code is **5613** (employment services: staffing,
   temp help, PEO) or **5415** (computer systems design and related services).
2. More than **50%** of its certified applications answer yes to the **H-1B
   dependency** question (the statutory test at 8 U.S.C. 1182(n)(3)).
3. More than **50%** answer yes to the **secondary entity** question -- the
   worker will sit at another company's worksite. This is the body shop in one
   field: the firm sponsors the visa, another firm gets the work.
4. At least **50** certified applications, so a two-filing firm cannot top the
   table.

Supplying contract workers is lawful. Being H-1B dependent is lawful. Placing a
worker at a client's site is lawful. Meeting this test says what a firm does,
never that it did anything wrong.

> Guidance, not text to repeat: a reader often arrives assuming the label
> implies a crime. Correct that in your own words, and never phrase it as
> advice to the reader about how to read the site.

## The figures

Source: DOL OFLC H-1B disclosure files, 15 quarterly files, FY2022 Q4 through
FY2026 Q3. Certified applications only.

| | |
|---|---|
| Certified applications read | **2,236,477** |
| Positions they cover | 3,914,580 |
| Placed at another company's worksite | **20.1%** |
| At an H-1B-dependent employer | 25.4% |
| Filed at wage Level I or II | **60.6%** |
| Filed by a self-declared wilful violator | 536 |
| Firms meeting all four parts of the test | **1,203** |
| Their share of all certified applications | **12.5%** |

The largest by certified applications:

| Firm | Applications | Dependent | Placed at a client | Level I-II | Median wage | States |
|---|---|---|---|---|---|---|
| Tata Consultancy Services | 33,258 | 99.9% | 87.4% | 84.4% | $85,530 | 51 |
| Infosys | 27,581 | 99.6% | 67.4% | 60.6% | $92,581 | 41 |
| HCL America | 12,641 | 99.9% | 76.6% | 52.6% | $108,468 | 46 |
| Wipro | 9,779 | 99.3% | 75.0% | 87.3% | $87,776 | 40 |
| LTIMindtree | 9,148 | 99.8% | 80.6% | 93.3% | $102,877 | 42 |
| Compunnel Software Group | 9,145 | 99.7% | 98.3% | 81.5% | $109,500 | 48 |

## Same job title, two prices

"Placed workers are paid less" invites the obvious objection: they must be
doing different work. So the occupation is held still and each title is split
in two. For **Software Developers**:

| | Placed at a client | Hired directly |
|---|---|---|
| Median wage | **$105,997** | **$146,893** |
| Filed at wage Level I-II | **85.7%** | 52.9% |

A **27.8%** gap within one job title. The same comparison runs for eleven other
occupations on the page; IT project managers and data scientists are both near
27-28%.

Wage level is the tier the employer chose: Level I is the entry rate for the
occupation, Level IV the experienced rate. **Filing at Level I or II is lawful,
and it is also the cheapest lawful option.** Never call it a violation.

## Do not borrow the local-wage figure for these firms

`32-local-wages-and-domestic-series.md` says **84.0% of certified filings
promise less than the local metro median**. That is **every** certified H-1B
filing in the country, not these firms. It is not a body-shop statistic, and
pulling it into an answer about body shops -- "for example, 84%..." -- tells
the reader something the data has not shown.

The body-shop equivalents are the two in this file, and they are the ones to
quote here: **85.7% of placed software-developer applications are filed at wage
Level I or II against 52.9% of direct ones**, and the **27.8% median gap within
that one job title**. If you want both figures in one answer, label each with
the population it describes.

## How concentrated the programme is

From the USCIS H-1B Employer Data Hub, fiscal 2009-2023 (`/bodyshops.html#concentration`):

- **368,825** employers received **1,675,026** initial approvals.
- **340,672** of them got five or fewer across fifteen years.
- The ten largest took 11.2%; the largest two hundred took 32.7%.

## Enforcement: the finding is the absence

- **Five** employers are currently barred from H-1B in the entire country.
- **USCIS publishes no list** of barred employers; it acts on DOL debarments.
- **ICE / SEVP publishes no list** for STEM OPT.
- The reported Cognizant PERM suspension traces only to the DOL Inspector
  General's own public statements -- **no DOL instrument, no Federal Register
  document, no entry on any list**. The Cloudera suspension is verified through
  an official DOL news release. State this difference precisely if asked.
- A **suspension** pending investigation is not a debarment and appears in no
  published list, so **absence from the debarment list is not evidence that a
  firm is in good standing**. Say this whenever a reader reads the short list
  as reassurance.

For what enforcement does find when it looks, use `24-enforcement.md` -- the
WHD investigation record, which is a floor and never a rate.

## The limits, which must travel with every figure

- **Positions are not people, and applications are not hires.** A certified LCA
  is permission to employ at a stated wage. Every figure here is a ceiling on
  intent. The USCIS approvals are the closer measure of people.
- **Counted by application, not by position.** One application can cover forty
  workers: Grandison Management files 40 positions per application where
  Microsoft files 1.4. Counting positions would hand every share on the page to
  the bulk filers.
- **Industry, dependency, wilful-violator and secondary-entity are all
  self-reported.**
- **Names are matched as filed.** A firm filing under several entity names
  appears as several firms, so any single firm's total is a floor.
- **FY2022 and FY2026 are missing quarters**, and the missing quarter is rarely
  average: January to March is H-1B cap season and the busiest of the four.
  Quote shares for those years, never counts.
- The occupation comparison holds the **job title** constant. It does not hold
  seniority, metro area or employer size constant.

Data: `/data/visa_bodyshops.json` and `/data/visa_staffing.json`, built by
`scripts/build_visa_bodyshops.py` and `scripts/build_visa_staffing.py`.
