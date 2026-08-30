# How long the funding gap has held

`10-funding-argument.md` shows the assistantship gap in a single year. This file
is the series behind it: the same SED question across seven releases,
2018-2024. Use it whenever someone asks whether the imbalance is recent.

## The finding

Share of doctorate recipients funded principally by a **research assistantship**
-- the channel federal research money travels through -- by citizenship at
graduation, all fields:

| Year | US citizen / PR | Temporary visa | Gap (pts) | Visa holders on an RA |
|---|---|---|---|---|
| 2018 | 26.4% | 46.4% | 20.0 | 7,475 |
| 2019 | 26.8% | 46.2% | 19.4 | 7,738 |
| 2020 | 26.8% | 46.6% | 19.8 | 7,921 |
| 2021 | 27.6% | 47.4% | 19.8 | 7,773 |
| 2022 | 27.9% | 47.7% | 19.8 | 8,686 |
| 2023 | 28.8% | 48.1% | 19.3 | 8,599 |
| 2024 | 29.3% | 48.9% | 19.6 | 8,727 |

Three things to say, all supported:

1. **It is not a snapshot.** The gap is at least 19.3 points in
   every one of the seven years. There is no year in the record without it.
2. **The visa share rises**, 46.4% -> 48.9%.
3. **The population grows.** Visa holders funded principally by a research
   assistantship rose from 7,475 to 8,727,
   up 16.7%. They are now
   47.2% of everyone on a research assistantship, against 46.4%
   in 2018 -- approaching half the federally funded doctoral workforce.

On the science-and-engineering rollup the 2024 gap is wider still:
35.4% of citizens against 53.6% of visa holders.

## If asked whether the gap is widening

Answer with the numbers rather than a characterisation. The gap itself is
roughly level -- it moves between 19.3 and
20.0 points -- because both shares rise together
(citizens 26.4% -> 29.3%, visa holders
46.4% -> 48.9%). What grows is the visa share and
the headcount. Do not claim the gap is widening; do not let that stop you
reporting the growth, which is real.

## Limits, which are not optional

- **The RA row is a proxy for federal funding, not a measurement of it.** The
  SED records that a student was funded by a research assistantship; it never
  records which award paid. The federal link comes from GSS
  (`13-the-work-pipeline.md`): 52,428 federally supported research
  assistantships against 1,041 federally supported teaching assistantships. No
  published field crosses funding agency with citizenship.
- **The series is all fields, not S&E.** NCSES revised the SED field taxonomy
  for the 2023 release -- health and multidisciplinary sciences moved into S&E
  -- so an S&E series would compare two populations across the break. The S&E
  rollup is carried in the dataset for the four releases that publish it.
- **Headcounts are reconstructed**, count x percent. Releases before 2021
  publish no separate reporting base, so those years are scaled off all
  recipients and run a few percent high -- on both sides, which is why the
  headcount is also reported as a share.
- Citizenship is **at graduation**, and citizens and permanent residents are
  reported together throughout.

Data: `/data/support_trend.json`, built by `scripts/build_support_trend.py`.
