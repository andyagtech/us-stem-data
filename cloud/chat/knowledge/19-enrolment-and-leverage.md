# The long enrolment view, and what the leverage data actually shows

## 1. Forty years of S&E enrolment by citizenship

GSS table 1-7, science engineering and health, temporary-visa share:

| Year | Graduate students | Postdocs | Graduate visa holders |
|---|---|---|---|
| 1980 | 13.7% | 35.4% | 50,302 |
| 1990 | 23.7% | 48.9% | 107,066 |
| 2000 | 26.0% | 54.9% | 128,417 |
| 2020 | 30.2% | 54.5% | 210,762 |
| 2024 | 38.5% | 58.3% | 314,569 |

Graduate students **13.7% -> 38.5%**
(peak 39.4% in 2023). Postdocs
**35.4% -> 58.3%** -- a majority of the people
doing the country's postdoctoral science hold a temporary visa.

Citizen counts rose too (graduate +59%, postdoc
+145%), so this is a share shift, not a domestic
collapse. Say both.

**Limit:** this counts STUDENTS ENROLLED in S&E&H units. `graduate_balance`
counts DEGREES CONFERRED in eight core-STEM CIP families from IPEDS. Different
population, field definition and collection. They agree in direction; **their
levels are not interchangeable** and must never be quoted as one series.

## 2. Leverage: what the data supports, and what it does not

The structure is documented and not in dispute: H-1B status is tied to one
employer, the employer files the petition, and on termination the worker has
**60 days** to find another sponsor or leave (8 CFR 214.1(l)(2)). Permanent
residence is likewise employer-filed for a named job. PERM shows 57.6% of
certifications are for someone already working for that employer on an H-1B,
and 45.8% are for Indian nationals, who then wait years for a visa number.

**Supported by the SDR** -- doctorate holders working in the US, by status now:

| Dissatisfied with | Temporary visa | US citizen (native) |
|---|---|---|
| Job security | **21.8%** | 13.7% |
| Salary | **27.0%** | 19.2% |

Visa holders are 1.6x as
likely to be dissatisfied with job security.

**NOT supported: longer hours.** Working more than 40 hours a week is *less*
common among visa holders -- 32.8% against
48.0% -- and still lower within recent cohorts:

| Cohort | Temporary visa | US citizen | Gap |
|---|---|---|---|
| 2010-14 | 28.4% | 46.9% | -18.5 |
| 2015 or later | 32.5% | 41.8% | -9.3 |

Do not claim visa holders work longer hours. This dataset says the opposite.

**Population caveat, which matters a lot here.** These are DOCTORATE HOLDERS,
many of them academic postdocs. The H-1B population the leverage argument is
usually about mostly holds a bachelor's or master's and works in industry, and
is **not covered by any survey in this project**. The hours finding is evidence
about doctorate holders; it is not evidence about H-1B software engineers
either way. If asked, say that plainly rather than generalising in either
direction.

**No dataset in this project records** whether a visa-holding worker accepted
worse terms, worked unpaid overtime, or declined to complain. The structure and
the reported insecurity are what can be shown.

Data: `/data/gss_citizenship_trend.json`, `/data/working_conditions.json`,
`data/h1b/perm_pipeline.json`.
