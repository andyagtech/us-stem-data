#!/usr/bin/env python3
"""
Enrich per-university JSON files with enrollment, funding, and completion trend data.

Reads from:
  - data/nsf_gss/parsed/gss_enrollment_by_institution.csv (GSS enrollment by field)
  - data/ipeds/enrollment/grad_enrollment_demographics_2022.csv (IPEDS grad enrollment)
  - data/herd/funding_by_university.json (HERD R&D funding)
  - data/ipeds/c20{10..24}_a.csv (IPEDS completions by year)

Writes enriched JSON back to site/data/stem/<key>.json and site/data/nonstem/<key>.json
"""

import csv
import json
import os
import sys
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Manual key → UNITID mapping ──
# Built from data/master_stem_phd_institutions.csv cross-referenced with CONFIGS
KEY_TO_UNITID = {
    'auburn': 100858,
    'binghamton': 196079,
    'boise_state': 142115,
    'bu': 164988,
    'byu': 230038,
    'caltech': 110404,
    'clemson': 217882,
    'cmu': 211440,
    'columbia': 190150,
    'cornell': 190415,
    'cuny': 190576,  # CUNY Graduate School and University Center
    'dartmouth': 182670,
    'duke': 198419,
    'gatech': 139755,
    'gmu': 232186,
    'harvard': 166027,
    'iowa_state': 153603,
    'kstate': 155399,
    'la_tech': 159647,
    'lsu': 159391,
    'marquette': 239105,
    'mines': 126775,  # Colorado School of Mines
    'missouri_st': 178411,
    'mit': 166683,
    'msstate': 176080,
    'msu': 171100,
    'mtu': 171128,
    'nau': 105330,
    'ncstate': 199193,
    'niu': 147703,
    'njit': 185828,
    'northern_colorado': 127741,
    'northwestern': 147767,
    'olemiss': 176017,
    'oregon_state': 209542,
    'osu': 204796,
    'pdx': 209807,
    'penn_state': 214777,
    'purdue': 243780,
    'rice': 227757,
    'rit': 195003,
    'rpi': 194824,
    'sdsu': 219356,
    'siu': 149222,
    'smu': 228246,
    'stanford': 243744,
    'stony_brook': 196097,
    'syracuse': 196413,
    'temple': 216339,
    'ttu': 229115,
    'uarizona': 104179,
    'uarkansas': 106397,
    'ubuffalo': 196088,
    'ucberkeley': 110635,
    'ucdavis': 110644,
    'ucf': 132903,
    'ucirvine': 110653,
    'ucla': 110662,
    'ucmerced': 445188,
    'uconn': 129020,
    'ucriverside': 110671,
    'ucsb': 110705,
    'ucsc': 110714,
    'ucsd': 110680,
    'ucsf': 110699,
    'udel': 130943,
    'udenver': 127060,
    'uf': 134130,
    'uga': 139959,
    'uhouston': 225511,
    'uiuc': 145637,
    'ukansas': 155317,
    'uky': 157085,
    'ulouisville': 157289,
    'umass': 166629,
    'umd': 163286,
    'umemphis': 220862,
    'umissouri': 178396,
    'umn': 174066,
    'umt': 180489,
    'und': 200280,
    'unh': 183044,
    'unl': 181464,
    'unlv': 182281,
    'unm': 187985,
    'unt': 227216,
    'uoregon': 209551,
    'upenn': 215062,
    'usc_columbia': 218663,
    'usd': 219471,
    'usf': 137351,
    'usm': 176372,
    'utah_state': 230728,
    'utarlington': 228769,
    'utaustin': 228778,
    'utdallas': 228787,
    'utk': 221759,
    'uutah': 230764,
    'uva': 234076,
    'uw_seattle': 236948,
    'uwmadison': 240444,
    'vt': 233921,
    'washu': 179867,
    'wayne_state': 172644,
    'wsu': 236939,
    'wvu': 238032,
    'yale': 130794,
}

# Reverse mapping for lookups
UNITID_TO_KEYS = defaultdict(list)
for k, u in KEY_TO_UNITID.items():
    UNITID_TO_KEYS[u].append(k)


def safe_int(val):
    """Parse an int from a possibly quoted/flagged IPEDS value."""
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip().strip('"'))
    except (ValueError, TypeError):
        return 0


def load_gss_enrollment():
    """Load GSS enrollment data, aggregated by UNITID.

    Returns dict: unitid -> {
        total_grad, foreign, doctoral_total, doctoral_foreign,
        masters_total, masters_foreign,
        by_field: [{field, total, foreign, foreign_pct}]
    }
    """
    path = os.path.join(BASE_DIR, 'data/nsf_gss/parsed/gss_enrollment_by_institution.csv')
    if not os.path.exists(path):
        print(f"  WARN: GSS file not found: {path}")
        return {}

    result = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        # Group by unitid — use most recent year only
        by_unit = defaultdict(list)
        for row in reader:
            unitid = safe_int(row['unitid'])
            if unitid == 0:
                continue
            by_unit[unitid].append(row)

    for unitid, rows in by_unit.items():
        # Use most recent year
        max_year = max(safe_int(r['year']) for r in rows)
        rows = [r for r in rows if safe_int(r['year']) == max_year]

        total_grad = 0
        foreign = 0
        doctoral_total = 0
        doctoral_foreign = 0
        masters_total = 0
        masters_foreign = 0
        by_field = []

        for r in rows:
            t = safe_int(r['total_enrolled'])
            f = safe_int(r['total_foreign'])
            total_grad += t
            foreign += f
            doctoral_total += safe_int(r['doctoral_enrolled'])
            doctoral_foreign += safe_int(r['doctoral_foreign'])
            masters_total += safe_int(r['masters_enrolled'])
            masters_foreign += safe_int(r['masters_foreign'])

            field_name = r['field_name']
            if t > 0:
                by_field.append({
                    'field': field_name,
                    'total': t,
                    'foreign': f,
                    'foreign_pct': round(100 * f / t, 1) if t > 0 else 0,
                })

        # Sort by foreign count descending, keep top 10 for compactness
        by_field.sort(key=lambda x: x['foreign'], reverse=True)
        by_field = by_field[:10]

        result[unitid] = {
            'total_grad': total_grad,
            'foreign': foreign,
            'foreign_pct': round(100 * foreign / total_grad, 1) if total_grad > 0 else 0,
            'doctoral_total': doctoral_total,
            'doctoral_foreign': doctoral_foreign,
            'masters_total': masters_total,
            'masters_foreign': masters_foreign,
            'by_field': by_field,
        }

    print(f"  GSS enrollment: {len(result)} institutions loaded")
    return result


def load_ipeds_enrollment():
    """Load IPEDS grad enrollment demographics.

    Returns dict: unitid -> {total_grad, nra, nra_pct, asian, white, black, hispanic}
    """
    path = os.path.join(BASE_DIR, 'data/ipeds/enrollment/grad_enrollment_demographics_2022.csv')
    if not os.path.exists(path):
        print(f"  WARN: IPEDS enrollment file not found: {path}")
        return {}

    result = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            unitid = safe_int(row['unitid'])
            result[unitid] = {
                'total_grad': safe_int(row['total_grad']),
                'nra': safe_int(row['nra']),
                'nra_pct': float(row['nra_pct']),
                'asian': safe_int(row['asian']),
                'white': safe_int(row['white']),
                'black': safe_int(row['black']),
                'hispanic': safe_int(row['hispanic']),
            }

    print(f"  IPEDS enrollment: {len(result)} institutions loaded")
    return result


def load_h1b_data():
    """Load H-1B employer data hub (aggregated by university key).

    Returns dict: key -> {year -> {initial_approvals, initial_denials, continuing_approvals, continuing_denials}}
    """
    path = os.path.join(BASE_DIR, 'data/h1b/h1b_by_university.json')
    if not os.path.exists(path):
        print(f"  WARN: H-1B data not found: {path}")
        return {}
    with open(path) as f:
        raw = json.load(f)
    # Convert to compact format: yearly total approvals
    result = {}
    for key, years in raw.items():
        yearly = []
        for fy in sorted(years.keys()):
            if not fy or not fy.strip():
                continue
            counts = years[fy]
            yearly.append([
                int(fy),
                counts.get("initial_approvals", 0) + counts.get("continuing_approvals", 0),
                counts.get("initial_denials", 0) + counts.get("continuing_denials", 0),
            ])
        result[key] = yearly
    print(f"  H-1B data: {len(result)} institutions loaded")
    return result


def load_herd_funding():
    """Load HERD funding data (already keyed by university key).

    Returns dict: key -> compact funding dict
    """
    path = os.path.join(BASE_DIR, 'data/herd/funding_by_university.json')
    if not os.path.exists(path):
        print(f"  WARN: HERD funding file not found: {path}")
        return {}

    with open(path) as f:
        raw = json.load(f)

    result = {}
    for key, data in raw.items():
        # Extract compact version: yearly R&D and latest finance snapshot
        compact = {
            'name': data.get('name', ''),
            'rank': data.get('rank'),
        }
        if 'yearly_rd_thousands' in data:
            compact['rd'] = data['yearly_rd_thousands']
        if 'ipeds_finance_fy2023' in data:
            fin = data['ipeds_finance_fy2023']
            compact['finance'] = {
                'federal': fin.get('total_federal', 0),
                'state': fin.get('state_appropriations', 0),
                'tuition': fin.get('tuition_fees', 0),
                'total_revenue': fin.get('total_revenue', 0),
            }
        result[key] = compact

    print(f"  HERD funding: {len(result)} institutions loaded")
    return result


def load_ipeds_completions():
    """Load IPEDS completions for doctoral research degrees (AWLEVEL=17) by year.

    Returns dict: unitid -> {years: [...], phd_total: [...], phd_nra: [...]}
    """
    # Find all completion files c20{YY}_a.csv
    ipeds_dir = os.path.join(BASE_DIR, 'data/ipeds')
    comp_files = []
    for fname in sorted(os.listdir(ipeds_dir)):
        lower = fname.lower()
        # Match c20XX_a.csv but not c20XX_a_rv.csv
        if lower.startswith('c20') and lower.endswith('_a.csv'):
            year_str = lower[1:5]
            try:
                year = int(year_str)
                if 2010 <= year <= 2030:
                    comp_files.append((year, os.path.join(ipeds_dir, fname)))
            except ValueError:
                continue

    if not comp_files:
        print("  WARN: No IPEDS completions files found")
        return {}

    comp_files.sort()
    print(f"  IPEDS completions: {len(comp_files)} years ({comp_files[0][0]}-{comp_files[-1][0]})")

    # We only care about UNITIDs in our mapping
    target_unitids = set(KEY_TO_UNITID.values())

    # STEM CIP code prefixes (2-digit)
    STEM_CIPS = {'01','03','04','10','11','14','15','26','27','29','30','40','41','42','45','51'}

    # Aggregate by unitid and year: sum all CIPCODE rows where AWLEVEL=17
    # unitid -> year -> [total, nra, unknown, stem_total, stem_nra]
    data = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0]))

    for year, fpath in comp_files:
        with open(fpath, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                unitid = safe_int(row.get('UNITID', 0))
                if unitid not in target_unitids:
                    continue

                awlevel = str(row.get('AWLEVEL', '')).strip().strip('"')
                if awlevel != '17':
                    continue

                cipcode = str(row.get('CIPCODE', '')).strip()
                if cipcode == '99':
                    continue

                total = safe_int(row.get('CTOTALT', 0))
                nra = safe_int(row.get('CNRALT', 0))
                unknown = safe_int(row.get('CUNKNT', 0))

                data[unitid][year][0] += total
                data[unitid][year][1] += nra
                data[unitid][year][2] += unknown

                # Check if STEM
                cip2 = cipcode.split('.')[0] if '.' in cipcode else cipcode[:2]
                if cip2 in STEM_CIPS:
                    data[unitid][year][3] += total
                    data[unitid][year][4] += nra

    # Convert to compact arrays
    result = {}
    for unitid, year_data in data.items():
        years = sorted(year_data.keys())
        result[unitid] = {
            'years': years,
            'phd_total': [year_data[y][0] for y in years],
            'phd_nra': [year_data[y][1] for y in years],
            'phd_unknown': [year_data[y][2] for y in years],
            'phd_stem_total': [year_data[y][3] for y in years],
            'phd_stem_nra': [year_data[y][4] for y in years],
        }

    print(f"  IPEDS completions: {len(result)} institutions with doctoral data")
    return result


def load_tuition():
    """Load graduate tuition data from IPEDS IC."""
    result = {}
    fpath = os.path.join(BASE_DIR, 'data/ipeds/ic_tuition/grad_tuition_2023.csv')
    if not os.path.exists(fpath):
        print("  WARN: No tuition data found")
        return {}
    with open(fpath) as f:
        for row in csv.DictReader(f):
            uid = int(row.get('unitid', 0) or 0)
            if uid:
                result[uid] = {
                    'instate': int(row.get('grad_instate_tuition', 0) or 0) + int(row.get('grad_instate_fees', 0) or 0),
                    'outstate': int(row.get('grad_outstate_tuition', 0) or 0) + int(row.get('grad_outstate_fees', 0) or 0),
                }
    print(f"  Tuition: {len(result)} institutions loaded")
    return result


def load_financial_aid():
    """Load graduate financial aid data from IPEDS SFA."""
    result = {}
    fpath = os.path.join(BASE_DIR, 'data/ipeds/sfa/grad_aid_2223.csv')
    if not os.path.exists(fpath):
        print("  WARN: No financial aid data found")
        return {}
    with open(fpath) as f:
        for row in csv.DictReader(f):
            uid = int(row.get('unitid', 0) or 0)
            if uid:
                result[uid] = {
                    'grad_students': int(row.get('grad_students', 0) or 0),
                    'receiving_grants': int(row.get('receiving_grants_n', 0) or 0),
                    'grant_total': int(row.get('grant_total_amount', 0) or 0),
                    'grant_avg': int(row.get('grant_avg_amount', 0) or 0),
                    'fed_grants_n': int(row.get('receiving_fed_grants_n', 0) or 0),
                    'fed_grant_total': int(row.get('fed_grant_total', 0) or 0),
                }
    print(f"  Financial aid: {len(result)} institutions loaded")
    return result


def load_faculty():
    """Load faculty demographics from IPEDS HR."""
    result = {}
    fpath = os.path.join(BASE_DIR, 'data/ipeds/hr/faculty_demographics_2022.csv')
    if not os.path.exists(fpath):
        print("  WARN: No faculty data found")
        return {}
    with open(fpath) as f:
        for row in csv.DictReader(f):
            uid = int(row.get('unitid', 0) or 0)
            if uid:
                total = int(row.get('faculty_total', 0) or 0)
                nra = int(row.get('faculty_nra', 0) or 0)
                result[uid] = {
                    'total': total,
                    'nra': nra,
                    'nra_pct': round(nra / total * 100, 1) if total > 0 else 0,
                    'asian': int(row.get('faculty_asian', 0) or 0),
                    'white': int(row.get('faculty_white', 0) or 0),
                    'black': int(row.get('faculty_black', 0) or 0),
                    'hispanic': int(row.get('faculty_hispanic', 0) or 0),
                }
    print(f"  Faculty: {len(result)} institutions loaded")
    return result


def enrich_data_dir(data_dir, gss, ipeds_enroll, herd, completions, tuition=None, aid=None, faculty=None, h1b=None):
    """Enrich all university JSON files in data_dir."""
    enriched = 0
    skipped = 0

    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith('.json') or fname.startswith('_'):
            continue

        key = fname.replace('.json', '')
        fpath = os.path.join(data_dir, fname)

        with open(fpath) as f:
            uni_data = json.load(f)

        unitid = KEY_TO_UNITID.get(key)
        added = []

        # 1. Enrollment data (prefer GSS for by-field detail, fall back to IPEDS)
        if unitid and unitid in gss:
            uni_data['enrollment'] = gss[unitid]
            added.append('enrollment(GSS)')
        elif unitid and unitid in ipeds_enroll:
            # Use IPEDS enrollment as fallback (no by-field data)
            ie = ipeds_enroll[unitid]
            uni_data['enrollment'] = {
                'total_grad': ie['total_grad'],
                'foreign': ie['nra'],
                'foreign_pct': ie['nra_pct'],
                'demographics': {
                    'asian': ie['asian'],
                    'white': ie['white'],
                    'black': ie['black'],
                    'hispanic': ie['hispanic'],
                },
            }
            added.append('enrollment(IPEDS)')

        # 2. Funding data from HERD (keyed by our university key)
        if key in herd:
            uni_data['funding'] = herd[key]
            added.append('funding')
        # Handle HERD key mismatches (uci->ucirvine, ucr->ucriverside)
        elif key == 'ucirvine' and 'uci' in herd:
            uni_data['funding'] = herd['uci']
            added.append('funding')
        elif key == 'ucriverside' and 'ucr' in herd:
            uni_data['funding'] = herd['ucr']
            added.append('funding')

        # 3. Completions trend
        if unitid and unitid in completions:
            uni_data['completions_trend'] = completions[unitid]
            added.append('completions')

        # 4. Tuition data
        if tuition and unitid and unitid in tuition:
            uni_data['tuition'] = tuition[unitid]
            added.append('tuition')

        # 5. Financial aid
        if aid and unitid and unitid in aid:
            uni_data['financial_aid'] = aid[unitid]
            added.append('aid')

        # 6. Faculty demographics
        if faculty and unitid and unitid in faculty:
            uni_data['faculty'] = faculty[unitid]
            added.append('faculty')

        # 7. H-1B employer data
        if h1b and key in h1b:
            uni_data['h1b'] = h1b[key]
            added.append('h1b')

        # 8. OPT data (from SEVP PDF extraction)
        if hasattr(enrich_data_dir, '_opt') and key in enrich_data_dir._opt:
            uni_data['opt'] = enrich_data_dir._opt[key]
            added.append('opt')

        # 9. LCA summary data
        if hasattr(enrich_data_dir, '_lca') and key in enrich_data_dir._lca:
            uni_data['lca'] = enrich_data_dir._lca[key]
            added.append('lca')

        # 10. PERM green card data
        if hasattr(enrich_data_dir, '_perm') and key in enrich_data_dir._perm:
            uni_data['perm'] = enrich_data_dir._perm[key]
            added.append('perm')

        if added:
            # Write back compact JSON
            with open(fpath, 'w') as f:
                json.dump(uni_data, f, ensure_ascii=False, separators=(',', ':'))
            enriched += 1
        else:
            skipped += 1

        if added:
            print(f"    {key}: +{', '.join(added)}")
        else:
            if unitid is None:
                print(f"    {key}: SKIP (no UNITID mapping)")
            else:
                print(f"    {key}: SKIP (no matching data for UNITID {unitid})")

    return enriched, skipped


def main():
    print("Loading enrichment data sources...")
    gss = load_gss_enrollment()
    ipeds_enroll = load_ipeds_enrollment()
    herd = load_herd_funding()
    completions = load_ipeds_completions()
    tuition = load_tuition()
    aid = load_financial_aid()
    faculty = load_faculty()
    h1b = load_h1b_data()

    # Load OPT and LCA data
    opt_path = os.path.join(BASE_DIR, 'data/h1b/opt_by_university.json')
    if os.path.exists(opt_path):
        with open(opt_path) as f:
            enrich_data_dir._opt = json.load(f)
        print(f"  OPT data: {len(enrich_data_dir._opt)} institutions loaded")
    else:
        enrich_data_dir._opt = {}

    lca_path = os.path.join(BASE_DIR, 'data/h1b/lca_by_university.json')
    if os.path.exists(lca_path):
        with open(lca_path) as f:
            enrich_data_dir._lca = json.load(f)
        print(f"  LCA data: {len(enrich_data_dir._lca)} institutions loaded")
    else:
        enrich_data_dir._lca = {}

    perm_path = os.path.join(BASE_DIR, 'data/h1b/perm_by_university.json')
    if os.path.exists(perm_path):
        with open(perm_path) as f:
            enrich_data_dir._perm = json.load(f)
        print(f"  PERM data: {len(enrich_data_dir._perm)} institutions loaded")
    else:
        enrich_data_dir._perm = {}

    for label, data_dir in [
        ("STEM", os.path.join(BASE_DIR, "site/data/stem")),
        ("NON-STEM", os.path.join(BASE_DIR, "site/data/nonstem")),
    ]:
        if not os.path.isdir(data_dir):
            print(f"\n{label}: directory not found ({data_dir}), skipping")
            continue
        print(f"\n=== Enriching {label} ({data_dir}) ===")
        enriched, skipped = enrich_data_dir(data_dir, gss, ipeds_enroll, herd, completions, tuition, aid, faculty, h1b)
        print(f"  {label}: {enriched} enriched, {skipped} skipped")

    print("\nDone.")


if __name__ == "__main__":
    main()
