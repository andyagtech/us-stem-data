# Five industries the country cannot offshore

## Why this file exists

Readers ask about specific industries, not CIP codes. `/industries.html` and
its five pages answer for mining, petroleum, aerospace, batteries and nuclear.
This file carries what they say and, more importantly, what they must not be
read to say.

## The figures

IPEDS Completions, research doctorates, pooled 2015-2022. The national figure
across all fields in that window is **27.0%**, and every one of these five runs
above it.

| Industry | Share | Doctorates | Institutions | Federal access regime |
|---|---|---|---|---|
| Petroleum | **85.3%** | 943 | 16 | none by default |
| Artificial intelligence | **63.3%** | 8,891 | 122 | none for the field as such |
| Mining and metals | **56.4%** | 303 | 8 | none by default |
| Battery technology | **51.6%** | 6,738 | 113 | none by default |
| Aerospace | **42.6%** | 2,911 | 49 | export control (ITAR) |
| Nuclear | **32.8%** | 1,318 | 28 | access authorisation |

Petroleum at 85.3% is the highest share of any field on this site, above
Electrical Engineering.

## "Clearance" -- get this right, the audience will know

Three different regimes get run together under that one word. They are not the
same thing and you must not treat them as the same thing. Federal readers will
notice immediately.

- **Export control** (ITAR, 22 CFR 120-130; EAR, 15 CFR 730-774) limits access
  to controlled technical data to a **"U.S. person"**, defined at 22 CFR
  120.62: a citizen, a **lawful permanent resident**, or a protected individual
  under 8 USC 1324b(a)(3). **It is not a security clearance and it does not
  require citizenship.** A green-card holder needs no authorisation for it.
- **Access authorisation at a commercial reactor** (10 CFR 73.56) is a
  background investigation and fitness-for-duty determination for unescorted
  access. **Also not a security clearance**, and not citizenship-restricted on
  its face.
- **A security clearance** is eligibility for access to classified national
  security information, adjudicated under EO 12968 and SEAD 4. DOE's **L and Q
  access authorisations** (10 CFR 710) are of this kind and **do** require US
  citizenship. Very little doctoral work in these five industries is this.

Never say an industry "requires a clearance" unless it is the third one. The
site's pages say "export control" and "access authorisation" for exactly that
reason.

**Where the distinction actually bites.** IPEDS counts a permanent resident as
domestic, so every non-resident alien in these figures is on a temporary visa
and therefore outside the U.S.-person definition export control uses. That is a
statement about the rules, never about who was hired.

Do not build an argument out of comparing the restricted industries against the
unrestricted ones. The site used to pool them that way and the pooling was
dropped: five industries is far too small a sample to carry a causal claim, and
the regimes are too different from each other to pool at all.

## Where the American pipeline stops, and why it is the important table

Each industry page carries the same field at three award levels. It holds the
subject constant and varies only the level, and it is the most direct evidence
on this site for whether Americans are being trained for these roles.

AI and computer science, 2025:

| Level | Awarded to Americans | Share American | Total |
|---|---|---|---|
| Bachelor's | 48,813 | **88.9%** | 54,901 |
| Master's | 10,910 | **30.7%** | 35,488 |
| Doctorate | 756 | 37.7% | 2,007 |

Americans take nine in ten of the bachelor's degrees and three in ten of the
master's. The undergraduate pipeline is American. The graduate pipeline above
it is not, and the graduate degree is the one these industries hire from. The
same shape appears in petroleum, mining and the rest.

This is `/expansion.html`'s argument shown inside a single critical field. Give
it as such when a reader asks whether America is training its own people for
this work.

## The grid: a different question, a different page

`/industries/grid.html` does not measure a share, because there is nothing to
measure: electrician credentials are **0.2%** non-resident and lineworker
**0.3%**. These are American jobs held by Americans. The page counts instead,
and the counts are the point.

- **62** power plant technology credentials awarded in 2025, **in the entire
  country**, at **5** institutions.
- **78** nuclear power technology credentials, every level combined, **down
  54.1%** in ten years.
- 83,102 credentials across every programme on the page, **90.3%** of them to
  Americans.
- Lineworker is the one growing: up 39% in ten years, to 1,973.

**The caveat belongs with every one of those numbers.** IPEDS covers Title IV
institutions. A great deal of electrical and line work is learned in union or
employer apprenticeships -- IBEW and NECA among them -- that award no IPEDS
credential and appear nowhere in this data. For the trades these counts are a
FLOOR on the pipeline, not the pipeline. The power plant and engineering
numbers do not have that problem, because colleges award those credentials.

Never present the trades counts as the size of the workforce. They are the size
of the college-credentialled share of one year's new entrants.

## What these pages are NOT

- **A CIP code is a field of study, not an industry.** Nobody in this data is
  observed working anywhere. The mapping from field to industry is this site's,
  and each page lists the codes it used so a reader can argue with it.
- **There is no battery CIP.** The battery page is a declared proxy built from
  Materials Engineering (14.1801) and Materials Science (40.1001). It counts
  people who will never work on a battery and misses battery work done inside
  chemistry and chemical engineering. If a reader asks about batteries, say
  this before quoting 51.6%. The page itself says it in a box at the top.
- **Mining excludes geology on purpose.** 14.2101 and 14.2001 only. Adding the
  geosciences would multiply the cohort fifteenfold and drop the share to about
  35%, because most geologists never work in mining.
- **The regime note describes LAW, not hiring.** Neither page shows who was
  actually employed, under what authorisation, or whether they stayed.
- **Shares are of degrees awarded, not of the workforce.** A doctorate awarded
  in 2016 may have left the field or the country.
- **"Non-resident alien" is the IPEDS category**: a student on a temporary
  visa. Permanent residents count as domestic.

## Two numbers that look wrong together

Each industry page shows a pooled headline (2015-2022) and a line running the
full published history. They will not match -- petroleum reads 85.3% pooled and
72.8% in 2025 -- because they answer different questions. The page says so
under the chart. If a reader spots the gap, that is the explanation.

## Where to send people

- `/industries.html` -- all five compared, and the citizenship-gate section.
- `/industries/petroleum.html`, `/industries/mining.html`,
  `/industries/battery.html`, `/industries/aerospace.html`,
  `/industries/nuclear.html` -- each with its programmes, its institutions and
  its trend.
- `/index.html#clearance` -- the computer science against information security
  comparison these pages extend.
- `/rankings.html` -- the same question by programme rather than by industry.

Data: `/data/critical_industries.json`, built by
`scripts/build_critical_industries.py`.
