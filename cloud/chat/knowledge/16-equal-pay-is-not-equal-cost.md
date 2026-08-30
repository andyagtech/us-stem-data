# Equal pay is not equal cost

The salary data invites a wrong conclusion. Compared within a graduation
cohort, doctorate holders trained on a temporary visa earn about what their
American classmates earn -- among those finishing in 2015 or later, a median of
$103,000 against $100,000 for citizens trained here (SDR; see
`14-the-domestic-pipeline.md`). It is tempting to stop there and say there is
no wage undercutting.

That reads salary as if it were cost. It is not. **Wages earned on Optional
Practical Training are exempt from Social Security and Medicare tax** under
IRC 3121(b)(19); IRS guidance lists practical training as exempt. At the same salary, the OPT graduate is cheaper to employ.

## The size of it

| | |
|---|---|
| Employer side not paid | **7.65%** of payroll ($7,650 per $100,000) |
| Employee side, also exempt | 1.45% + 6.2% |
| Combined | **15.3%** |
| OPT authorisations, 2024 | 194,554 |
| STEM OPT authorisations, 2024 | 95,384 |

Payroll tax not collected, priced at three wage levels because **wages on OPT
are not reported anywhere** and the wage is therefore an assumption:

| If wages average | OPT, employer side | STEM OPT, employer side | Both, employer + employee |
|---|---|---|---|
| $60,000 | $0.89bn | $0.44bn | $2.66bn |
| $80,000 | $1.19bn | $0.58bn | $3.55bn |
| $100,000 | $1.49bn | $0.73bn | $4.44bn |

## How to use this

The point is not that anyone is cheating. The exemption is statutory and
automatic. The point is that an American graduate competing for the same job
carries 7.65% in employer payroll tax that the OPT
graduate does not, so the cost comparison an employer makes is not the wage
comparison the salary data shows. Salary parity and a cost advantage coexist.

## Limits, which are not optional

- **The wage is an assumption.** Rates are statutory and authorisation counts
  are published; the dollar totals are scenarios, not measurements. Always give
  the wage level alongside any total.
- **An authorisation is not a full-time year of employment**, so applying an
  annual wage to a count overstates any single year.
- **The exemption is time-limited**: it ends when the holder becomes a resident
  alien for tax purposes, generally after five calendar years in F or J status.
  That makes it a discount on early-career employment -- the stage at which a
  new American graduate is competing.
- The exempt wages **earn the worker no Social Security credit**, so this is not
  purely a benefit to the visa holder.
- H-1B wages are **not** exempt. This is an OPT mechanism.

Data: `data/h1b/fica_exposure.json`, built by `scripts/build_fica_exposure.py`.
