# Where the balance shifted, and where it leads

Two findings that belong together. The first says the change in graduate STEM
happened at **master's** level, not the doctorate. The second says the visa
category the first one counts is, for most of the people in it, a step toward
permanent residence rather than a temporary stay.

## 1. The shift is at master's level

Non-resident share of core-STEM degrees conferred, IPEDS, 1995-2025:

| Year | Master's | Doctorate | Graduate combined |
|---|---|---|---|
| 1995 | 24.4% | 32.7% | 26.4% |
| 2000 | 28.0% | 31.3% | 28.7% |
| 2005 | 29.9% | 37.1% | 31.4% |
| 2010 | 29.0% | 36.8% | 30.6% |
| 2015 | 36.0% | 37.5% | 36.3% |
| 2020 | 37.9% | 39.8% | 38.2% |
| 2025 | 45.9% | 37.5% | 44.8% |

| Level | 1995 | 2025 | Change | Non-resident | Domestic |
|---|---|---|---|---|---|
| Master's | 24.4% | 45.9% | **+21.5 pts** | +658% | +189% |
| Doctorate | 32.7% | 37.5% | +4.8 pts | +115% | +74% |
| Graduate | 26.4% | 44.8% | +18.4 pts | +499% | +164% |

The doctorate peaked at 40.1% in
2021 and has fallen since. **The master's has not
turned.** If someone cites only the doctorate figure, they are looking at the
level where the shift is smallest and already receding.

Domestic output rose at both levels across the period, so this is a change in
share, not an American retreat. Say both.

## 2. The visa category is a route to settlement

IPEDS "non-resident alien" is a **visa** category, not an immigration outcome.
A permanent resident is counted under their race and appears as *domestic* in
the table above. So those lines understate the foreign-born share, and they say
nothing about where the visa holders go.

The SDR follows them. Of those who earned a US doctorate on a temporary visa:

| Now | Share |
|---|---|
| Naturalised US citizen | **36.4%** |
| Permanent resident | 21.9% |
| Still on a temporary visa | 9.8% |
| Living outside the US | 31.3% |

**58.3% now hold citizenship or permanent residence.** Of those who
stayed in the country, 86% reached one or the
other. Naturalisation is the single largest outcome -- larger than leaving.

So a non-resident share of 44.8% of graduate STEM
degrees is not a count of visitors passing through. It is the entry point of a
route to permanent settlement.

## Limits, which are not optional

- **Counts are degrees, not people.** A person earning a master's and then a
  doctorate is counted twice; first majors only, CIPCODE 99 rollups excluded.
- **The transition is measured at doctorate level only.** The SDR does not
  follow master's recipients, so applying 58.3% to the much larger
  master's population is inference, not measurement. Say so.
- **The SDR spans every cohort from the 1970s**, so the stay/leave balance
  describes the whole period. Recent graduates have had less time to
  naturalise, which if anything understates the eventual rate.
- Two IPEDS schema breaks are handled in the builder: residency columns renamed
  in 2008, and doctorate award level 9 becoming 17 in 2010 with institutions
  migrating across 2008-09 (both codings must be summed in those two years).
  The doctorate line reproduces the independent `long_series` index within 0.3%
  in every overlapping year.

Data: `/data/graduate_balance.json` (`scripts/build_graduate_balance.py`) and
`/data/doctorate_outcomes.json`.
