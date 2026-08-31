# What H-1B enforcement finds

## Why this file exists

Every survey in this project reaches **doctorate holders**. The H-1B workforce
the leverage argument is about mostly holds a bachelor's or master's and works
in industry, and no survey here reaches it. DOL enforcement records do: one row
per investigation, employer named.

## The findings

| | |
|---|---|
| Investigations finding H-1B violations, 2000-2026 | **2,887** |
| Back wages agreed | **$123,435,007** |
| Employees covered | 13,640 |
| Average per employee | $9,049 |
| Civil penalties assessed | $11,699,452 |

### Enforcement intensity has fallen elevenfold

| Year | Cases | H-1B issuances | Cases per 10,000 |
|---|---|---|---|
| 2000 | 10 | 133,290 | **0.75** |
| 2004 | 99 | 138,965 | **7.12** |
| 2008 | 216 | 129,464 | **16.68** |
| 2009 | 289 | 110,367 | **26.19** |
| 2012 | 134 | 135,530 | **9.89** |
| 2016 | 110 | 180,057 | **6.11** |
| 2020 | 84 | 124,983 | **6.72** |
| 2024 | 52 | 219,659 | **2.37** |

### Largest findings by back wages

| Employer | Back wages agreed | Employees |
|---|---|---|
| Prince George'S County Public Schools | $4,222,146 | 1,046 |
| Advanced Prfessional Marketing, Inc. | $2,865,216 | 156 |
| Patni Computer Systems Inc. | $2,402,757 | 607 |
| Computech Corporation | $2,250,000 | 36 |
| Byton North America Corporation | $1,749,185 | 76 |
| Globalcynex, Inc. | $1,683,584 | 343 |
| Populus Group, Llc | $1,159,056 | 596 |
| Metropolitan Center For Mental Health | $1,113,678 | 15 |

### Industries

| Industry | Cases | Back wages |
|---|---|---|
| Custom Computer Programming Services | 599 | $27,572,478 |
| Computer Systems Design and Related Services | 267 | $14,418,349 |
| Other Computer Related Services | 205 | $7,593,534 |
| Computer Systems Design Services | 207 | $7,156,102 |
| Other Scientific and Technical Consulting Services | 131 | $7,065,813 |
| Temporary Help Services | 52 | $5,076,579 |

## The limit, which is the most important line in this file

**This is a floor, never a rate.** These are violations that were *found*, which
requires a complaint to be filed or an investigation to be opened.

So a falling line is **not** evidence of improving compliance. It is equally
consistent with fewer investigations, or with fewer complaints from workers
whose right to remain in the country depends on the employer they would be
complaining about -- which is exactly what `19-enrolment-and-leverage.md` and
`23-the-queue.md` describe. **This data cannot say which**, and the ambiguity
must not be collapsed in either direction. Do not say "violations fell". Say
"findings fell", and give both readings.

Other limits:
- Back wages are **"agreed to pay"** -- a finding and an agreement, not money
  proven collected.
- Cases are dated by the end of findings; an investigation may cover several
  earlier years.
- Employers are grouped on the filed legal name with case and whitespace
  normalised **only**. Nothing is fuzzy-matched, so two spellings of one company
  remain two rows and any company total is a floor.

Data: `/data/h1b_enforcement.json`, built by `scripts/build_h1b_enforcement.py`
from the WHISARD extract in `data/WHD_enforcement.zip` (191 MB, not in git).
