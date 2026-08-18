#!/usr/bin/env python3
"""Build SHEEO state funding JSON files for the 101 universities.

Outputs:
  data/state_funding/sheeo_by_state.json - State-level time series 2010-2024
  data/state_funding/sheeo_by_university.json - Per-university mapping (state-level proxy)
"""
import csv
import json
from pathlib import Path

import openpyxl

ROOT = Path('/Users/andy/usds_china')
SHEEO_DIR = ROOT / 'data' / 'state_funding' / 'sheeo'
OUT_DIR = ROOT / 'data' / 'state_funding'

STATE_ABBR_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
}


def load_unitid_state_map():
    """Map IPEDS UNITID -> state abbr using HD2024 and fall back to earlier years."""
    mapping = {}
    for fname in ['HD2024.csv', 'HD2023.csv', 'hd2022.csv', 'hd2021.csv', 'hd2020.csv']:
        fp = ROOT / 'data' / 'ipeds' / fname
        if not fp.exists():
            continue
        with open(fp, encoding='latin-1') as f:
            r = csv.reader(f)
            hdr = next(r)
            uid_idx = 0
            st_idx = hdr.index('STABBR') if 'STABBR' in hdr else 5
            for row in r:
                try:
                    uid = int(row[uid_idx])
                    if uid not in mapping:
                        mapping[uid] = row[st_idx].strip()
                except (ValueError, IndexError):
                    pass
    return mapping


def load_shef_state_data():
    """Load SHEF report data keyed by (state_name, fy) -> dict of metrics."""
    wb = openpyxl.load_workbook(SHEEO_DIR / 'SHEEO_SHEF_FY24_Report_Data.xlsx', data_only=True)
    ws = wb['Report Data']
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]

    # Metrics we care about (all in nominal current dollars unless noted)
    keep_cols = {
        'Total State Support': 'total_state_support',
        'Total State and Local Support': 'total_state_local_support',
        'Total Federal Stimulus': 'federal_stimulus',
        'Total State and Local Support Excluding Federal Stimulus': 'state_local_ex_stimulus',
        'Education Appropriations': 'education_appropriations',
        'Education Appropriations Excluding Federal Stimulus': 'ed_approp_ex_stimulus',
        'Net Tuition and Fee Revenue': 'net_tuition_revenue',
        'Student Share': 'student_share',
        'Total Education Revenue': 'total_education_revenue',
        'Net FTE Enrollment': 'net_fte_enrollment',
        'State Tax Appropriations': 'state_tax_appropriations',
        'Research Appropriations': 'research_appropriations',
        'Medical School Appropriations': 'medical_school_appropriations',
        'HECA (Inflation) Adjustment': 'heca_inflation_adj',
    }
    col_idx = {}
    for i, h in enumerate(headers):
        if h in keep_cols:
            col_idx[keep_cols[h]] = i

    out = {}  # state_name -> {year: {metric: value}}
    for row in rows[1:]:
        state = row[0]
        fy = row[1]
        if not isinstance(fy, int) or fy < 2010 or fy > 2024:
            continue
        rec = {}
        for key, i in col_idx.items():
            v = row[i]
            if isinstance(v, (int, float)):
                rec[key] = v
        # Derived: per-FTE education appropriations (nominal)
        fte = rec.get('net_fte_enrollment')
        ed_ap = rec.get('education_appropriations')
        if fte and ed_ap and fte > 0:
            rec['ed_approp_per_fte'] = round(ed_ap / fte, 2)
        # HECA-adjusted real dollars (constant FY24 dollars)
        heca = rec.get('heca_inflation_adj')
        if heca:
            for src, tgt in [
                ('total_state_support', 'total_state_support_real24'),
                ('education_appropriations', 'education_appropriations_real24'),
                ('state_tax_appropriations', 'state_tax_appropriations_real24'),
            ]:
                if rec.get(src) is not None:
                    rec[tgt] = round(rec[src] * heca, 2)
            if rec.get('ed_approp_per_fte') is not None:
                rec['ed_approp_per_fte_real24'] = round(rec['ed_approp_per_fte'] * heca, 2)
        out.setdefault(state, {})[fy] = rec
    return out


MANUAL_STATE_OVERRIDES = {
    'mines': 'CO',   # CO School of Mines
    'cuny': 'NY',    # CUNY Graduate Center
}


def main():
    unitid_state = load_unitid_state_map()
    shef = load_shef_state_data()

    # Load 101 universities
    with open(ROOT / 'pipeline' / 'universities.json') as f:
        unis = json.load(f)

    # State JSON
    sheeo_by_state = {
        '_meta': {
            'source': 'SHEEO State Higher Education Finance (SHEF) FY24 Report Data',
            'source_url': 'https://shef.sheeo.org/data-downloads/',
            'years': '2010-2024',
            'dollar_basis': 'Nominal current dollars; *_real24 fields are HECA-adjusted to FY2024 constant dollars',
            'fields': {
                'total_state_support': 'Total state support for higher ed (nominal $)',
                'total_state_local_support': 'State + local support (nominal $)',
                'federal_stimulus': 'Federal stimulus funds included in state support',
                'state_local_ex_stimulus': 'State + local ex-stimulus (nominal $)',
                'education_appropriations': 'Education appropriations (operating, ex RAM) (nominal $)',
                'ed_approp_ex_stimulus': 'Education appropriations ex-stimulus',
                'ed_approp_per_fte': 'Education appropriations per net FTE (nominal $)',
                'net_tuition_revenue': 'Net tuition & fee revenue (nominal $)',
                'student_share': 'Student share of total education revenue',
                'total_education_revenue': 'Total education revenue (nominal $)',
                'net_fte_enrollment': 'Net FTE enrollment',
                'state_tax_appropriations': 'State tax appropriations (nominal $)',
                'research_appropriations': 'Research appropriations (nominal $)',
                'medical_school_appropriations': 'Medical school appropriations (nominal $)',
                'heca_inflation_adj': 'HECA inflation multiplier to FY2024 dollars',
                'total_state_support_real24': 'Total state support in FY2024 real $',
                'education_appropriations_real24': 'Education approp in FY2024 real $',
                'state_tax_appropriations_real24': 'State tax approp in FY2024 real $',
                'ed_approp_per_fte_real24': 'Education approp per FTE in FY2024 real $',
            },
        },
        'states': shef,
    }
    (OUT_DIR / 'sheeo_by_state.json').write_text(json.dumps(sheeo_by_state, indent=2, default=str))

    # University JSON (state-level proxy since institution data unavailable)
    by_uni = {
        '_meta': {
            'source': 'SHEEO SHEF FY24 Report Data (state-level) joined on IPEDS HD state',
            'note': 'SHEEO does not publish institution-level appropriations publicly; '
                    'each university is attached to its STATE-level time series as a proxy. '
                    'For private universities, state appropriations are not applicable (private_no_state=true).',
            'years': '2010-2024',
        },
        'universities': {},
    }

    unmatched = []
    for key, u in unis.items():
        uid = u.get('unitid')
        abbr = unitid_state.get(uid) if uid else None
        if not abbr:
            abbr = MANUAL_STATE_OVERRIDES.get(key)
        state_name = STATE_ABBR_TO_NAME.get(abbr) if abbr else None
        entry = {
            'name': u.get('name'),
            'unitid': uid,
            'state_abbr': abbr,
            'state_name': state_name,
        }
        if state_name and state_name in shef:
            entry['state_time_series'] = shef[state_name]
        else:
            entry['state_time_series'] = None
            unmatched.append((key, u.get('name'), abbr))
        by_uni['universities'][key] = entry

    (OUT_DIR / 'sheeo_by_university.json').write_text(json.dumps(by_uni, indent=2, default=str))

    matched = sum(1 for e in by_uni['universities'].values() if e['state_time_series'])
    print(f"Universities: {len(unis)}; matched to SHEF state: {matched}; unmatched: {len(unmatched)}")
    for row in unmatched:
        print("  unmatched:", row)
    print(f"State-level rows: {sum(len(v) for v in shef.values())} across {len(shef)} states")


if __name__ == '__main__':
    main()
