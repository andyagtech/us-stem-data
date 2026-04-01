#!/usr/bin/env python3
"""
Classify all harvested dissertation datasets by author name ethnicity.
Filters to STEM fields first, then runs Chinese/Indian/Korean/Vietnamese classifiers.

Usage:
    python3 scripts/classify_all_datasets.py [--all] [--stem-only] [--output FILE]

Default: STEM-only classification across all datasets.
"""

import csv
import os
import sys
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from name_classifier import classify

# ── STEM keyword lists for field filtering ──
# These match against subject, contributor (department), title, and description fields.

STEM_DEPARTMENT_KEYWORDS = {
    # Engineering
    'engineering', 'mechanical', 'electrical', 'civil', 'chemical engineering',
    'biomedical engineering', 'aerospace', 'aeronautics', 'astronautics',
    'industrial engineering', 'materials science', 'nuclear engineering',
    'environmental engineering', 'systems engineering', 'computer engineering',
    'structural engineering', 'transportation engineering', 'ocean engineering',
    'petroleum engineering',
    # Computer Science
    'computer science', 'computing', 'informatics', 'artificial intelligence',
    'data science', 'cybersecurity', 'information science', 'information technology',
    'software engineering',
    # Biological Sciences
    'biology', 'biological', 'biochemistry', 'microbiology', 'molecular biology',
    'genetics', 'genomics', 'neuroscience', 'neurobiology', 'ecology',
    'bioinformatics', 'biostatistics', 'biophysics', 'biotechnology',
    'cell biology', 'developmental biology', 'evolutionary biology',
    'plant biology', 'botany', 'zoology', 'entomology', 'marine biology',
    'immunology', 'pathobiology', 'pharmacology', 'toxicology', 'physiology',
    'anatomy', 'crop science', 'soil science', 'agronomy', 'horticulture',
    'animal science', 'food science', 'nutrition science',
    'environmental science', 'life sciences',
    # Mathematics / Statistics
    'mathematics', 'applied mathematics', 'statistics', 'biostatistics',
    'mathematical', 'actuarial',
    # Physical Sciences
    'physics', 'chemistry', 'astronomy', 'astrophysics', 'geoscience',
    'geophysics', 'geology', 'atmospheric science', 'meteorology',
    'oceanography', 'earth science', 'planetary science', 'materials science',
    'optics', 'photonics',
    # Psychology (research-oriented)
    'psychology', 'cognitive science', 'behavioral science',
    # Other STEM
    'pharmaceutical', 'pharmacy', 'biomedical', 'kinesiology',
    'public health', 'epidemiology',
}

STEM_SUBJECT_KEYWORDS = {
    # Engineering terms
    'algorithm', 'circuit', 'semiconductor', 'transistor', 'antenna',
    'robot', 'robotics', 'control system', 'signal processing',
    'finite element', 'computational fluid', 'turbulence', 'aerodynamic',
    'thermodynamic', 'heat transfer', 'combustion', 'polymer',
    'composite material', 'nanoparticle', 'nanotechnology', 'microfluidic',
    'mems', 'vlsi', 'fpga', 'embedded system', 'wireless', 'radar',
    'photovoltaic', 'solar cell', 'battery', 'fuel cell', 'power system',
    'structural analysis', 'seismic', 'geotechnical',
    # CS terms
    'machine learning', 'deep learning', 'neural network', 'natural language processing',
    'computer vision', 'distributed system', 'database', 'cloud computing',
    'software', 'programming', 'compiler', 'operating system',
    'cryptography', 'blockchain', 'reinforcement learning',
    # Biology terms
    'gene', 'genome', 'protein', 'enzyme', 'dna', 'rna', 'mrna',
    'cell', 'cellular', 'mutation', 'transgenic', 'phylogenetic',
    'metabolic', 'mitochondri', 'ribosom', 'transcription', 'translation',
    'apoptosis', 'signaling pathway', 'receptor', 'ligand',
    'bacteria', 'virus', 'pathogen', 'antibiotic', 'antimicrobial',
    'biofilm', 'fermentation', 'bioreactor',
    'photosynthesis', 'chloroplast', 'ecosystem', 'biodiversity',
    'species', 'phylogen', 'taxonom',
    # Chemistry terms
    'synthesis', 'catalyst', 'catalytic', 'spectroscopy', 'chromatography',
    'electrochemistry', 'organic chemistry', 'inorganic chemistry',
    'analytical chemistry', 'physical chemistry', 'polymer chemistry',
    'reaction mechanism', 'molecular dynamics', 'density functional',
    'crystallography', 'nmr', 'mass spectrometry',
    # Physics terms
    'quantum', 'photon', 'laser', 'plasma', 'superconductor',
    'magnetic', 'magnetism', 'ferromagnetic', 'spin', 'lattice',
    'particle physics', 'higgs', 'neutrino', 'gravitational',
    'cosmolog', 'dark matter', 'black hole', 'galaxy', 'stellar',
    'optic', 'waveguide', 'interferometer',
    # Math terms
    'theorem', 'conjecture', 'stochastic', 'differential equation',
    'topology', 'algebraic', 'combinatorial', 'optimization',
    'numerical method', 'fourier', 'eigenvalue', 'manifold',
    'probability', 'bayesian', 'regression', 'statistical model',
    # Geoscience terms
    'tectonic', 'sediment', 'stratigraph', 'mineral', 'geochemist',
    'paleontolog', 'seismolog', 'volcan', 'hydrology', 'groundwater',
    'climate model', 'atmospheric', 'ocean current',
    # Biomedical / Health
    'clinical trial', 'epidemiolog', 'biomarker', 'diagnostic',
    'therapeutic', 'drug delivery', 'tissue engineering', 'prosthetic',
    'imaging', 'mri', 'ct scan', 'ultrasound',
}

# Non-STEM keywords that indicate false positives
NON_STEM_KEYWORDS = {
    'literature', 'literary', 'poetry', 'novel', 'fiction', 'rhetoric',
    'philosophy', 'theology', 'divinity', 'ministry', 'pastoral',
    'history of art', 'art history', 'fine arts', 'studio art', 'music theory',
    'music composition', 'music performance', 'musicology', 'ethnomusicology',
    'dance', 'theater', 'theatre', 'film studies', 'cinema',
    'political science', 'political theory', 'international relations',
    'sociology', 'anthropology', 'archaeology',
    'linguistics', 'language', 'translation studies',
    'education', 'curriculum', 'pedagogy', 'teaching',
    'law', 'jurisprudence', 'legal studies',
    'business administration', 'management', 'marketing', 'accounting', 'finance',
    'economics',  # debatable, but typically classified as social science
    'social work', 'counseling', 'public administration', 'public policy',
    'communication studies', 'journalism', 'media studies',
    'religious studies', 'biblical',
}


def is_stem(row):
    """Determine if a dissertation record is STEM based on available metadata."""
    # Combine searchable text fields
    subject = (row.get('subject', '') or '').lower()
    contributor = (row.get('contributor', '') or '').lower()
    title = (row.get('title', '') or '').lower()
    description = (row.get('description', '') or '').lower()
    doc_type = (row.get('type', '') or '').lower()

    searchable = f"{subject} {contributor} {title}"
    searchable_full = f"{searchable} {description}"

    # Quick reject: strong non-STEM signals
    for kw in NON_STEM_KEYWORDS:
        if kw in contributor:
            return False

    # Department match (high confidence)
    for kw in STEM_DEPARTMENT_KEYWORDS:
        if kw in contributor:
            return True

    # Subject/title keyword match
    for kw in STEM_DEPARTMENT_KEYWORDS:
        if kw in subject:
            return True

    # Specific STEM subject terms (check subject + title)
    matches = 0
    for kw in STEM_SUBJECT_KEYWORDS:
        if kw in searchable:
            matches += 1
            if matches >= 2:
                return True

    # Single strong STEM keyword in subject with no non-STEM signals
    if matches == 1:
        for kw in NON_STEM_KEYWORDS:
            if kw in searchable:
                return False
        return True

    # Check description for STEM keywords (lower confidence, need more matches)
    desc_matches = 0
    for kw in STEM_SUBJECT_KEYWORDS:
        if kw in description:
            desc_matches += 1
            if desc_matches >= 3:
                return True

    return False


def process_all_datasets(data_dir, stem_only=True):
    """Process all CSV datasets and classify authors."""
    results = {}

    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith('_etds.csv'):
            continue
        repo = fname[:-9]
        filepath = os.path.join(data_dir, fname)

        with open(filepath, encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            continue

        university = rows[0].get('university', repo)
        state = rows[0].get('state', '')

        total_records = len(rows)
        stem_records = 0
        cats = defaultdict(int)
        by_year = defaultdict(lambda: defaultdict(int))
        conf_counts = defaultdict(lambda: defaultdict(int))  # category -> confidence -> count
        
        # Also track PhD-only for repos with clean type field
        phd_cats = defaultdict(int)
        phd_total = 0

        for r in rows:
            if stem_only and not is_stem(r):
                continue

            stem_records += 1
            author = r.get('creator', '').strip()
            if not author:
                continue

            cat, conf = classify(author)
            cats[cat] += 1
            conf_counts[cat][conf] += 1

            # Year tracking
            date = r.get('date', '')
            year = date[:4] if len(date) >= 4 else ''
            if year.isdigit() and 2015 <= int(year) <= 2025:
                by_year[year][cat] += 1
                by_year[year]['total'] += 1

            # PhD tracking
            doc_type = (r.get('type', '') or '').lower()
            if 'dissertation' in doc_type:
                phd_cats[cat] += 1
                phd_total += 1

        results[repo] = {
            'university': university,
            'state': state,
            'total_records': total_records,
            'stem_records': stem_records,
            'categories': dict(cats),
            'by_year': {y: dict(d) for y, d in by_year.items()},
            'confidence': {c: dict(d) for c, d in conf_counts.items()},
            'phd_cats': dict(phd_cats),
            'phd_total': phd_total,
        }

    return results


def print_report(results, stem_only=True):
    """Print comprehensive classification report."""
    filter_label = "STEM-filtered" if stem_only else "all fields"
    print(f"\n{'='*110}")
    print(f"  NAME CLASSIFICATION REPORT — {filter_label.upper()}")
    print(f"  Source: OAI-PMH harvested dissertation metadata across {len(results)} university repositories")
    print(f"{'='*110}")

    # Summary table
    print(f"\n{'Rank':<5} {'University':<45} {'ST':<4} {'STEM':>6} {'Chinese':>8} {'%Chi':>6} {'Indian':>8} {'%Ind':>6} {'Korean':>7} {'Viet':>5}")
    print(f"{'-'*110}")

    all_rows = []
    for repo, data in results.items():
        stem = data['stem_records']
        if stem == 0:
            continue
        ch = data['categories'].get('chinese', 0)
        ind = data['categories'].get('indian', 0)
        kr = data['categories'].get('korean', 0)
        vn = data['categories'].get('vietnamese', 0)
        ch_pct = ch / stem * 100
        ind_pct = ind / stem * 100
        all_rows.append((repo, data['university'], data.get('state', ''), stem, ch, ch_pct, ind, ind_pct, kr, vn))

    all_rows.sort(key=lambda x: -x[4])  # sort by Chinese count

    grand_stem = grand_ch = grand_ind = grand_kr = grand_vn = grand_total = 0
    for i, (repo, uni, st, stem, ch, ch_pct, ind, ind_pct, kr, vn) in enumerate(all_rows, 1):
        print(f"{i:<5} {uni[:45]:<45} {st:<4} {stem:>6,} {ch:>8,} {ch_pct:>5.1f}% {ind:>8,} {ind_pct:>5.1f}% {kr:>7,} {vn:>5,}")
        grand_stem += stem
        grand_ch += ch
        grand_ind += ind
        grand_kr += kr
        grand_vn += vn

    grand_total = sum(d['total_records'] for d in results.values())
    print(f"{'-'*110}")
    print(f"{'':5} {'GRAND TOTAL':<45} {'':4} {grand_stem:>6,} {grand_ch:>8,} {grand_ch/grand_stem*100:>5.1f}% {grand_ind:>8,} {grand_ind/grand_stem*100:>5.1f}% {grand_kr:>7,} {grand_vn:>5,}")
    print(f"\n  Total records: {grand_total:,} | STEM-filtered: {grand_stem:,} ({grand_stem/grand_total*100:.1f}%)")

    # ── Yearly trends (aggregate) ──
    print(f"\n{'='*80}")
    print(f"  YEARLY TRENDS (2015-2025, {filter_label})")
    print(f"{'='*80}")
    agg_years = defaultdict(lambda: defaultdict(int))
    for data in results.values():
        for yr, cats in data['by_year'].items():
            for cat, cnt in cats.items():
                agg_years[yr][cat] += cnt

    print(f"\n  {'Year':<6} {'Total':>7} {'Chinese':>8} {'%Chi':>7} {'Indian':>8} {'%Ind':>7} {'Korean':>7} {'%Kor':>7} {'Viet':>6}")
    print(f"  {'-'*75}")
    for yr in sorted(agg_years.keys()):
        d = agg_years[yr]
        t = d.get('total', 1)
        ch = d.get('chinese', 0)
        ind = d.get('indian', 0)
        kr = d.get('korean', 0)
        vn = d.get('vietnamese', 0)
        print(f"  {yr:<6} {t:>7,} {ch:>8,} {ch/t*100:>6.1f}% {ind:>8,} {ind/t*100:>6.1f}% {kr:>7,} {kr/t*100:>6.1f}% {vn:>6,}")

    # ── Top universities by Chinese % (min 100 STEM records) ──
    print(f"\n{'='*80}")
    print(f"  TOP 20 UNIVERSITIES BY CHINESE % ({filter_label}, min 100 STEM records)")
    print(f"{'='*80}")
    pct_rows = [(r, u, st, stem, ch, ch_pct, ind, ind_pct) for r, u, st, stem, ch, ch_pct, ind, ind_pct, kr, vn in all_rows if stem >= 100]
    pct_rows.sort(key=lambda x: -x[5])
    print(f"\n  {'Rank':<5} {'University':<45} {'STEM':>6} {'Chinese':>8} {'%Chi':>7}")
    print(f"  {'-'*75}")
    for i, (r, u, st, stem, ch, ch_pct, ind, ind_pct) in enumerate(pct_rows[:20], 1):
        print(f"  {i:<5} {u[:45]:<45} {stem:>6,} {ch:>8,} {ch_pct:>6.1f}%")

    # ── Top universities by Indian % (min 100 STEM records) ──
    print(f"\n{'='*80}")
    print(f"  TOP 20 UNIVERSITIES BY INDIAN % ({filter_label}, min 100 STEM records)")
    print(f"{'='*80}")
    pct_rows.sort(key=lambda x: -x[7])
    print(f"\n  {'Rank':<5} {'University':<45} {'STEM':>6} {'Indian':>8} {'%Ind':>7}")
    print(f"  {'-'*75}")
    for i, (r, u, st, stem, ch, ch_pct, ind, ind_pct) in enumerate(pct_rows[:20], 1):
        print(f"  {i:<5} {u[:45]:<45} {stem:>6,} {ind:>8,} {ind_pct:>6.1f}%")

    # ── PhD-only analysis where available ──
    phd_repos = [(repo, data) for repo, data in results.items() if data['phd_total'] >= 50]
    if phd_repos:
        print(f"\n{'='*80}")
        print(f"  PhD DISSERTATIONS ONLY (repos with clean type field, {filter_label})")
        print(f"{'='*80}")
        print(f"\n  {'University':<45} {'PhDs':>6} {'Chinese':>8} {'%Chi':>7} {'Indian':>8} {'%Ind':>7}")
        print(f"  {'-'*85}")
        phd_rows = []
        for repo, data in phd_repos:
            pt = data['phd_total']
            ch = data['phd_cats'].get('chinese', 0)
            ind = data['phd_cats'].get('indian', 0)
            phd_rows.append((data['university'], pt, ch, ch/pt*100, ind, ind/pt*100))
        phd_rows.sort(key=lambda x: -x[3])
        for uni, pt, ch, ch_pct, ind, ind_pct in phd_rows:
            print(f"  {uni[:45]:<45} {pt:>6,} {ch:>8,} {ch_pct:>6.1f}% {ind:>8,} {ind_pct:>6.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Classify dissertation authors by name ethnicity')
    parser.add_argument('--all', action='store_true', help='Include all fields, not just STEM')
    parser.add_argument('--output', '-o', type=str, help='Output file path')
    args = parser.parse_args()

    stem_only = not args.all
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'western_us_dissertations')
    data_dir = os.path.abspath(data_dir)

    print(f"Processing datasets from {data_dir}...")
    results = process_all_datasets(data_dir, stem_only=stem_only)

    if args.output:
        orig_stdout = sys.stdout
        with open(args.output, 'w') as f:
            sys.stdout = f
            print_report(results, stem_only=stem_only)
            sys.stdout = orig_stdout
        print(f"Report written to {args.output}")
        # Also print to stdout
        print_report(results, stem_only=stem_only)
    else:
        print_report(results, stem_only=stem_only)


if __name__ == '__main__':
    main()
