#!/usr/bin/env python3
"""
Classify names from high-NRA university OAI harvests.
Produces per-university summaries and a cross-university comparison.
"""

import csv
import sys
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from name_classifier import classify, get_surname

# ── Datasets to classify ──
DATASETS = [
    {
        "key": "missouri_st",
        "name": "Missouri S&T",
        "nra_pct": 73.2,
        "file": "data/western_us_dissertations/missouri_st_etds.csv",
    },
    {
        "key": "mtu",
        "name": "Michigan Tech",
        "nra_pct": 62.0,
        "file": "data/western_us_dissertations/mtu_etds.csv",
    },
    {
        "key": "sdsu",
        "name": "SD State",
        "nra_pct": 59.6,
        "file": "data/western_us_dissertations/sdsu_etds.csv",
    },
    {
        "key": "utdallas",
        "name": "UT Dallas",
        "nra_pct": 59.3,
        "file": "data/western_us_dissertations/utdallas_etds.csv",
    },
    {
        "key": "rit",
        "name": "RIT",
        "nra_pct": 57.3,
        "file": "data/western_us_dissertations/rit_etds.csv",
    },
    {
        "key": "erau",
        "name": "Embry-Riddle",
        "nra_pct": 52.3,
        "file": "data/western_us_dissertations/erau_etds.csv",
    },
    {
        "key": "stony_brook",
        "name": "Stony Brook",
        "nra_pct": 49.6,
        "file": "data/western_us_dissertations/stony_brook_etds.csv",
    },
    {
        "key": "rpi",
        "name": "RPI",
        "nra_pct": 48.7,
        "file": "data/western_us_dissertations/rpi_etds.csv",
    },
    # ── New harvests (Mar 10 2026 afternoon) ──
    {
        "key": "upenn",
        "name": "U Pennsylvania",
        "nra_pct": 31.6,
        "file": "data/western_us_dissertations/upenn_etds.csv",
    },
    {
        "key": "cuny",
        "name": "CUNY Grad Center",
        "nra_pct": 0.0,
        "file": "data/western_us_dissertations/cuny_etds.csv",
    },
    {
        "key": "umissouri",
        "name": "U Missouri",
        "nra_pct": 50.2,
        "file": "data/western_us_dissertations/umissouri_etds.csv",
    },
    {
        "key": "nau",
        "name": "Northern Arizona",
        "nra_pct": 17.0,
        "file": "data/western_us_dissertations/nau_etds.csv",
    },
    {
        "key": "smu",
        "name": "SMU",
        "nra_pct": 0.0,
        "file": "data/western_us_dissertations/smu_etds.csv",
    },
    {
        "key": "uri",
        "name": "U Rhode Island",
        "nra_pct": 0.0,
        "file": "data/western_us_dissertations/uri_etds.csv",
    },
]


def extract_year(date_str):
    """Extract 4-digit year from a date string."""
    if not date_str:
        return None
    m = re.search(r'(\d{4})', date_str)
    return int(m.group(1)) if m else None


def is_likely_phd(record):
    """
    Heuristic to filter for doctoral dissertations vs master's theses.
    Uses type, description, title, and subject fields.
    """
    title = (record.get('title') or '').lower()
    desc = (record.get('description') or '').lower()
    typ = (record.get('type') or '').lower()
    subj = (record.get('subject') or '').lower()
    oai_set = (record.get('oai_set') or '').lower()

    # Strong PhD signals
    if 'dissert' in oai_set:
        return True
    if 'dissertation' in typ or 'doctoral' in typ:
        return True
    if 'dissertation' in desc[:200]:
        return True

    # Strong master's signals → exclude
    if 'master' in typ or 'thesis' in typ:
        if 'dissert' not in typ:
            return False
    if desc.startswith('a thesis') or desc.startswith('thesis'):
        return False

    # For repos that mix everything (like UT Dallas DSpace), be conservative
    return None  # unknown


def load_and_classify(dataset):
    """Load CSV and classify all records. Returns list of classified records."""
    filepath = dataset["file"]
    records = []

    with open(filepath, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            creator = row.get('creator', '').strip()
            if not creator:
                continue

            # Some records have multiple creators separated by semicolons
            # Use the first one (primary author)
            if ';' in creator:
                creator = creator.split(';')[0].strip()

            cat, conf = classify(creator)
            year = extract_year(row.get('date', ''))
            phd_flag = is_likely_phd(row)

            records.append({
                'name': creator,
                'classification': cat,
                'confidence': conf,
                'year': year,
                'title': row.get('title', ''),
                'subject': row.get('subject', ''),
                'type': row.get('type', ''),
                'description': (row.get('description', '') or '')[:200],
                'is_phd': phd_flag,
                'oai_set': row.get('oai_set', ''),
            })

    return records


def print_university_report(dataset, records):
    """Print detailed classification report for one university."""
    name = dataset["name"]
    nra_pct = dataset["nra_pct"]

    print(f"\n{'='*70}")
    print(f"  {name}  (IPEDS NRA: {nra_pct}%)")
    print(f"{'='*70}")
    print(f"  Total OAI records: {len(records)}")

    # Filter to likely PhDs if possible
    phd_records = [r for r in records if r['is_phd'] is True]
    non_phd = [r for r in records if r['is_phd'] is False]
    unknown = [r for r in records if r['is_phd'] is None]

    print(f"  Likely PhDs: {len(phd_records)}  |  Likely Master's: {len(non_phd)}  |  Unknown: {len(unknown)}")

    # Use all records for classification (most bepress repos are dissertation-only sets)
    # but flag the split
    for label, subset in [("ALL RECORDS", records), ("LIKELY PhDs ONLY", phd_records)]:
        if not subset:
            continue
        if label == "LIKELY PhDs ONLY" and len(phd_records) == 0:
            continue
        if label == "LIKELY PhDs ONLY" and len(phd_records) == len(records):
            continue  # Same as all records

        print(f"\n  ── {label} ({len(subset)} records) ──")

        cls = Counter(r['classification'] for r in subset)
        print(f"  Classification breakdown:")
        for c, n in cls.most_common():
            print(f"    {c:<25} {n:>6} ({n/len(subset)*100:>5.1f}%)")

        # Chinese by confidence
        ch_high = len([r for r in subset if r['classification'] == 'chinese' and r['confidence'] == 'high'])
        ch_med = len([r for r in subset if r['classification'] == 'chinese' and r['confidence'] == 'medium'])
        ch_total = ch_high + ch_med
        print(f"\n  Chinese names: {ch_total} total ({ch_total/len(subset)*100:.1f}%)")
        print(f"    High confidence: {ch_high}  |  Medium: {ch_med}")

        # Indian
        ind_total = len([r for r in subset if r['classification'] == 'indian'])
        print(f"  Indian names: {ind_total} ({ind_total/len(subset)*100:.1f}%)")

        # Korean + Vietnamese
        kor = len([r for r in subset if r['classification'] == 'korean'])
        viet = len([r for r in subset if r['classification'] == 'vietnamese'])
        print(f"  Korean: {kor} ({kor/len(subset)*100:.1f}%)  |  Vietnamese: {viet} ({viet/len(subset)*100:.1f}%)")

        # Combined Asian-origin estimate
        asian_est = ch_total + ind_total + kor + viet
        print(f"  Est. Asian-origin total: {asian_est} ({asian_est/len(subset)*100:.1f}%)")

        # By year (recent 10 years)
        years = sorted(set(r['year'] for r in subset if r['year'] and r['year'] >= 2015))
        if years:
            print(f"\n  Year breakdown (2015+):")
            print(f"  {'Year':>6} {'Total':>6} {'Chinese':>8} {'%':>6} {'Indian':>8} {'%':>6} {'Kor+Viet':>8} {'Other':>6}")
            print(f"  {'-'*62}")
            for yr in years:
                yr_recs = [r for r in subset if r['year'] == yr]
                ch = len([r for r in yr_recs if r['classification'] == 'chinese'])
                ind = len([r for r in yr_recs if r['classification'] == 'indian'])
                kv = len([r for r in yr_recs if r['classification'] in ('korean', 'vietnamese')])
                oth = len(yr_recs) - ch - ind - kv
                t = len(yr_recs)
                print(f"  {yr:>6} {t:>6} {ch:>8} {ch/t*100:>5.1f}% {ind:>8} {ind/t*100:>5.1f}% {kv:>8} {oth:>6}")

    # Sample Chinese names (recent)
    recent_chinese = [r for r in records if r['classification'] == 'chinese'
                      and r['year'] and r['year'] >= 2020]
    if recent_chinese:
        print(f"\n  Sample Chinese names (2020+, first 15):")
        for r in recent_chinese[:15]:
            print(f"    {r['year']}  {r['name']:<35} [{r['confidence']}]  {r['title'][:60]}")

    # Sample Indian names
    recent_indian = [r for r in records if r['classification'] == 'indian'
                     and r['year'] and r['year'] >= 2020]
    if recent_indian:
        print(f"\n  Sample Indian names (2020+, first 10):")
        for r in recent_indian[:10]:
            print(f"    {r['year']}  {r['name']:<35} [{r['confidence']}]  {r['title'][:60]}")

    return {
        'total': len(records),
        'phd_likely': len(phd_records),
        'chinese': len([r for r in records if r['classification'] == 'chinese']),
        'chinese_high': ch_high if records else 0,
        'indian': len([r for r in records if r['classification'] == 'indian']),
        'korean': len([r for r in records if r['classification'] == 'korean']),
        'vietnamese': len([r for r in records if r['classification'] == 'vietnamese']),
        'other': len([r for r in records if r['classification'] == 'other']),
        'excluded': len([r for r in records if r['classification'] == 'excluded_ambiguous']),
    }


def main():
    print("HIGH-NRA UNIVERSITY NAME CLASSIFICATION REPORT")
    print("=" * 70)
    print("Using name_classifier.py to classify OAI-harvested dissertation authors")
    print("Comparing with IPEDS NRA percentages (2015-2024)\n")

    all_stats = []

    for ds in DATASETS:
        if not Path(ds["file"]).exists():
            print(f"\n  SKIPPING {ds['name']}: {ds['file']} not found")
            continue

        records = load_and_classify(ds)
        stats = print_university_report(ds, records)
        stats['name'] = ds['name']
        stats['nra_pct'] = ds['nra_pct']
        all_stats.append(stats)

    # ── Cross-university comparison ──
    print(f"\n\n{'='*70}")
    print(f"  CROSS-UNIVERSITY COMPARISON")
    print(f"{'='*70}")
    print(f"  {'University':<20} {'NRA%':>5} {'Total':>7} {'Chinese':>8} {'%':>6} {'Indian':>8} {'%':>6} {'K+V':>5} {'Other':>7}")
    print(f"  {'-'*75}")

    for s in sorted(all_stats, key=lambda x: -x['nra_pct']):
        t = s['total']
        ch = s['chinese']
        ind = s['indian']
        kv = s['korean'] + s['vietnamese']
        oth = s['other'] + s['excluded']
        print(f"  {s['name']:<20} {s['nra_pct']:>5.1f} {t:>7} {ch:>8} {ch/t*100:>5.1f}% {ind:>8} {ind/t*100:>5.1f}% {kv:>5} {oth:>7}")

    print(f"\n  Note: These datasets include BOTH master's theses and doctoral dissertations")
    print(f"  from OAI repositories. The IPEDS NRA% is for PhDs only (2015-2024).")
    print(f"  Chinese + Indian + Korean + Vietnamese names approximate but don't equal NRA")
    print(f"  (NRA also includes Middle Eastern, African, Latin American students).")


if __name__ == "__main__":
    main()
