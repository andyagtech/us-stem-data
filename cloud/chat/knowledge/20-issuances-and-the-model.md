# The entry point, and where the master's is the model

## 1. Visa issuances, 1997-2024

Counted at the consulate, by nationality. The most current series in the
project -- State publishes through the last fiscal year, and monthly files run
further still (2025-10 to 2026-02).

| FY | F-1 | J-1 | H-1B | O-1 |
|---|---|---|---|---|
| 1997 | 266,483 | 179,598 | 80,547 | 3,345 |
| 2000 | 284,053 | 236,837 | 133,290 | 6,466 |
| 2005 | 237,890 | 275,161 | 124,099 | 6,712 |
| 2010 | 385,210 | 320,805 | 117,409 | 8,589 |
| 2015 | 644,233 | 332,540 | 172,748 | 13,865 |
| 2020 | 111,387 | 108,510 | 124,983 | 8,838 |
| 2024 | 400,737 | 322,820 | 219,659 | 19,457 |

H-1B issuances went 80,547 -> 219,659. **O-1 rose
482%**, which is the uncapped route
and the reason the O-visa page exists.

Leading origins in 2024:

| F-1 origin | Issuances | H-1B origin | Issuances |
|---|---|---|---|
| India | 86,067 (21.5%) | India | 150,647 (68.6%) |
| China - mainland | 82,654 (20.6%) | China - mainland | 31,735 (14.4%) |
| Vietnam | 18,454 (4.6%) | Philippines | 3,562 (1.6%) |
| Korea, South | 14,786 (3.7%) | Korea, South | 2,289 (1.0%) |
| Nepal | 13,184 (3.3%) | Mexico | 1,954 (0.9%) |

**India is 68.6% of all H-1B issuances.** That is the single
most concentrated figure in the project, and it is the same nationality facing
the longest green-card queue -- see `19-enrolment-and-leverage.md`.

**Limits:** an issuance is **not a person and not an arrival**. One person may
be issued several visas over the years, and a visa is permission to travel and
seek admission, not admission itself. Never convert issuances into people.
FY2020-21 are depressed by consular closures, not by policy.

## 2. Where the master's is the model

Nationally, temporary-visa holders are **46.8%**
of full-time S&E&H master's enrolment and
**44.5%** of doctoral. The institution-level
figures are where the pattern is unmistakable:

| Institution | Visa holders | Share |
|---|---|---|
| Harrisburg University of Science and Technology | 1,591 of 1,651 | **96.4%** |
| Southern Arkansas University | 216 of 225 | **96.0%** |
| Gannon University | 285 of 299 | **95.3%** |
| Illinois Institute of Technology | 1,995 of 2,120 | **94.1%** |
| University of Central Missouri | 2,652 of 2,862 | **92.7%** |
| Clark University | 668 of 724 | **92.3%** |
| University of Bridgeport | 617 of 674 | **91.5%** |
| University of Arkansas at Little Rock | 241 of 265 | **90.9%** |

This is the concrete form of the "paid-for visa" argument: several institutions
run science and engineering master's programmes that are over ninety percent
temporary-visa, at scale -- Central Missouri on 2,862 students, Illinois Tech
on 2,120.

**Limits:** enrolments, not degrees, on an S&E&H basis -- **not comparable**
with the IPEDS core-STEM degree rankings. GSS reports one row per
organisational unit and rows must be summed to the institution. Share rankings
apply an enrolment floor (200 students, 331 qualify)
because small programmes give meaningless percentages. Permanent residents
count as domestic, so these are a floor on the foreign-born share. Single year.

Data: `/data/visa_issuances.json`, `/data/gss_institution_ranking.json`.
