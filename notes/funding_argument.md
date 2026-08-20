# The funding argument: what the federal data actually supports

Written 2026-08-20. Every figure here is derived from a federal collection and
reproducible from the scripts named. Where a claim is an inference rather than a
measurement, it says so.

---

## The strongest single finding

**Three in four international science and engineering doctorate recipients are
paid for by an assistantship. Barely half of American ones are. And Americans
are more than four times as likely to be funding themselves.**

NSF Survey of Earned Doctorates, Table 4-1, 2024. Science and engineering:

| Primary source of support | US citizen / PR | Temporary visa | Gap |
|---|---|---|---|
| Research assistantship | 35.4% | **53.6%** | +18.2 |
| Teaching assistantship | 17.7% | 22.4% | +4.7 |
| **Assistantships combined** | **53.1%** | **76.0%** | **+22.9** |
| Fellowship or scholarship | 27.6% | 17.4% | −10.2 |
| **Own resources** | **16.0%** | **3.5%** | **−12.5** |

n = 25,660 citizens and permanent residents, 15,497 temporary visa holders.

This is the piece the site was missing. Everything else measures *composition* —
who received the degrees. Composition cannot show that anyone was prioritised,
because it says nothing about who paid. This does.

**Why the SED is hard to dismiss.** It is a census, not a survey of opinion:
essentially every research doctorate recipient in the United States completes it
before graduating, and institutions are required to administer it. It is the
same instrument NSF uses to produce the official count of American doctorates.

## The gap holds in every field

| Field | Assistantships, citizen | Assistantships, visa | Gap | Citizens self-fund at |
|---|---|---|---|---|
| Interdisciplinary | 54.3% | 80.2% | +25.9 | 3.8× |
| Engineering | 57.7% | 82.4% | +24.7 | 2.6× |
| Computer & information sciences | 59.2% | 83.1% | +23.9 | **5.5×** |
| Health sciences | 31.4% | 53.8% | +22.4 | 4.1× |
| Education | 22.1% | 44.4% | +22.3 | 2.5× |
| Psychology | 45.5% | 65.3% | +19.8 | 2.7× |
| Business | 29.1% | 48.0% | +18.9 | 4.6× |
| Biological & biomedical | 48.7% | 66.1% | +17.4 | 2.4× |
| Physical sciences | 74.2% | 86.7% | +12.5 | **6.0×** |
| Social sciences | 44.6% | 56.4% | +11.8 | 5.0× |

Not one field runs the other way. That consistency is what makes it an argument
rather than an anecdote — it is not a quirk of computer science.

## The scale of the public money

NSF Graduate Students and Postdoctorates Survey, 2024:

- **274,601** full-time doctoral students
- **67,936** — 24.7% — have federal support as their primary source
- **52,428** are federally funded research assistants
- **46% of all doctoral research assistantships** are federally funded
- By agency: NIH 22,824 · NSF 19,229 · DoD 6,532 · DOE 5,320
- Only **8.8%** are self-supporting

Research assistantships are the largest federally funded category by a wide
margin, and the RA gap between citizens and visa holders is the largest gap in
the SED table. Those two facts sit together well.

**The limit, stated plainly.** GSS gives federal-versus-institutional funding but
not citizenship. SED gives citizenship but not whether a given assistantship is
federal or institutional. **The two cannot be multiplied.** Doing so would assume
the federal share of assistantships is identical for both groups, which nothing
measures. Anyone quoting "X federally funded international students" has invented
the number.

What can be said: the funded route through a doctorate runs mostly through
assistantships; assistantships are heavily federally funded in aggregate; and
international students take that route at far higher rates than citizens do.

## The complementary argument: who the expansion was built for

IPEDS Completions, core-STEM, 2012 → 2025:

- Master's seats added: **159,213**. To non-residents: **95,938 — 60.3%**
- Domestic master's: +68%. Non-resident master's: **+264%**
- Doctorates added: 10,335. To non-residents: 4,102 (39.7%)

The master's figure is the strong one. At doctorate level the split runs the
other way and should not be quoted for this argument.

## Sustained concentration

- **49 departments** at or above 70% non-resident in six or more years of
  2015–2022, on cohorts of 80+ doctorates
- Departments above 70%: **23 in 2010 → 67 in 2025** (4-digit CIP, 20+ doctorates)
- The 80–90% band: **5 → 23**
- Majority-non-resident departments: 73 → 162; doctorates inside them 7.7% → 12.9%

## What to expect back, and the answer

**"The national share is flat."** It is, and the site says so first. The claim is
about distribution, and the histogram shows the top bins thickening while the
median barely moves.

**"Domestic numbers rose."** They did — +32% at doctorate level, roughly in step
with the total. That is why the argument is about *who the growth was built for*
and *who pays*, not about displacement.

**"The doctorate share is falling."** Since 2022, yes: 40.1% → 37.5%. The
thirty-year series shows why that is weak ground for complacency — the same
pattern ran up to 39.5% by 2006, plateaued, then stepped higher. It is a ratchet
between steps, not a reversal.

**"You are inferring nationality from names."** Not on the IPEDS pages. Non-resident
alien is a federal reporting category recorded by the institution at graduation.
The name-origin work elsewhere on the site is labelled as estimated and the two
are never mixed.

**"Lamar is a tiny programme."** True — median 15 doctorates a year, and the case
panel says so. North Dakota State (166 doctorates, 90.4%, 8 of 8 years) and Stony
Brook computer science (185, 85.9%) carry the same claim on more volume.

## What would strengthen this further, and is not yet built

1. **Support by citizenship over time.** Table 4-1 is a 2024 snapshot. Earlier
   SED years would show whether the assistantship gap is widening. That is the
   single highest-value next analysis.
2. **Support by citizenship by institution.** SED public tables are national.
   Restricted-use microdata would allow the department-level claim, and is an
   application, not a download.
3. **Admissions data.** Nothing public shows who applied and who was admitted.
   Without it, "prioritised" remains an inference from outcomes.

## Sources

- NSF SED Table 4-1 → `scripts/build_support_by_citizenship.py`
- NSF GSS 2024 Support file → figures above, `data/nsf_gss/gss2024_Code.xlsx`
- IPEDS Completions → `scripts/analyze_domestic_trend.py`,
  `scripts/build_concentration_cases.py`, `scripts/build_distribution.py`,
  `scripts/build_long_series.py`
