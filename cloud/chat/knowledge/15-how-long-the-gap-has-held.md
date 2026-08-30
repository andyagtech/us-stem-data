# How long the funding gap has held

`10-funding-argument.md` shows the assistantship gap in a single year. A single year
cannot tell a new gap from an entrenched one, and "federal money has gone to
non-citizens for some time" is a claim about duration. This file is the series.

## The finding

Share of doctorate recipients funded principally by a **research assistantship**,
by citizenship at graduation, all fields, from seven SED releases:

| Year | US citizen / PR | Temporary visa | Gap (pts) | Visa holders on an RA |
|---|---|---|---|---|
| 2018 | 26.4% | 46.4% | 20.0 | 7,475 |
| 2019 | 26.8% | 46.2% | 19.4 | 7,738 |
| 2020 | 26.8% | 46.6% | 19.8 | 7,921 |
| 2021 | 27.6% | 47.4% | 19.8 | 7,773 |
| 2022 | 27.9% | 47.7% | 19.8 | 8,686 |
| 2023 | 28.8% | 48.1% | 19.3 | 8,599 |
| 2024 | 29.3% | 48.9% | 19.6 | 8,727 |

**The gap is old and flat.** It sits between 19.3 and
20.0 points in every one of the seven years and never leaves
that range.

## What is moving, and what is not

Do not describe this as a widening gap. It is not widening. Both lines rise
together, and the citizen share rises slightly faster: citizens
26.4% -> 29.3%
(+2.9 points), visa holders
46.4% -> 48.9%
(+2.5 points).

What grows is headcount. Visa holders funded principally by a research
assistantship rose from 7,475 to 8,727,
up 16.7%. Visa holders
are 47.2% of everyone on a research assistantship, against
46.4% in 2018.

So the correct summary is **duration and scale, not deterioration**: the
imbalance is not new, it has not worsened, and it now covers more people.

## Limits, which are not optional

- **The RA row is a proxy for federal funding, not a measurement of it.** The
  SED records that a student was funded by a research assistantship; it never
  records which award paid. The federal link comes from GSS -- see
  `13-the-work-pipeline.md` -- which shows federal support reaching doctoral
  students overwhelmingly through RAs: 52,428 federally supported research
  assistantships against 1,041 federally supported teaching assistantships. No
  published field crosses funding agency with citizenship.
- **The series is all fields, not science and engineering.** NCSES revised the
  SED field taxonomy for the 2023 release -- health and multidisciplinary
  sciences moved into S&E -- so an S&E series would compare two different
  populations across the break. The S&E rollup is carried in the dataset for
  the four releases that publish it, and shows a wider gap
  (35.4% against 53.6% in 2024) on a shorter run.
- **Headcounts are reconstructed**, count x percent. Releases before 2021
  publish no separate reporting base, so those years are scaled off all
  recipients and run a few percent high -- on both sides, which is why the
  headcount is reported as a share.
- Citizenship is **at graduation**, and citizens and permanent residents are
  reported together throughout.

Data: `/data/support_trend.json`, built by `scripts/build_support_trend.py`.
