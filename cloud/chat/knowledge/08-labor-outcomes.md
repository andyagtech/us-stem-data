# Labor-market outcomes for doctorate holders

Readers frequently want to set the composition finding against employment: if a
field is heavily non-resident, does it also look bad in the labor market? Here
is what can and cannot be said.

## What exists

The **NSF Survey of Doctorate Recipients (SDR)** is the source. Its public-use
file carries, for a large sample of US doctorate holders: labor force status,
field of doctorate at two levels of grain, citizenship, salary, employment
sector, and whether the principal job is related to the doctorate. Survey
weights must be applied for any population estimate.

**There is no state in the SDR public-use file.** Geography is suppressed for
confidentiality. Any state-level employment question needs a different source —
BLS occupational data or Census microdata — and those are organised by
occupation or by bachelor's field, not by field of doctorate. Say so rather
than improvising a state answer from national data.

## Unemployment is the wrong metric here

Doctorate unemployment is very low and remarkably uniform across fields —
around one percent everywhere, with little spread. It does not discriminate
between fields, and the per-field unemployed counts in the sample are small
enough that apparent differences are mostly noise. **Do not build an argument on
doctorate unemployment rates**, and be skeptical of anyone who does.

The better outcome measure is **whether the job is related to the doctorate**.
That varies several-fold across fields on much healthier sample sizes, and it
captures underemployment, which is the real labor-market question for people
holding a doctorate.

## What the correlation looks like

Setting the IPEDS non-resident share against SDR outcomes at field-group level
gives a **weak positive association** — fields with higher non-resident shares
look slightly worse on job-relatedness — but the relationship is loose and rests
on only a handful of field groups.

**This is descriptive and must be presented as such.** Six or seven points
cannot support inference. The two taxonomies map onto each other coarsely: SDR
field groups and IPEDS CIP families are different classification systems, and
the crosswalk is approximate. And the direction of any relationship is entirely
unestablished — a field can attract international students *because* it is
expanding, or its domestic candidates can decline *because* outcomes are poor,
and this data distinguishes neither.

If a reader wants this comparison, give it to them with the caveats attached,
and refuse to state it as a finding. If they push for a causal reading, say
plainly that the data does not carry one.

## Reproducing it

`scripts/analyze_sdr_outcomes.py` computes all of the above from the SDR
public-use file, with the cell-size flags visible. The field labels in that
script are marked provisional: the shipped SAS file contains format assignments
but not the value definitions, so the code-to-label mapping follows the standard
NCSES taxonomy without having been confirmed against the codebook.
