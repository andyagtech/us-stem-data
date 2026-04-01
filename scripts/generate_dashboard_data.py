#!/usr/bin/env python3
"""Generate JSON data for the STEM PhD classification dashboard."""

import csv, os, sys, json, re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from name_classifier import classify
from classify_all_datasets import is_stem

BASE_DIR = os.path.join(SCRIPT_DIR, '..')
DATA_DIR = os.path.join(BASE_DIR, 'data', 'western_us_dissertations')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'dashboard_data.json')


def extract_department(row, repo):
    contrib = (row.get('contributor', '') or '').strip()
    if repo == 'vt' and ';' in contrib:
        dept = contrib.split(';')[0].strip()
        return dept.replace('Department of ', '').replace('Dept. of ', '')
    if repo == 'mit' and 'Massachusetts Institute of Technology' in contrib:
        m = re.search(r'(?:Department|Dept\.?) (?:of )?(.+?)(?:\.|$)', contrib)
        if m:
            return m.group(1).strip().rstrip('.')
    if repo == 'gatech' and ';' in contrib:
        parts = [p.strip() for p in contrib.split(';')]
        for p in parts[1:3]:
            if any(kw in p.lower() for kw in ['engineering', 'science', 'physics', 'chemistry',
                   'biology', 'mathematics', 'computing', 'psychology', 'biomedical',
                   'textile', 'fiber', 'earth', 'atmospheric']):
                return p
    return None


def classify_broad_field(dept_str, subject_str):
    text = ((dept_str or '') + ' ' + (subject_str or '')).lower()
    if any(k in text for k in ['computer science', 'computing', 'computer engineering',
           'informatics', 'data science', 'artificial intelligence', 'software',
           'machine learning', 'deep learning', 'neural network', 'data mining',
           'computer vision', 'natural language', 'cyber', 'database']):
        return 'Computer Science'
    if any(k in text for k in ['electrical', 'electronics', 'ece ', 'vlsi', 'circuit',
           'antenna', 'signal processing', 'wireless', 'ofdm', 'mimo',
           'semiconductor', 'power system', 'electromagnet']):
        return 'Electrical Engineering'
    if any(k in text for k in ['mechanical engineering', 'mechanics', 'vibration',
           'turbulence', 'fluid dynamics', 'heat transfer', 'combustion',
           'thermodynamic', 'mems', 'tribology']):
        return 'Mechanical Engineering'
    if any(k in text for k in ['chemical engineering', 'reaction kinetics', 'reactor',
           'polymer', 'membrane', 'catalysis', 'fluidization']):
        return 'Chemical Engineering'
    if any(k in text for k in ['civil engineering', 'structural engineering',
           'transportation engineering', 'environmental engineering',
           'geotechnical', 'construction', 'pavement']):
        return 'Civil/Environmental Eng.'
    if any(k in text for k in ['biomedical engineering', 'bioengineering']):
        return 'Biomedical Engineering'
    if any(k in text for k in ['aerospace', 'aeronautics', 'astronautics']):
        return 'Aerospace Engineering'
    if any(k in text for k in ['materials science', 'metallurg']):
        return 'Materials Science'
    if any(k in text for k in ['industrial engineering', 'operations research',
           'systems engineering', 'industrial and systems']):
        return 'Industrial/Systems Eng.'
    if any(k in text for k in ['nuclear engineering']):
        return 'Nuclear Engineering'
    if 'engineering' in text:
        return 'Other Engineering'
    if any(k in text for k in ['chemistry', 'biochemistry', 'electrochemist',
           'synthesis', 'spectroscop']):
        return 'Chemistry/Biochemistry'
    if any(k in text for k in ['physics', 'astrophysics', 'astronomy', 'optics',
           'quantum', 'photon', 'laser', 'plasma']):
        return 'Physics/Astronomy'
    if any(k in text for k in ['mathematics', 'mathematical', 'statistics',
           'applied math', 'probability', 'stochastic']):
        return 'Mathematics/Statistics'
    if any(k in text for k in ['biology', 'biological', 'genetics', 'genomics',
           'ecology', 'microbiology', 'neuroscience', 'molecular',
           'bioinformatics', 'zoology', 'botany', 'entomology',
           'plant', 'animal science', 'crop', 'soil', 'agronomy',
           'food science', 'nutrition', 'fisheries', 'wildlife']):
        return 'Biological Sciences'
    if any(k in text for k in ['geology', 'geoscience', 'geophysics',
           'earth science', 'atmospheric', 'oceanograph', 'meteorolog',
           'climate', 'environmental science']):
        return 'Earth/Atmospheric Sci.'
    if any(k in text for k in ['psychology', 'cognitive', 'behavioral']):
        return 'Psychology'
    if any(k in text for k in ['public health', 'epidemiology', 'pharmacology',
           'pharmaceutical']):
        return 'Public Health/Pharma'
    return 'Unknown STEM'


def main():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('_etds.csv')])

    # Aggregation structures
    universities = []
    fields_agg = defaultdict(lambda: [0, 0, 0, 0, 0])  # total, chi, ind, kor, viet
    yearly_agg = defaultdict(lambda: [0, 0, 0, 0, 0])
    uni_yearly = {}
    uni_fields = {}
    classified_names = []
    njit_all = []

    # University name map
    uni_names = {}

    for fname in files:
        repo = fname.replace('_etds.csv', '')
        path = os.path.join(DATA_DIR, fname)

        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                rows = list(csv.DictReader(f))
        except Exception:
            continue

        if not rows:
            continue

        uni_name = rows[0].get('university', repo)
        uni_names[repo] = uni_name

        stats = [0, 0, 0, 0, 0, 0, 0]  # total, stem, chi, ind, kor, viet, chi_high
        uy = defaultdict(lambda: [0, 0, 0, 0, 0])
        uf = defaultdict(lambda: [0, 0, 0, 0, 0])

        for r in rows:
            stats[0] += 1
            if not is_stem(r):
                continue
            stats[1] += 1

            author = r.get('creator', '').strip()
            if not author:
                continue
            cat, conf = classify(author)
            date = (r.get('date', '') or '')[:4]

            dept = extract_department(r, repo)
            subject = r.get('subject', '')
            broad_field = classify_broad_field(dept, subject)

            # Map category to index
            ci = {'chinese': 0, 'indian': 1, 'korean': 2, 'vietnamese': 3}.get(cat, -1)

            if ci >= 0:
                stats[2 + ci] += 1
                if ci == 0 and conf == 'high':
                    stats[6] += 1

                fields_agg[broad_field][1 + ci] += 1
                uf[broad_field][1 + ci] += 1

                classified_names.append([
                    repo, author, ci, 1 if conf == 'high' else 0,
                    date, broad_field
                ])

                if date.isdigit() and 2015 <= int(date) <= 2025:
                    yearly_agg[date][1 + ci] += 1
                    uy[date][1 + ci] += 1

            fields_agg[broad_field][0] += 1
            uf[broad_field][0] += 1

            if date.isdigit() and 2015 <= int(date) <= 2025:
                yearly_agg[date][0] += 1
                uy[date][0] += 1

            # NJIT: save ALL records for department drill-down
            if repo == 'njit':
                rec_title = (r.get('title', '') or '').strip()
                njit_all.append([
                    author, ci, 1 if conf == 'high' else 0,
                    date, broad_field, rec_title
                ])

        universities.append({
            'k': repo, 'n': uni_name,
            't': stats[0], 's': stats[1],
            'c': stats[2], 'i': stats[3],
            'kr': stats[4], 'v': stats[5],
            'ch': stats[6],
        })

        uni_yearly[repo] = {yr: vals for yr, vals in sorted(uy.items())}
        uni_fields[repo] = {fld: vals for fld, vals in sorted(uf.items(), key=lambda x: -x[1][0])}

    # Sort universities by Chinese count descending
    universities.sort(key=lambda u: -u['c'])

    # Build output
    data = {
        'universities': universities,
        'uni_names': uni_names,
        'fields': {k: v for k, v in sorted(fields_agg.items(), key=lambda x: -x[1][1]/max(x[1][0],1))},
        'yearly': {k: v for k, v in sorted(yearly_agg.items())},
        'uni_yearly': uni_yearly,
        'uni_fields': uni_fields,
        'classified': classified_names,
        'njit_all': njit_all,
        'meta': {
            'total_records': sum(u['t'] for u in universities),
            'stem_records': sum(u['s'] for u in universities),
            'total_chinese': sum(u['c'] for u in universities),
            'total_indian': sum(u['i'] for u in universities),
            'total_korean': sum(u['kr'] for u in universities),
            'total_viet': sum(u['v'] for u in universities),
            'num_universities': len([u for u in universities if u['s'] > 0]),
        }
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    size_mb = os.path.getsize(OUTPUT_JSON) / 1024 / 1024
    print(f"Dashboard data written to {OUTPUT_JSON} ({size_mb:.1f} MB)")
    print(f"  Universities: {len(universities)}")
    print(f"  Classified names: {len(classified_names):,}")
    print(f"  NJIT all records: {len(njit_all):,}")
    print(f"  Fields: {len(fields_agg)}")
    print(f"  Years: {sorted(yearly_agg.keys())}")


if __name__ == '__main__':
    main()
