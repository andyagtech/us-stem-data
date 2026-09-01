# Waypoints, origins, and what the visa data cannot tell you

## The question that has no answer

**Country of birth is not published for any nonimmigrant classification.**
Not TN, not H-1B, not F-1, not L-1, not O-1. Every visa and admission series
in this project is by **citizenship**. A naturalised citizen of any country is
indistinguishable from a native-born one, everywhere in the data.

So "how many TN entrants from Canada were born elsewhere" **cannot be
answered**, and no amount of work on the visa tables will change that. Say
that plainly rather than estimating.

## The adjacent question that does have an answer

DHS publishes permanent residents twice: by country of **birth** and by
country of **last residence**. Where they disagree, people lived somewhere
that was not their birthplace before entering the United States.

| Arrived FROM more than were BORN there, FY2023 | From | Born | Gap | Share |
|---|---|---|---|---|
| Canada | 18,590 | 11,870 | +6,720 | **36.1%** |
| United Arab Emirates | 4,810 | 1,840 | +2,970 | **61.7%** |
| United Kingdom | 12,250 | 9,720 | +2,530 | **20.7%** |
| Germany | 5,950 | 4,550 | +1,400 | **23.5%** |
| Spain | 4,620 | 3,350 | +1,270 | **27.5%** |
| Australia | 3,810 | 2,790 | +1,020 | **26.8%** |

**36.1% of people obtaining US permanent residence from Canada were born
somewhere else** — 18,590 arrived from Canada against 11,870 born there. That
is not a one-year artifact: the share has sat near a third every year on
record except the pandemic dip.

The other side of the ledger:

| Born there, last lived elsewhere | From | Born | Gap |
|---|---|---|---|
| Mexico | 150,490 | 180,530 | -30,040 |
| Philippines | 42,360 | 49,200 | -6,840 |
| India | 72,310 | 78,070 | -5,760 |
| El Salvador | 20,890 | 26,210 | -5,320 |
| Afghanistan | 25,590 | 30,300 | -4,710 |

## What the Canada surplus is made of

The headline is a total, and the total hides the mechanism. Broken down by
class of admission, FY2023:

| Class | Gap | Share of surplus |
|---|---|---|
| Immediate relatives of U.S. citizens | +3,670 | 55% |
| Family-sponsored preferences | +1,560 | 23% |
| Employment-based preferences | +1,150 | 17% |
| Diversity | +350 | 5% |
| Refugees and asylees | +0 | 0% |
| Other | -20 | -0% |

**It is predominantly a family route.** Immediate relatives of US citizens and
family-sponsored preferences account for 78% of Canada's surplus; employment
preferences are 17%; refugees and asylees are **zero**.

That matters for how the finding can be used. A waypoint whose surplus sits in
family admission is a different phenomenon from one whose surplus sits in
employment, and quoting the 36% without the composition invites the wrong
reading in either direction.

## The limit that matters most here

**These are two separate totals, not a cross-tabulation.** No individual is
traced from a birthplace to a residence. Canada's +6,720 surplus and India's
−5,760 deficit cannot be linked, however neatly they appear to match. Any
sentence of the form "N of Canada's surplus were born in India" is
unsupported.

And this covers **permanent residents**, not TN holders — a different
population under different law.

## Refugee and asylee admissions

| Year | Refugee arrivals |
|---|---|
| 1980 | 207,120 |
| 1990 | 122,070 |
| 2000 | 72,170 |
| 2010 | 73,290 |
| 2020 | 11,840 |
| 2023 | 60,050 |

Peak **207,120 in 1980**; low 11,450; 60,050 in FY2023. Leading FY2023
nationalities: DR Congo 18,080, Syria 10,780, Afghanistan 6,590.

**Refugee admission is a policy ceiling**, set annually by presidential
determination. The series tracks decisions in Washington, not demand — a fall
is a policy choice and must never be read as fewer people seeking admission.

**Refugees and asylees are counted at different moments and are never summed
here**: a refugee is admitted from abroad after approval; an asylee is already
in the country when the grant is made.

Data: `/data/origin_vs_residence.json`, `/data/humanitarian_admissions.json`.
