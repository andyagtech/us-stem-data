# The local wage test, and the domestic series

## The national median was flattering the filings

The earlier figure compared each filing to the **national** median for its
occupation. H-1B filings are not spread evenly: they concentrate in
California, Texas, New York and Washington. Measured against the median for
the occupation **in the worksite state**, on the same 565,966
filings:

- Below the **national** median: 70.8%
- Below the **local** median: **78.7%**

Finer still, against the median in the **metropolitan area** where the work
is, on the 517,103 filings whose county resolves to one:

| Yardstick | Filings | Promising less |
|---|---|---|
| National | 565,966 | 70.8% |
| Worksite state | 565,966 | 78.7% |
| **Worksite metro** | 517,103 | **84.0%** |

**84.0% is the figure to quote.** On that same metro
subset the national comparison gives 70.0%,
so it understates by fourteen points.

**The progression is itself the argument.** The more precisely the comparison
is localised, the worse the filings look — which is exactly what happens when
they cluster in expensive places. If that ordering ever inverts, the crosswalk
is wrong, and a test holds it.

The metro chain is deterministic: the application records a worksite **county**,
and the Census delineation file maps counties to metropolitan areas. **No city
name or postcode is guessed anywhere.** The 9% whose county resolves to no
metro area keep the state comparison rather than being dropped or assigned one.

| State | Filings | Below national | Below local | Swing |
|---|---|---|---|---|
| CA | 103,494 | 37.7% | **70.3%** | +32.6 |
| TX | 84,796 | 81.7% | **79.1%** | -2.6 |
| NY | 42,075 | 56.0% | **77.2%** | +21.2 |
| WA | 34,702 | 57.2% | **84.3%** | +27.1 |
| NJ | 32,165 | 66.5% | **74.7%** | +8.2 |
| IL | 25,148 | 81.5% | **79.5%** | -2.0 |
| GA | 22,214 | 83.1% | **80.2%** | -2.9 |
| NC | 21,976 | 79.6% | **80.1%** | +0.5 |

California is the extreme: **37.7% below the national median, 70.3% below the
Californian one** — a 32.6-point swing. Washington +27.1, New York +21.2. Low
wage states move the other way (Florida −7.8, Georgia −2.9), which is the
check that this is measuring local cost rather than a coding error.

| Wage level | Below national | Below local |
|---|---|---|
| Level I | 99.3% | **99.8%** |
| Level II | 89.1% | **97.9%** |
| Level III | 53.1% | **72.9%** |
| Level IV | 19.6% | **16.5%** |

**Level III is the striking row.** It is nominally the *experienced* rate, and
nearly three in four filings at that level sit below the local median.

**Limits:** state, not metro — the application records a worksite state
reliably and a metro only by city and postcode, which needs a crosswalk with
its own errors. 60,558 filings whose occupation
has no published state median are counted unmatched rather than given the
national figure. What was **promised**, not paid; filing low is lawful.

## Twenty years of the domestic side

Unemployment rate by nativity, CPS annual averages:

| Year | Foreign born | Native born | Gap |
|---|---|---|---|
| 2008 | 5.8% | 5.8% | +0.0 |
| 2012 | 8.1% | 8.1% | +0.0 |
| 2016 | 4.3% | 5.0% | -0.7 |
| 2020 | 9.2% | 7.8% | +1.4 |
| 2024 | 4.2% | 4.0% | +0.2 |

The two track each other closely — the gap is under a point in most years and
went the *other* way in the mid-2010s. The pandemic is the exception (+1.4 in
2020), when foreign-born workers were concentrated in the sectors that shut.

**Do not read this as a displacement measure.** Nativity pools naturalised
citizens with visa holders, and an aggregate unemployment rate says nothing
about any occupation. It is context for the occupational shares, not evidence
about them.

Data: `/data/local_wage_comparison.json`, `/data/nativity_labour.json`.

## Occupation by nativity, now a series

The foreign-born share of **computer and mathematical occupations** runs from 2007,
parsed from Table 4 of every archived BLS release. Within one occupational
classification, 2011 to 2019, it rose from 21.6% to 26.8%. The latest year reads
29.0%.

**The series has breaks, and a change may only be read within one regime:**

- **2011** — the 2010 Census occupational classification was introduced; 2011 is
  not strictly comparable with earlier years.
- **2020** — the 2018 classification was introduced; same caveat.
- **2025** — annual averages are 11-month averages excluding October (the federal
  shutdown), and BLS says they are not strictly comparable with other years.
- **Every January** — new population controls, with no revision of earlier years.

So the rise to 29.0% in 2025 crosses two breaks at once and **must not be quoted
as a one-year jump**. The 21.6% → 26.8% rise over 2011–2019 is the clean
comparison. Whether it moved *because of* the visa series is not something two
aggregate series can show; they can be set side by side, and that is all.

Data: `/data/nativity_labour.json` → `occupation_series`, `occupation_series_breaks`.

