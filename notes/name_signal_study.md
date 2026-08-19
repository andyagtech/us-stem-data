# Does cohort name composition carry usable signal about reported NRA share?

Measurement study, 2026-08-18. Script: `/Users/andy/usds_china/scripts/name_signal_study.py`
Raw output: `ns_analyze.txt`, `ns_datequal.json`, `cohort_cells.csv`, `ipeds_doctorate_cells.csv` (this dir).

**This is a calibration study, not a classifier.** No per-person inference from name to visa
status was built or evaluated. The only quantity tested is whether the *distribution* of
name-derived features across a cohort tracks that cohort's *reported* NRA share.

---

## Verdict (read this first)

There is a real, statistically solid aggregate association — much stronger than I expected —
but **it is not worth building on, for three separate reasons**:

1. **~89% of it is field composition, not names.** Held out by university, name features alone
   reach OOS R² = 0.543; CIP-family fixed effects alone reach 0.639; both together reach 0.698.
   Names therefore contribute 0.698 − 0.639 = **0.059 uniquely**, i.e. 11% of their apparent
   explanatory power. The other 89% is "engineering and CS cohorts have both more non-Anglo
   names and more visa holders." That is the confound, and it dominates.
2. **What survives is worth +0.026 R² over free public data.** Field FE plus the institution's
   own IPEDS NRA share (leave-one-out, no names) gives OOS R² = 0.713. Adding every name
   feature moves it to 0.739. RMSE 0.117 → 0.112, i.e. the model gains **half a percentage
   point** of accuracy on a quantity whose spread is 22 points.
3. **The target is already published.** IPEDS reports CNRALT/CTOTALT at
   (institution × CIP-6 × year). For any US cohort in this project's scope, reading the number
   strictly dominates estimating it from names.

Residual error is the killer: even the best model is off by **±11 percentage points RMSE** on a
cell's NRA share. A department claimed at 40% NRA could genuinely be anywhere from 29% to 51%.
Nothing publishable can rest on that.

The honest one-line summary: *name composition predicts NRA share about as well as knowing
which department it is, and once you know the department it adds almost nothing.*

---

## 1. The joinable dataset — what matched, what was lost

Ground truth: IPEDS Completions, AWLEVEL = 17 (research doctorate), MAJORNUM = 1,
years 2010–2025, our 100 UNITIDs → 84,770 doctorate cells.
(The local 2008 and 2009 completions files are **partial** — they contain only 20 and 36 of our
100 institutions vs. 100 from 2010 on — so those two years were dropped. CIPCODE 99 rows are
kept *only* as institution totals, never as field cells, so nothing is double-counted.
The UNITID BOM gotcha is handled by reading `fieldnames[0]`.)

### Record-level attrition (474,064 records → cohort cells)

| stage | dropped | remaining |
|---|---:|---:|
| all records | — | 474,064 |
| university has no UNITID (2 of 102) | 13,261 | 460,803 |
| degree label is not `phd` (143k MS + 46k unlabeled) | 182,549 | 278,254 |
| year missing or outside 2010–2025 | 7,718 | 270,536 |
| department string not mappable to a CIP family | 28,634 | **241,902** |

→ **11,367 cohort cells** (university × CIP 2-digit family × year).

The crosswalk loss is smaller than it looks: 25,978 of the 28,634 unmapped records (91%) carry
the placeholder department labels `General` and `Keyword`, which contain no field information at
all and could not be mapped by any method. Real residual unmapped departments are in the low
hundreds each (`Fiber & Polymer Science`, `Health and Human Performance`, `Global Health`).

### Cell-level attrition (join to IPEDS)

| | by year | pooled over year |
|---|---:|---:|
| cohort cells offered | 11,367 | 1,479 |
| no matching IPEDS cell | −1,379 | −223 |
| IPEDS cell < 5 doctorates | −1,742 | −34 |
| our cohort < 5 records | −1,296 | −69 |
| **matched** | **6,950** | **1,153** |
| universities / fields | 94 / 20 | 96 / 21 |
| our PhD records inside matched cells | 223,926 | 236,683 |

Every correlation below states its cell count. Nothing rests on fewer than 1,153 cells.

### The crosswalk and the error it introduces

Our department labels are free-text repository metadata with no CIP anywhere. I built an ordered
keyword→CIP-2-digit ruleset (21 families, in `CIP2_RULES`). It is coarse by design: mapping to a
6-digit CIP would be guesswork. The error this introduces is visible in the coverage ratio
(our record count ÷ IPEDS doctorates in the same cell): in the by-year panel the median is 1.00
but **20.7% of cells have coverage > 1.5**, which is arithmetically impossible and means those
records were assigned to a family where IPEDS counted fewer degrees, or dated to the wrong year.
Restricting to the 589 pooled cells with plausible coverage (0.5–1.5) does not weaken the result
(r = 0.774 vs 0.729 overall), so the crosswalk noise is attenuating, not manufacturing, the
association.

### The date problem, handled three ways

1. **Primary panel is pooled over year** (1,153 cells). Collapsing 2010–2025 makes the result
   immune to any misdating *within* the window, which is the bulk of the damage.
2. **Empirical date-quality screen.** For each university I computed our PhD count ÷ IPEDS
   doctorates awarded, per year, and flagged instability (CV > 0.5) or impossibility
   (>5% of years with coverage > 1.5). 62 of 91 testable universities pass. Flagged worst:
   `ucsd` (70% of years impossible), `ucmerced` (40%), `purdue` (33%), `utk` (29%),
   `ubuffalo`/`cmu`/`uiuc`/`gmu`/`ucdavis` (unstable), `cornell`/`dartmouth`/`uutah`
   (median coverage ~0.1, i.e. near-total harvest gaps).
3. **Rerun restricted to the 62 sound universities.** Conclusions are unchanged and marginally
   stronger: pooled r = 0.760 (721 cells), partial r = 0.383, M2→M3 R² 0.641→0.718,
   M7→M8 0.720→0.751. The date problem is not what is driving or suppressing this.

Caveat on the screen: it did **not** flag `iowa_state` or `mit`, both of which are known from
independent evidence to have accession-date contamination. A volume-ratio proxy is weak when
misdating shuffles records between in-window years. Treat "62 sound" as a filter, not a
guarantee.

---

## 2. The measured association

### Raw correlation (pooled panel, **n = 1,153 cells**)

| feature | Pearson | Spearman |
|---|---:|---:|
| `sh_foreign_any` | **0.729** | 0.740 |
| `sh_chinese` | 0.658 | 0.686 |
| `sh_indian` | 0.466 | 0.500 |
| `sh_iranian` | 0.297 | 0.321 |
| `sh_arabic` | 0.201 | 0.232 |
| `sh_korean` | 0.170 | 0.175 |
| `sh_vietnamese` | 0.142 | 0.195 |
| `sh_turkish` | 0.073 | 0.167 |

Cluster bootstrap (200 reps, resampling whole universities): r = 0.729, **95% CI [0.677, 0.772]**.
By-year panel (n = 6,950): r = 0.622, CI [0.591, 0.659].

### After controlling for institution, field and year (the confound test)

Absorbing university + CIP-family (+ year) fixed effects by within-transformation, then
correlating residuals:

| | pooled (n=1,153) | by year (n=6,950) |
|---|---:|---:|
| `sh_foreign_any` partial r | **0.382** [0.315, 0.441] | 0.278 [0.243, 0.313] |
| `sh_chinese` partial r | 0.331 | 0.220 |
| `sh_indian` partial r | 0.099 | 0.098 |
| residual sd of NRA share after FE | 0.103 (from 0.219) | 0.145 (from 0.243) |

**The correlation does not vanish under those controls**, which is the result I expected to
report as negative and cannot. But note the shrinkage: r 0.73 → 0.38, and r² 0.53 → 0.15. The
fixed effects already absorb 78% of the variance in NRA share; names explain 15% of the small
remainder.

### Held out by whole university, 5-fold, out-of-sample R² (pooled panel, n = 1,153)

| model | OOS R² | fold sd | RMSE | MAE |
|---|---:|---:|---:|---:|
| M0 baseline — predict train global mean | −0.002 | 0.008 | 0.219 | 0.188 |
| M1 name features only | 0.543 | 0.143 | 0.148 | 0.111 |
| M5 `sh_foreign_any` alone | 0.524 | 0.142 | 0.151 | 0.115 |
| M6 `sh_chinese` alone | 0.423 | 0.131 | 0.166 | 0.131 |
| M2 field FE only, **no names** | 0.639 | 0.032 | 0.131 | 0.100 |
| M3 field FE + names | 0.698 | 0.066 | 0.120 | 0.089 |
| M7 field FE + IPEDS institution NRA (LOO), **no names** | 0.713 | 0.039 | 0.117 | 0.090 |
| M8 field FE + institution NRA + names | **0.739** | 0.047 | 0.112 | 0.084 |

By-year panel (n = 6,950) tells the same story with lower ceilings: M0 −0.002, M1 0.400,
M2 0.531, M3 0.586, M7 0.582, M8 0.620.

The two increments that matter:
- **names beyond field: +0.059 R²** (0.639 → 0.698)
- **names beyond field + the institution's published NRA share: +0.026 R²** (0.713 → 0.739)

The M7 institution feature is leave-one-out (the cell's own counts are removed from its
institution total), so that comparison is not leaked.

---

## 3. Where it fails

**By field.** Signal is concentrated where cohorts are mixed and collapses where they are not
(pooled panel):

| CIP2 | field | cells | mean NRA | r |
|---|---|---:|---:|---:|
| 42 | Psychology | 80 | 0.095 | 0.711 |
| 45 | Social Sciences | 80 | 0.324 | 0.604 |
| 27 | Math & Statistics | 84 | 0.474 | 0.593 |
| 13 | Education | 75 | 0.104 | 0.583 |
| 40 | Physical Sciences | 91 | 0.428 | 0.524 |
| 11 | Computer Science | 84 | 0.609 | 0.422 |
| 14 | Engineering | 90 | 0.572 | **0.311** |
| 50 | Visual & Performing Arts | 53 | 0.228 | 0.194 |
| 23 | English | 71 | 0.095 | **0.114** |
| 38 | Philosophy | 46 | 0.172 | **−0.015** |

Engineering — the field this project cares most about — has the *weakest* correlation of any
large STEM family (0.311), because NRA share is high nearly everywhere and the range is
compressed. Philosophy is flat-to-negative. English is near zero. The model works best in
Psychology and Education, fields where almost nobody is a visa holder and the prediction is
therefore trivially "low."

**By cohort size.** r = 0.305 for cells with 10–24 IPEDS doctorates (26 cells), 0.483 for 25–49
(82 cells), 0.766 for 50+ (1,043 cells). Below ~25 people the association is weak and the cell
counts are too thin to trust. **Almost the entire result rests on large cells.**

**Driven by one or two features.** `sh_chinese` alone reaches OOS R² 0.423 of the 0.543 that all
nine features reach together; `sh_foreign_any` alone reaches 0.524. Korean, Vietnamese and
Turkish shares contribute essentially nothing (partial r 0.04–0.12). This is a Chinese-and-Indian
-name effect with a long tail of noise, not a rich multi-feature signal.

**Across universities.** Within-university correlation across fields is high (median r = 0.823,
positive for 86/86 universities with ≥6 cells) — but that is *the confound in its purest form*:
inside one university, the fields with more non-Anglo names are the fields with more visa
holders. Worst transfer cases are the universities with broken harvests (`cornell` r = 0.14,
median coverage 0.12; `ucsf` 0.30; `ttu` 0.32). Fold-to-fold variance for names-only models is
large (sd 0.13–0.14 across held-out folds vs 0.03 for field FE), i.e. name-based prediction
transfers to a new university much less reliably than simply knowing the field mix.

---

## 4. Two caveats that limit even the positive reading

1. **Same people on both sides.** Our name features and the IPEDS NRA count describe largely the
   *same individuals* (median coverage 0.55 pooled, 1.00 by year). This is the correct design for
   a calibration question, but it means the association cannot be extrapolated to a cohort we
   have not harvested, and it is not evidence that names would predict an unobserved cohort's
   NRA share.
2. **The surviving partial correlation is still consistent with pure composition.** Fixed effects
   were absorbed at the CIP 2-digit level. Within CIP 14, electrical engineering and civil
   engineering differ sharply in both name mix and NRA share. So partial r = 0.38 may simply be
   names proxying *finer-grained field composition* than I could control for — not names carrying
   information about legal status. I cannot separate those two with the crosswalk available, and
   the finer-composition explanation is the more parsimonious one.

---

## 5. Recommendation

Do not build a name→NRA estimator, and do not put one on the site.

- The incremental value over data IPEDS already publishes is +0.026 R² / 0.5 percentage points.
- The absolute error (±11 points RMSE) is too large for any department-level claim.
- The signal is weakest exactly where the project's interest is strongest (Engineering, and small
  departments), and strongest where the answer is trivially "almost nobody."
- The most defensible mechanism for what signal exists is field composition, not visa status,
  which means any public framing would be describing the wrong thing.

The one legitimate use of this measurement is **as a negative control**: it quantifies that the
existing name classification, used in aggregate and at its best, reproduces a reported NRA share
to within about 11 points and adds almost nothing to public data. That is a good reason to keep
name classification off the public site, and it is worth recording as such.
