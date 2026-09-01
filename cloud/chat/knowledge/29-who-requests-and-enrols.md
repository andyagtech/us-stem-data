# Who requests, who receives, and who enrols

## Employers: the three H-1B files joined

| Employer | Approved (initial) | LCAs certified | Level I or II | Denial rate |
|---|---|---|---|---|
| Cognizant Tech Solns Us Corp | 50,940 | 43,264 | 51% | 18% |
| Tata Consultancy Svcs Ltd | 43,756 | 21,903 | 86% | 7% |
| Wipro Limited | 28,460 | 7,280 | 90% | 9% |
| Infosys Ltd | 23,917 | 30,496 | 71% | 12% |
| Accenture Llp | 21,489 | 9,575 | 44% | 7% |
| Ernst & Young U.S. Llp | n/a | 21,087 | 60% | n/a |
| Infosys Technologies Limited | 20,078 | n/a | n/a | 5% |
| Microsoft Corporation | 17,416 | 15,120 | 56% | 1% |
| Amazon Com Services Llc | 17,035 | 22,123 | 75% | 2% |
| Google Inc | 14,591 | 18,943 | 61% | 1% |
| Hcl America Inc | 14,052 | 8,920 | 49% | 8% |
| Intel Corporation | 11,111 | 5,162 | 41% | 1% |

Read the columns as three different agencies answering three different
questions: DOL certified the request, USCIS granted or denied the petition,
DOL's Wage and Hour Division found violations. **21** of
84 employers appear in both the USCIS and LCA extracts.

**"n/a" means not in that extract, not zero.** The inputs are top-N lists.

**Totals are floors.** The agencies share no identifier and each company files
under several spellings; names are normalised for case, punctuation, legal
suffixes and a short explicit abbreviation table, and matched exactly. Nothing
is fuzzy-matched. Every row lists the spellings it absorbed. "Infosys" and
"Infosys Technologies" stay separate because any rule merging them would also
merge unrelated firms — the true Infosys total is the sum of both.

## What cannot be answered

**There is no employer-level data for L-1 or O-1.** Neither requires a labour
condition application, and USCIS publishes an employer hub for H-1B, H-2A and
H-2B but not for these. So "which companies bring in the most L-1s" has no
published answer at all. Say that plainly rather than substituting H-1B.

## Universities: enrolment, not issuance

**F-1 issuance by university is not published either.** State reports visas by
consulate and nationality, never by school. SEVP publishes school-level
figures only for OPT. What can be shown is who *enrols* foreign students:

| Institution | Non-resident | Total | Share |
|---|---|---|---|
| New York University | 19,373 | 57,335 | 33.8% |
| Columbia University in the City of New York | 13,898 | 35,279 | 39.4% |
| University of Southern California | 12,754 | 47,147 | 27.1% |
| Georgia Institute of Technology-Main Campus | 12,661 | 47,946 | 26.4% |
| University of Illinois Urbana-Champaign | 12,575 | 56,563 | 22.2% |
| Arizona State University Campus Immersion | 12,364 | 79,593 | 15.5% |
| Northeastern University | 12,146 | 31,159 | 39.0% |
| Boston University | 10,468 | 36,624 | 28.6% |
| Purdue University-Main Campus | 9,387 | 52,905 | 17.7% |
| University of Michigan-Ann Arbor | 8,828 | 52,065 | 17.0% |
| University of North Texas | 8,827 | 47,507 | 18.6% |
| University of Washington-Seattle Campus | 8,145 | 55,620 | 14.6% |

Graduate level only:

| Institution | Non-resident graduate | Share |
|---|---|---|
| Columbia University in the City of New York | 12,142 | 46.4% |
| New York University | 11,549 | 41.9% |
| Georgia Institute of Technology-Main Campus | 10,935 | 38.4% |
| University of Southern California | 9,777 | 37.4% |
| Northeastern University | 9,725 | 63.7% |
| Trine University-Regional/Non-Traditional Campuses | 7,657 | 98.3% |
| University of North Texas | 7,520 | 55.1% |
| University of Illinois Urbana-Champaign | 7,355 | 35.0% |

Nationally: **17.1% of graduate** and
2.8% of undergraduate enrolment.

**Three measures, three populations.** IPEDS counts everyone enrolled in a
fall term, every level and field. SEVP counts graduates already working on
STEM OPT. The GSS ranking covers science, engineering and health graduate
students only. They rank institutions differently because they measure
different things — report them side by side, never blended.

Ranked by **count, not share**: share rankings at this level are dominated by
very small institutions. Non-resident is a visa category, so permanent
residents count as domestic and every share here is a floor.

Data: `/data/employer_profiles.json`, `/data/university_foreign_students.json`.
