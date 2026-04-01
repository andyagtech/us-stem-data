#!/usr/bin/env python3
"""Rank universities by NRA and Asian STEM PhD counts from IPEDS data.
Cross-reference with existing scraped repos to identify priority targets."""

import csv
import os
import json
from collections import defaultdict

# ── Load institution names ──
institutions = {}
for enc in ['utf-8-sig', 'latin-1', 'cp1252']:
    try:
        with open('data/ipeds/HD2024.csv', encoding=enc, errors='replace') as f:
            for row in csv.DictReader(f):
                uid = row.get('UNITID', '').strip()
                institutions[uid] = {
                    'name': row.get('INSTNM', '').strip(),
                    'state': row.get('STABBR', '').strip(),
                    'city': row.get('CITY', '').strip(),
                }
        break
    except:
        continue

# ── Aggregate NRA and Asian PhD counts (AWLEVEL=17, STEM CIPs, 2015-2024) ──
stem_cips = {'11', '14', '15', '26', '27', '30', '40', '42'}
counts = defaultdict(lambda: {
    'total': 0, 'nra': 0, 'asian': 0, 'stem_total': 0, 'stem_nra': 0, 'stem_asian': 0
})

for year in range(2015, 2025):
    fname = f'data/ipeds/C{year}_A.csv'
    if not os.path.exists(fname):
        continue
    with open(fname, encoding='latin-1', errors='replace') as f:
        for row in csv.DictReader(f):
            uid = row.get('UNITID', '').strip()
            if uid not in institutions:
                continue
            if row.get('AWLEVEL', '').strip() != '17':
                continue
            cip = row.get('CIPCODE', '').strip()

            def safe_int(v):
                try:
                    return int(v)
                except:
                    return 0

            total = safe_int(row.get('CTOTALT', 0))
            nra = safe_int(row.get('CNRALT', 0))
            asian = safe_int(row.get('CASIAT', 0))

            if cip == '99':
                counts[uid]['total'] += total
                counts[uid]['nra'] += nra
                counts[uid]['asian'] += asian
            else:
                cip2 = cip.split('.')[0]
                if cip2 in stem_cips:
                    counts[uid]['stem_total'] += total
                    counts[uid]['stem_nra'] += nra
                    counts[uid]['stem_asian'] += asian

# ── Check which repos we already have ──
existing_repos = set()
repo_rows = {}
oai_dir = 'data/western_us_dissertations'
if os.path.exists(oai_dir):
    for f in os.listdir(oai_dir):
        if f.endswith('_etds.csv'):
            repo = f[:-9]
            try:
                rows = sum(1 for _ in open(os.path.join(oai_dir, f))) - 1
            except:
                rows = 0
            repo_rows[repo] = rows
            existing_repos.add(repo)

# Also check other scraped dirs
other_scraped = {}
for d, label in [
    ('data/uc_dissertations', 'UC system'),
    ('data/stanford_dissertations', 'Stanford'),
    ('data/uw_dissertations', 'UW Seattle'),
    ('data/or_wa_dissertations', 'OR/WA'),
]:
    if os.path.exists(d):
        for f in os.listdir(d):
            if f.endswith('.csv'):
                try:
                    rows = sum(1 for _ in open(os.path.join(d, f))) - 1
                    other_scraped[f] = (label, rows)
                except:
                    pass

# ── Known repo key → UNITID mapping ──
# Map repo keys to institution names for cross-reference
repo_name_map = {
    'uarizona': 'University of Arizona',
    'byu': 'Brigham Young University',
    'boise_state': 'Boise State University',
    'mines': 'Colorado School of Mines',
    'udenver': 'University of Denver',
    'unlv': 'University of Nevada-Las Vegas',
    'umt': 'University of Montana',
    'utah_state': 'Utah State University',
    'unm': 'University of New Mexico',
    'northern_colorado': 'University of Northern Colorado',
    'oregon_state': 'Oregon State University',
    'iowa_state': 'Iowa State University',
    'washu': 'Washington University in St Louis',
    'missouri_st': 'Missouri University of Science and Technology',
    'ukansas': 'University of Kansas',
    'kstate': 'Kansas State University',
    'unl': 'University of Nebraska-Lincoln',
    'und': 'University of North Dakota',
    'sdsu': 'South Dakota State University',
    'usd': 'University of South Dakota',
    'uarkansas': 'University of Arkansas',
    'lsu': 'Louisiana State University',
    'la_tech': 'Louisiana Tech University',
    'marquette': 'Marquette University',
    'siu': 'Southern Illinois University Carbondale',
    'niu': 'Northern Illinois University',
    'purdue': 'Purdue University',
    'uky': 'University of Kentucky',
    'ulouisville': 'University of Louisville',
    'umemphis': 'University of Memphis',
    'msstate': 'Mississippi State University',
    'olemiss': 'University of Mississippi',
    'usm': 'University of Southern Mississippi',
    'wayne_state': 'Wayne State University',
    'wmich': 'Western Michigan University',
    'mtu': 'Michigan Technological University',
    'bgsu': 'Bowling Green State University',
    'upenn': 'University of Pennsylvania',
    'njit': 'New Jersey Institute of Technology',
    'wvu': 'West Virginia University',
    'ncstate': 'North Carolina State University',
    'duke': 'Duke University',
    'clemson': 'Clemson University',
    'usc_columbia': 'University of South Carolina',
    'usf': 'University of South Florida',
    'ucf': 'University of Central Florida',
    'fau': 'Florida Atlantic University',
    'harvard': 'Harvard University',
    'bu': 'Boston University',
    'syracuse': 'Syracuse University',
    'cuny': 'City University of New York',
    'yale': 'Yale University',
    'uconn': 'University of Connecticut',
    'dartmouth': 'Dartmouth College',
    'unh': 'University of New Hampshire',
    'umaine': 'University of Maine',
    'uri': 'University of Rhode Island',
    'unt': 'University of North Texas',
    'smu': 'Southern Methodist University',
    'uhawaii': 'University of Hawaii at Manoa',
}

# Build set of scraped institution names (lowercase for matching)
scraped_names = set()
for name in repo_name_map.values():
    scraped_names.add(name.lower())
# Add UC, Stanford, UW, PSU, WSU, UO
scraped_names.update([
    'university of california-berkeley', 'university of california-los angeles',
    'university of california-san diego', 'university of california-davis',
    'university of california-santa barbara', 'university of california-irvine',
    'university of california-santa cruz', 'university of california-riverside',
    'university of california-merced',
    'stanford university', 'university of washington-seattle campus',
    'portland state university', 'washington state university',
    'university of oregon',
])

# ── Build rankings ──
exclude = ['seminary', 'theological', 'bible', 'divinity', 'phoenix', 'walden',
           'capella', 'trident', 'northcentral']

results = []
for uid, c in counts.items():
    if c['total'] < 50:
        continue
    inst = institutions.get(uid, {})
    name = inst.get('name', 'Unknown')
    if any(e in name.lower() for e in exclude):
        continue
    
    # Check if scraped
    scraped = name.lower() in scraped_names
    scraped_rows = 0
    if scraped:
        # Try to find the row count
        for repo, rname in repo_name_map.items():
            if rname.lower() == name.lower():
                scraped_rows = repo_rows.get(repo, 0)
                break
    
    results.append({
        'uid': uid,
        'name': name,
        'state': inst.get('state', ''),
        'city': inst.get('city', ''),
        **c,
        'scraped': scraped,
        'scraped_rows': scraped_rows,
    })

# ── Output rankings ──
output = []
output.append("=" * 130)
output.append("TOP UNIVERSITIES BY NRA + ASIAN STEM PhD COUNTS (2015-2024)")
output.append("Source: IPEDS AWLEVEL=17, CIP families: CS, Engineering, Bio, Math, Physical Sci, Psychology, Interdisciplinary")
output.append("=" * 130)

# Sort by STEM NRA + STEM Asian
results.sort(key=lambda x: -(x['stem_nra'] + x['stem_asian']))

output.append(f"\n{'Rank':<5} {'University':<48} {'ST':<4} {'STEM':>6} {'NRA':>6} {'Asian':>6} {'NRA+A':>7} {'%NRA':>6} {'Scraped':>10} {'Rows':>8}")
output.append("-" * 115)

for i, r in enumerate(results[:100], 1):
    nra_asian = r['stem_nra'] + r['stem_asian']
    nra_pct = (r['stem_nra'] / r['stem_total'] * 100) if r['stem_total'] > 0 else 0
    scraped_str = "YES" if r['scraped'] else "NO"
    rows_str = f"{r['scraped_rows']:,}" if r['scraped_rows'] > 0 else ""
    output.append(f"{i:<5} {r['name'][:48]:<48} {r['state']:<4} {r['stem_total']:>6,} {r['stem_nra']:>6,} {r['stem_asian']:>6,} {nra_asian:>7,} {nra_pct:>5.1f}% {scraped_str:>10} {rows_str:>8}")

# ── Not-yet-scraped priority list ──
not_scraped = [r for r in results if not r['scraped']]
not_scraped.sort(key=lambda x: -(x['stem_nra'] + x['stem_asian']))

output.append(f"\n\n{'=' * 130}")
output.append("PRIORITY TARGETS: NOT YET SCRAPED — sorted by STEM NRA + Asian count")
output.append("=" * 130)
output.append(f"\n{'Rank':<5} {'University':<48} {'ST':<4} {'STEM':>6} {'NRA':>6} {'Asian':>6} {'NRA+A':>7} {'%NRA':>6}")
output.append("-" * 95)

for i, r in enumerate(not_scraped[:60], 1):
    nra_asian = r['stem_nra'] + r['stem_asian']
    nra_pct = (r['stem_nra'] / r['stem_total'] * 100) if r['stem_total'] > 0 else 0
    output.append(f"{i:<5} {r['name'][:48]:<48} {r['state']:<4} {r['stem_total']:>6,} {r['stem_nra']:>6,} {r['stem_asian']:>6,} {nra_asian:>7,} {nra_pct:>5.1f}%")

# ── Summary stats ──
total_stem_nra = sum(r['stem_nra'] for r in results)
total_stem_asian = sum(r['stem_asian'] for r in results)
scraped_stem_nra = sum(r['stem_nra'] for r in results if r['scraped'])
scraped_stem_asian = sum(r['stem_asian'] for r in results if r['scraped'])

output.append(f"\n\n{'=' * 130}")
output.append("COVERAGE SUMMARY")
output.append("=" * 130)
output.append(f"Total STEM NRA PhDs (2015-2024): {total_stem_nra:,}")
output.append(f"Total STEM Asian PhDs (2015-2024): {total_stem_asian:,}")
output.append(f"Scraped STEM NRA PhDs: {scraped_stem_nra:,} ({scraped_stem_nra/total_stem_nra*100:.1f}%)")
output.append(f"Scraped STEM Asian PhDs: {scraped_stem_asian:,} ({scraped_stem_asian/total_stem_asian*100:.1f}%)")
output.append(f"Total universities in ranking: {len(results)}")
output.append(f"Universities scraped: {sum(1 for r in results if r['scraped'])}")
output.append(f"Universities NOT scraped: {len(not_scraped)}")

text = "\n".join(output)
print(text)

with open('data/ipeds_nra_asian_ranking.txt', 'w') as f:
    f.write(text)
print(f"\nSaved to data/ipeds_nra_asian_ranking.txt")
