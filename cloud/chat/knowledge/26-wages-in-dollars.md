# What the wage levels are worth in dollars

## The finding

**73.3% of 730,738 priced H-1B filings
promise less than the median wage for their own occupation.**

The prevailing-wage level (I to IV) is a position in a distribution. BLS OEWS
supplies the distribution — what everyone in that occupation actually earns —
so the promise can be priced:

| Occupation | Occupational median | Level I promised | As % of median |
|---|---|---|---|
| Software Developers | $133,080 | $83,720 | **63%** |
| Computer Occupations, All Other | $108,970 | $53,248 | **49%** |
| Computer Systems Analysts | $103,790 | $73,965 | **71%** |
| Data Scientists | $112,590 | $76,960 | **68%** |
| Mechanical Engineers | $102,320 | $65,374 | **64%** |
| Computer and Information Systems M | $171,200 | $110,843 | **65%** |
| Operations Research Analysts | $91,290 | $60,299 | **66%** |
| Accountants and Auditors | $81,680 | $54,704 | **67%** |

## The ladder, measured rather than asserted

For software developers, the four levels against the occupational median:

| Level | Median promised | As % of occupational median |
|---|---|---|
| Level I | $83,720 | 62.9% |
| Level II | $99,008 | 74.4% |
| Level III | $121,222 | 91.1% |
| Level IV | $139,464 | 104.8% |

**Levels I, II and III all sit below the occupational median; only Level IV
exceeds it.** This is measured from the filings themselves, not inferred from
the regulation — an earlier attempt to source the statutory percentile anchors
failed, and this replaces it with evidence.

**Limits:** what was PROMISED, not paid. Filing low is entirely lawful — it is
the cheapest legal way to fill a role. 64%
of filings carried both a usable occupation code and wage; the rest could not
be priced. OEWS is national, so a filing in a high-cost metro is compared
against a national median.

## Tuition dependence: the answer splits by sector

Tuition as a share of institutional revenue, against foreign graduate share:

| Sector | Half | Median tuition share | Foreign graduate share |
|---|---|---|---|
| Public (GASB) | least dependent | 14.0% | 40.7% |
| Public | most dependent | 27.9% | **50.4%** |
| Private (FASB) | least dependent | 27.7% | **50.2%** |
| Private | most dependent | 64.7% | 40.9% |

**The two sectors point opposite ways**, and that is the honest summary. Among
publics, tuition-dependent institutions run a higher foreign share; among
privates, a lower one. The likely reason is composition — tuition-dependent
privates are small teaching colleges, while research privates look
un-dependent because endowment and grants are large. **The opposite signs are
themselves the argument against reading either causally.**

**Never pool the two.** GASB and FASB forms are not interchangeable: public
tuition is net of discounts, the private revenue total includes investment
return. And the tuition figure is from EVERY student — IPEDS does not report
revenue by citizenship.

Data: `/data/lca_wage_levels.json`, `/data/occupational_wages.json`,
`/data/tuition_dependence.json`.
