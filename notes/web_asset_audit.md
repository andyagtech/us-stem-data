# Web asset audit

Regenerate with `python3 scripts/audit_web_assets.py`. Nothing here is
deleted automatically; this is a list to review.

## 1. Unreferenced assets — candidates for deletion

Nothing in the site links to these.

| Size | Path |
|---:|---|
| 4,878.6 KB | `dashboard_data.json` |
| 749.0 KB | `department_summary.json` |
| 276.1 KB | `states/ca.html` |
| 276.0 KB | `android-chrome-512x512.png` |
| 217.0 KB | `states/ny.html` |
| 160.4 KB | `states/tx.html` |
| 151.5 KB | `states/pa.html` |
| 133.4 KB | `funding_data.json` |
| 120.6 KB | `states/il.html` |
| 114.6 KB | `states/fl.html` |
| 112.4 KB | `states/ma.html` |
| 98.4 KB | `states/oh.html` |
| 92.6 KB | `states/nc.html` |
| 88.9 KB | `states/va.html` |
| 88.1 KB | `states/mo.html` |
| 83.4 KB | `states/mi.html` |
| 81.5 KB | `og-image.png` |
| 77.6 KB | `states/ga.html` |
| 77.6 KB | `quality.html` |
| 77.5 KB | `states/tn.html` |
| 74.0 KB | `states/in.html` |
| 72.9 KB | `states/mn.html` |
| 72.4 KB | `states/wi.html` |
| 70.2 KB | `states/pr.html` |
| 65.3 KB | `states/wa.html` |
| 62.4 KB | `states/nj.html` |
| 62.0 KB | `states/sc.html` |
| 61.5 KB | `states/ky.html` |
| 60.7 KB | `android-chrome-192x192.png` |
| 58.9 KB | `states/md.html` |
| 58.7 KB | `states/co.html` |
| 58.3 KB | `states/ia.html` |
| 58.2 KB | `states/ks.html` |
| 55.6 KB | `states/az.html` |
| 54.1 KB | `states/al.html` |
| 53.6 KB | `states/la.html` |
| 52.5 KB | `states/or.html` |
| 51.8 KB | `states/ct.html` |
| 50.7 KB | `states/ar.html` |
| 49.0 KB | `og-image-twitter.png` |
| 48.5 KB | `states/ok.html` |
| 47.3 KB | `states/ne.html` |
| 45.1 KB | `states/ut.html` |
| 44.4 KB | `states/ms.html` |
| 43.8 KB | `andy-avatar.jpeg` |
| 43.6 KB | `states/wv.html` |
| 41.0 KB | `states/nm.html` |
| 40.3 KB | `states/nh.html` |
| 40.0 KB | `states/me.html` |
| 38.6 KB | `states/sd.html` |
| 37.7 KB | `states/mt.html` |
| 37.4 KB | `states/dc.html` |
| 35.7 KB | `states/nd.html` |
| 33.0 KB | `states/nv.html` |
| 32.4 KB | `states/ri.html` |
| 31.7 KB | `states/id.html` |
| 31.0 KB | `states/vt.html` |
| 30.8 KB | `analytics.html` |
| 30.0 KB | `ipeds_field_demographics.json` |
| 30.0 KB | `states/hi.html` |
| 29.9 KB | `states/de.html` |
| 28.6 KB | `medical.html` |
| 26.1 KB | `states/ak.html` |
| 23.6 KB | `states/wy.html` |
| 23.1 KB | `department_reports.html` |
| 22.7 KB | `states.html` |
| 22.6 KB | `workforce.html` |
| 22.0 KB | `caltech_dashboard_data.json` |
| 17.7 KB | `data_requests.html` |
| 16.8 KB | `visa-schools.html` |
| 16.4 KB | `caltech_field_demographics.html` |
| 16.0 KB | `contents.html` |
| 15.6 KB | `caltech_dashboard.html` |
| 14.4 KB | `industries.html` |
| 14.3 KB | `expansion.html` |
| 11.5 KB | `bodyshops.html` |
| 11.3 KB | `usaid.html` |
| 10.1 KB | `caltech_ipeds_tables.html` |
| 9.9 KB | `eor.html` |
| 9.4 KB | `security.html` |
| 9.0 KB | `rankings.html` |
| 6.5 KB | `briefing.html` |
| 6.0 KB | `filers.html` |
| 1.6 KB | `chat-admin.html` |
| 1.2 KB | `concentration.html` |

Total 10,306.7 KB across 85 files.

## 2. Published data, unreferenced on purpose

These are open-data publications. The methodology page cites them and the
report builders read them; no page fetches them, and that is correct.

| Size | Path |
|---:|---|
| 2,352.3 KB | `data/institution_profiles.json` |
| 1,448.8 KB | `data/buildfellowship_projects.json` |
| 945.0 KB | `data/lca_by_university.json` |
| 632.5 KB | `data/visa_issuances.json` |
| 627.8 KB | `data/occupational_wages.json` |
| 541.9 KB | `data/cap_exempt_directory.json` |
| 451.7 KB | `data/visa_bulletin.json` |
| 393.8 KB | `data/cap_exempt_sponsor_ranking.json` |
| 340.0 KB | `data/tuition_and_appropriations.json` |
| 282.6 KB | `data/cap_exempt_merged_employers.json` |
| 204.1 KB | `data/university_distribution.json` |
| 187.7 KB | `data/state_residency.json` |
| 180.1 KB | `data/institution_funding.json` |
| 154.7 KB | `data/gss_institution_ranking.json` |
| 132.4 KB | `data/concentration_cases.json` |
| 120.3 KB | `data/legal_directory.json` |
| 100.1 KB | `data/chat/site_map.json` |
| 85.2 KB | `data/h1b_approvals.json` |
| 83.8 KB | `data/opt_by_university.json` |
| 82.4 KB | `data/us_states.json` |
| 80.9 KB | `data/visa_staffing.json` |
| 80.4 KB | `data/visa_bodyshops.json` |
| 70.3 KB | `data/visa_schools.json` |
| 67.6 KB | `data/origin_vs_residence.json` |
| 65.1 KB | `data/security_cases.json` |
| 49.9 KB | `data/visa_substitution.json` |
| 49.2 KB | `data/level_rankings.json` |
| 42.9 KB | `data/programme_shares.json` |
| 42.0 KB | `data/critical_industries.json` |
| 38.8 KB | `data/federal_support_by_university.json` |
| 37.5 KB | `data/employer_profiles.json` |
| 35.8 KB | `data/lca_wage_levels.json` |
| 31.1 KB | `data/composition_change.json` |
| 27.6 KB | `data/eor_market.json` |
| 26.7 KB | `data/nativity_labour.json` |
| 23.7 KB | `data/completions_by_race.json` |
| 20.8 KB | `data/enrolment_and_funding.json` |
| 20.7 KB | `data/taxpayer_cost.json` |
| 20.7 KB | `data/opt_employers.json` |
| 20.6 KB | `data/h1b_enforcement.json` |
| 19.1 KB | `data/tuition_dependence.json` |
| 18.3 KB | `data/build_fellowship_partners.json` |
| 17.5 KB | `data/state_funding_and_enrolment.json` |
| 17.2 KB | `data/university_foreign_students.json` |
| 17.2 KB | `data/grid_capacity.json` |
| 17.2 KB | `data/buildfellowship_project_links.json` |
| 13.8 KB | `data/taxonomy.json` |
| 12.1 KB | `data/tuition.json` |
| 11.6 KB | `data/gss_citizenship_trend.json` |
| 10.9 KB | `data/expansion_phases.json` |
| 9.5 KB | `data/nonprofit_990s.json` |
| 9.4 KB | `data/graduate_balance.json` |
| 9.3 KB | `data/live_bundle.json` |
| 9.3 KB | `data/domestic_pipeline.json` |
| 9.2 KB | `data/support_by_citizenship.json` |
| 8.3 KB | `data/perm_pipeline.json` |
| 8.0 KB | `data/doctorate_origins.json` |
| 7.4 KB | `data/summary.json` |
| 7.3 KB | `data/support_trend.json` |
| 7.3 KB | `data/institution_fields.json` |
| 7.1 KB | `data/stem_earnings.json` |
| 6.7 KB | `data/workforce_dashboard.json` |
| 6.6 KB | `data/cap_exempt_proxy_comparison.json` |
| 6.6 KB | `data/universities_index.json` |
| 6.6 KB | `data/nonimmigrant_admissions.json` |
| 6.5 KB | `data/doctorate_outcomes.json` |
| 6.1 KB | `data/graduate_enrollment.json` |
| 5.9 KB | `data/long_series.json` |
| 5.7 KB | `data/h1b_cap_exempt.json` |
| 5.5 KB | `data/lpr_adjustments.json` |
| 5.2 KB | `data/local_wage_comparison.json` |
| 4.7 KB | `data/wage_level_trend.json` |
| 4.2 KB | `data/working_conditions.json` |
| 3.9 KB | `data/grad_support.json` |
| 3.1 KB | `data/sed_series.json` |
| 3.0 KB | `data/j1_scholars.json` |
| 2.8 KB | `data/humanitarian_admissions.json` |
| 2.6 KB | `data/repo_datasets.json` |
| 2.6 KB | `data/eb2_niw.json` |
| 2.3 KB | `data/fica_exposure.json` |
| 2.2 KB | `data/stay_rates.json` |
| 2.1 KB | `data/opt_national.json` |
| 1.7 KB | `data/distribution.json` |

## 3. Datasets that never reach the site

Built and catalogued, but produced only into `data/`. They are not
downloadable, they are not in the assistant's bundle, and no chart reads
them.

- `build_fellowship_partners`
- `build_fellowship_projects`
- `cap_exempt_directory`
- `eb2_niw`
- `federal_support`
- `h1b_cap_exempt`
- `j1_scholars`
- `lca`
- `nonprofit_990s`
- `nra_index`
- `opt`
- `perm_pipeline`
- `pipeline_funnel`
- `workforce`

## 4. Legacy objects in S3

0 objects at the bucket root, 0.0 MB, from before
the atomic-deploy scheme. The CloudFront origin points at `/v/<build>/`, so
these are not served. Every name also exists in the current build.

Confirm the origin has no root fallback before deleting.

## What the assistant actually holds

The chat Lambda ships its own bundle in `cloud/chat/chat_data/` and fetches
nothing at runtime: `universities_compact.json`, `national_series.json`,
`nra_index.csv.gz`, `level_rankings.json`, `search_index.bin`, `site_map.json`,
`hd_states.csv.gz`, `sheeo_state_compact.json.gz`.

None of the datasets built in the most recent work are in it, so the assistant
cannot answer from them or chart them.
