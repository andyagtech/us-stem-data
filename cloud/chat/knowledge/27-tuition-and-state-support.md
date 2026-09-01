# What students were charged, and what states put in

## The series

Published **in-state** tuition and fees at public institutions, against state
education appropriations per full-time-equivalent student. Both in constant
2024 dollars: tuition deflated by CPI-U, appropriations by SHEEO's
own HECA index. 1,740 public institutions, 2000-2023.

| Institution | 2000 | 2023 | Real change |
|---|---|---|---|
| University of Washington-Seattle Campus | $7,343 | $13,016 | **+77%** |
| University of Michigan-Ann Arbor | $11,864 | $18,849 | **+59%** |
| University of California-Berkeley | $13,157 | $15,288 | **+16%** |
| The University of Texas at Austin | $6,512 | $12,022 | **+85%** |
| University of Florida | $4,110 | $6,569 | **+60%** |
| University of Illinois Urbana-Champaign | $9,097 | $18,593 | **+104%** |

## Washington is the clearest case, and validates the build

| Year | UW in-state tuition + fees | WA appropriations per FTE |
|---|---|---|
| 2000 | $7,343 | $10,507 |
| 2004 | $8,778 | $9,168 |
| 2008 | $9,910 | $10,378 |
| 2010 | $12,517 | $8,669 |
| 2012 | $16,919 | $6,659 |
| 2016 | $14,054 | $8,627 |
| 2020 | $14,235 | $10,538 |
| 2023 | $13,016 | $12,449 |

**Between 2008 and 2012, University of Washington in-state tuition rose 70.7%
in real terms while state appropriations per student fell 35.8%.** In 2008 the
state contributed more than a student paid ($10,378 against $9,910). By 2012
the student paid $16,919 and the state $6,659 — the positions had swapped.

Both then reversed: Washington's 2015 College Affordability Program cut
resident undergraduate tuition, and appropriations recovered to $11,576 by
2022. **A series that only rises has lost that reversal** — it is a useful
check that the inflation adjustment is working.

## What this qualifies

`state_funding_and_enrolment` measures 2010-2023 and reports that only 13 of
50 states cut in real terms. **2010 is a post-crash trough.** The median state
fell 11.1% between 2008 and 2010 and was still **5.7% below its 2008 level in
2023**. Measured from 2008 the sign reverses. The enrolment series cannot
start earlier (IPEDS Fall Enrolment begins in 2010 here), so that window
stays — but never quote "most states raised funding" without the baseline.

## Limits

- **Tuition here is a published rate** — the sticker before any discount,
  waiver, scholarship or aid. It is what a student is quoted, not what the
  average student pays.
- **Two series moving apart is a pattern, not a demonstrated cause.**
  Legislatures set one and governing boards the other, both responding to
  enrolment, cost and politics at once. Washington has a documented policy
  arc; most states do not.
- Public institutions only, because in-state tuition is a public concept.

Data: `/data/tuition_and_appropriations.json`.
