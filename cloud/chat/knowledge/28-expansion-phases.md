# When each part of the pipeline expanded

## The windows

### 1998–2003 · Post-9/11 contraction

Student visa issuance falls after the 2001 attacks and the consular tightening that followed.

| Series | Change |
|---|---|
| F-1 issuances | 251,565 → 215,695 (-14%), peak 293,357 in 2001 |
| Non-resident master's degrees | 18,678 → 28,222 (+51%) |
| H-1B issuances | 91,360 → 107,196 (+17%), peak 161,643 in 2001 |
| O-1 issuances | 4,257 → 6,126 (+44%), peak 6,666 in 2001 |

### 2003–2015 · The long student expansion

F-1 issuance rises without interruption from its post-9/11 trough to an all-time peak.

| Series | Change |
|---|---|
| F-1 issuances | 215,695 → 644,233 (+199%) |
| Non-resident master's degrees | 28,222 → 53,810 (+91%) |
| H-1B issuances | 107,196 → 172,748 (+61%) |
| O-1 issuances | 6,126 → 13,865 (+126%) |

### 2007–2017 · The master's expansion

Non-resident master's degrees rise steeply, beginning about three years after the student expansion and ending about two after it.

| Series | Change |
|---|---|
| F-1 issuances | 298,393 → 393,573 (+32%), peak 644,233 in 2015 |
| Non-resident master's degrees | 24,368 → 76,995 (+216%) |
| H-1B issuances | 154,053 → 179,049 (+16%), peak 180,057 in 2016 |
| O-1 issuances | 7,653 → 17,011 (+122%) |

### 2015–2019 · Student visas fall, degrees hold

F-1 issuance drops sharply while conferrals stay near their peak -- the pipeline emptying from the front.

| Series | Change |
|---|---|
| F-1 issuances | 644,233 → 364,204 (-44%), peak 644,233 in 2015 |
| Non-resident master's degrees | 53,810 → 69,204 (+29%), peak 76,995 in 2017 |
| H-1B issuances | 172,748 → 188,123 (+9%) |
| O-1 issuances | 13,865 → 17,751 (+28%) |

### 2019–2021 · Consular closure

Posts close and an entry proclamation suspends H-1B admission. Anchored on 2019 so the window shows the collapse rather than growth off its own trough; an exogenous break, excluded from every trend computed here.

| Series | Change |
|---|---|
| F-1 issuances | 364,204 → 357,839 (-2%), peak 364,204 in 2019 |
| Non-resident master's degrees | 69,204 → 69,596 (+1%), peak 70,631 in 2020 |
| H-1B issuances | 188,123 → 61,569 (-67%), peak 188,123 in 2019 |
| O-1 issuances | 17,751 → 7,294 (-59%), peak 17,751 in 2019 |

### 2022–2025 · The second surge

Non-resident master's degrees and H-1B issuance both reach records, faster than the first expansion.

| Series | Change |
|---|---|
| F-1 issuances | 411,131 → 400,737 (-2%), peak 445,418 in 2023 |
| Non-resident master's degrees | 55,288 → 132,149 (+139%) |
| H-1B issuances | 206,002 → 219,659 (+7%), peak 265,777 in 2023 |
| O-1 issuances | 19,102 → 19,457 (+2%) |


## The order, and the lag

The student expansion runs 2003–2015. The master's expansion runs 2007–2017 —
**it starts about three years later and ends about two years later.** That is
the shape a two-year degree produces mechanically.

Tested rather than assumed. Correlating two rising series proves nothing, so
this correlates **year-over-year changes**, which removes the shared trend,
with 2020–21 excluded as an exogenous consular shock:

| Lag (years F-1 leads degrees) | r | n |
|---|---|---|
| 0 | -0.11 | 22 |
| 1 | 0.04 | 21 |
| 2 | 0.36 | 20 |
| 3 | 0.56 | 19 |
| 4 | 0.16 | 19 |
| 5 | -0.16 | 19 |

**The peak is at 3 years (r=0.56) and lag zero
is near zero.** A spurious correlation between two trending series would be
flat across lags or peak at zero; this peaks where the mechanics predict.

**It is still a correlation on 22 observations.**
Consistent with the mechanics of a two-year degree, not proof of them.

## What to say about the sequence

- **The student visa moves first.** F-1 issuance turns before conferrals do,
  by about three years, in both directions — it rose from 2003 and degrees
  followed from 2007; it fell from 2015 and the master's boom ended in 2017.
- **The work visas do not drive it.** H-1B grew 61% across the whole
  2003–2015 student expansion while F-1 grew 199%. H-1B is capped; F-1 is not.
- **O-1 is the exception that grew throughout** — uncapped, and up 122%
  across the master's expansion alone.
- **The second surge is faster.** Non-resident master's degrees rose 139% in
  three years, 2022–2025, against 216% over ten in the first expansion.

## Limits

- **Phase boundaries are a judgment**, set from turning points and known
  events. Each carries its reason so a reader can move them.
- **Degrees and issuances are different units.** An issuance is a document,
  not a person, and includes re-stamping for travel. A degree is a conferral,
  not a person. Neither is a headcount.
- 2020–21 is an exogenous break — consular closure and an entry proclamation
  — and is excluded from every trend here.

Data: `/data/expansion_phases.json`.
