# The queue, and the institution as the unit

## 1. How long the employment queue actually is

State Department historical final action dates, FY1992-2023. The wait is the
gap between the priority date being acted on and the month acting on it.

| Country | EB-2 | EB-3 |
|---|---|---|
| All chargeability areas | 1.2 yr | 3.3 yr |
| China | 4.2 yr | 4.0 yr |
| India | 12.7 yr | 14.7 yr |
| Philippines | 1.2 yr | 3.3 yr |

India's queue is not a constant. September of each year:

| Year | EB-2 | EB-3 |
|---|---|---|
| 1998 | 1.3 yr | 2.8 yr |
| 2004 | C | C |
| 2007 | 3.4 yr | U |
| 2010 | 4.3 yr | 8.7 yr |
| 2013 | 5.2 yr | 9.9 yr |
| 2016 | 11.5 yr | 11.5 yr |
| 2019 | 10.3 yr | 14.2 yr |
| 2023 | 12.7 yr | 14.7 yr |

**India's EB-2 was current -- no queue at all -- through 2004.** It passed three
years by 2007, five by 2013, ten by 2016. Every year of it is a year in which
leaving the employer means starting over, which is what makes the dependence on
`19-enrolment-and-leverage.md` concrete rather than theoretical.

**Limits, which matter here:**
- The wait is **already served** by the person now reaching the front. It is
  **not a forecast** for someone filing today; where a queue is growing the
  eventual wait is longer than any figure here.
- **"C" is current (no queue). "U" is unavailable -- an unknown wait, NOT
  zero.** Both are stored as a status with a null wait so neither can be
  averaged in. September 2022 reads C for India because unused numbers spilled
  over; read the run, never one month.

## 2. Count the institution, not the traced dollar

Federal R&D at institutions where a majority of graduate students hold a
temporary visa, counted three ways:

| Counted at | Institutions | Federal R&D | Share of matched | Students |
|---|---|---|---|---|
| Doctoral | 106 | $12.5bn | 21.5% | 70,197 |
| Master&#39;S | 109 | $24.1bn | 41.1% | 128,885 |
| Both combined | 108 | $19.4bn | 32.9% | 210,870 |

The unit of analysis is **the institution and its graduate operation in bulk**.
HERD records expenditure at the institution and never at a student, so the
defensible sentence is "federal money is at these institutions", never "federal
money paid these students". That is a limit on the wording, not on the finding.

Report all three levels when asked. The doctoral figure is the one connected to
research assistantships; the master's figure is the larger population and the
larger share of federal R&D; the combined figure is the institution as a whole.

Data: `/data/visa_bulletin.json`, `/data/enrolment_and_funding.json`.
