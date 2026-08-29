# Web asset audit

Regenerate with `python3 scripts/audit_web_assets.py`. Nothing here is
deleted automatically; this is a list to review.

## 1. Unreferenced assets — candidates for deletion

Nothing in the site links to these.

| Size | Path |
|---:|---|
| 4,878.6 KB | `dashboard_data.json` |
| 749.0 KB | `department_summary.json` |
| 276.0 KB | `android-chrome-512x512.png` |
| 133.4 KB | `funding_data.json` |
| 81.5 KB | `og-image.png` |
| 60.7 KB | `android-chrome-192x192.png` |
| 49.0 KB | `og-image-twitter.png` |
| 43.8 KB | `andy-avatar.jpeg` |
| 30.0 KB | `ipeds_field_demographics.json` |
| 22.0 KB | `caltech_dashboard_data.json` |
| 1.6 KB | `chat-admin.html` |

Total 6,325.7 KB across 11 files.

## 2. Published data, unreferenced on purpose

These are open-data publications. The methodology page cites them and the
report builders read them; no page fetches them, and that is correct.

| Size | Path |
|---:|---|
| 204.1 KB | `data/university_distribution.json` |
| 132.4 KB | `data/concentration_cases.json` |
| 120.3 KB | `data/legal_directory.json` |
| 82.4 KB | `data/us_states.json` |
| 74.6 KB | `data/chat/site_map.json` |
| 49.2 KB | `data/level_rankings.json` |
| 42.9 KB | `data/programme_shares.json` |
| 31.1 KB | `data/composition_change.json` |
| 23.7 KB | `data/completions_by_race.json` |
| 20.7 KB | `data/taxpayer_cost.json` |
| 13.8 KB | `data/taxonomy.json` |
| 12.1 KB | `data/tuition.json` |
| 9.3 KB | `data/live_bundle.json` |
| 9.3 KB | `data/domestic_pipeline.json` |
| 9.2 KB | `data/support_by_citizenship.json` |
| 7.3 KB | `data/institution_fields.json` |
| 7.1 KB | `data/stem_earnings.json` |
| 6.6 KB | `data/universities_index.json` |
| 5.9 KB | `data/long_series.json` |
| 3.1 KB | `data/sed_series.json` |
| 2.2 KB | `data/stay_rates.json` |
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
- `fica_exposure`
- `h1b_cap_exempt`
- `j1_scholars`
- `lca`
- `nonprofit_990s`
- `nra_index`
- `opt`
- `perm_pipeline`
- `workforce`

## 4. Legacy objects in S3

66 objects at the bucket root, 7.9 MB, from before
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
