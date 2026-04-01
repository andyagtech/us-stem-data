#!/usr/bin/env python3
"""
Data anomaly detector for PhD Demographics site.

Checks all per-university JSON data for:
1. Duplicate names (same person appearing many times)
2. Suspicious year distributions (all records in one year)
3. Non-thesis content (ATLAS papers, journal articles, etc.)
4. Empty or placeholder records
5. Extreme outliers (departments with improbable record counts)
6. Name patterns that suggest multi-author papers (e.g., semicolons, "Collaboration")

Usage:
    python scripts/data_anomaly_check.py
    python scripts/data_anomaly_check.py --fix  # Show suggested fixes
"""

import json
import os
import sys
from collections import Counter


def check_university(key, data):
    """Check a single university's data for anomalies. Returns list of issues."""
    issues = []
    records = data.get('records', [])
    if not records:
        return issues

    # 1. Duplicate names — same person appearing >5 times
    name_counts = Counter(r[2] for r in records)
    for name, count in name_counts.most_common(10):
        if count > 5 and name:
            # Check if it's the SAME title or different
            titles = set(r[5] for r in records if r[2] == name)
            if len(titles) > 3:  # Many different titles = likely multi-author papers
                issues.append({
                    'severity': 'HIGH',
                    'type': 'multi_author_papers',
                    'detail': f'"{name}" appears {count}x with {len(titles)} different titles — likely collaboration papers, not individual theses',
                    'name': name,
                    'count': count,
                })
            elif count > 10:
                issues.append({
                    'severity': 'MEDIUM',
                    'type': 'duplicate_name',
                    'detail': f'"{name}" appears {count}x — possible duplicate records',
                    'name': name,
                    'count': count,
                })

    # 2. Empty or very short names
    empty_names = sum(1 for r in records if not r[2] or len(r[2]) < 3)
    if empty_names > 5:
        issues.append({
            'severity': 'HIGH',
            'type': 'empty_names',
            'detail': f'{empty_names} records with empty/very short names',
            'count': empty_names,
        })

    # 3. Suspicious year distribution — >80% of records in a single year
    year_counts = Counter(r[1] for r in records)
    total = len(records)
    for year, count in year_counts.most_common(1):
        if count > total * 0.8 and total > 50:
            issues.append({
                'severity': 'MEDIUM',
                'type': 'year_concentration',
                'detail': f'{count}/{total} records ({count/total*100:.0f}%) are from {year} — possible bulk import or data error',
                'year': year,
                'count': count,
            })

    # 4. Department with extreme record counts (>200 in a single year)
    dept_year_counts = Counter((r[0], r[1]) for r in records)
    for (dept, year), count in dept_year_counts.most_common(5):
        if count > 200:
            issues.append({
                'severity': 'HIGH',
                'type': 'extreme_dept_year',
                'detail': f'{dept} in {year} has {count} records — improbably high, likely includes non-thesis content',
                'dept': dept,
                'year': year,
                'count': count,
            })

    # 5. Collaboration/multi-author indicators in names
    collab_count = sum(1 for r in records if any(x in r[2] for x in ['Collaboration', 'ATLAS', 'CMS', 'BESIII', 'LHCb', ';']))
    if collab_count > 5:
        issues.append({
            'severity': 'HIGH',
            'type': 'collaboration_papers',
            'detail': f'{collab_count} records have collaboration names (ATLAS, CMS, etc.) — these are multi-author papers, not theses',
            'count': collab_count,
        })

    # 6. Titles suggesting non-thesis content
    non_thesis_titles = sum(1 for r in records if any(x in r[5].lower() for x in [
        'search for', 'measurement of', 'observation of',  # Physics paper patterns
        'proceedings of', 'journal of', 'conference on',
    ]) and len(r[5]) < 90)  # Short truncated titles from papers
    if non_thesis_titles > 20:
        issues.append({
            'severity': 'MEDIUM',
            'type': 'paper_titles',
            'detail': f'{non_thesis_titles} records have titles suggesting journal papers rather than theses',
            'count': non_thesis_titles,
        })

    # 7. "General" department with >90% of records
    general_count = sum(1 for r in records if r[0] == 'General')
    if general_count > total * 0.9 and total > 100:
        issues.append({
            'severity': 'LOW',
            'type': 'mostly_general',
            'detail': f'{general_count}/{total} records ({general_count/total*100:.0f}%) in "General" — poor department classification',
            'count': general_count,
        })

    # 8. No records in recent years (2023-2024) when we expect them
    recent = sum(1 for r in records if r[1] in (2023, 2024))
    if recent == 0 and total > 100:
        years = sorted(set(r[1] for r in records))
        issues.append({
            'severity': 'LOW',
            'type': 'no_recent_data',
            'detail': f'No records in 2023-2024 (data covers {min(years)}-{max(years)}) — may need re-harvest',
        })

    return issues


def main():
    show_fix = '--fix' in sys.argv

    stem_dir = 'site/data/stem'
    all_issues = {}
    total_high = total_medium = total_low = 0

    for fn in sorted(os.listdir(stem_dir)):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        key = fn.replace('.json', '')
        data = json.load(open(os.path.join(stem_dir, fn)))
        issues = check_university(key, data)

        if issues:
            all_issues[key] = issues
            for issue in issues:
                if issue['severity'] == 'HIGH':
                    total_high += 1
                elif issue['severity'] == 'MEDIUM':
                    total_medium += 1
                else:
                    total_low += 1

    # Print report
    print("=" * 80)
    print("DATA ANOMALY REPORT")
    print("=" * 80)
    print(f"\nUniversities checked: {len(os.listdir(stem_dir)) - 2}")
    print(f"Universities with issues: {len(all_issues)}")
    print(f"HIGH severity: {total_high}")
    print(f"MEDIUM severity: {total_medium}")
    print(f"LOW severity: {total_low}")
    print()

    # HIGH severity first
    for severity in ['HIGH', 'MEDIUM', 'LOW']:
        printed_header = False
        for key, issues in sorted(all_issues.items()):
            sev_issues = [i for i in issues if i['severity'] == severity]
            if sev_issues:
                if not printed_header:
                    print(f"\n{'='*40}")
                    print(f"  {severity} SEVERITY ISSUES")
                    print(f"{'='*40}")
                    printed_header = True

                uni_data = json.load(open(os.path.join(stem_dir, f'{key}.json')))
                print(f"\n  {uni_data.get('name', key)} ({len(uni_data.get('records', []))} records):")
                for issue in sev_issues:
                    print(f"    [{issue['type']}] {issue['detail']}")
                    if show_fix:
                        if issue['type'] == 'collaboration_papers':
                            print(f"      FIX: Add 'type_filter': 'thesis' to CONFIGS")
                        elif issue['type'] == 'multi_author_papers':
                            print(f"      FIX: Filter out records where creator contains ';' or 'Collaboration'")
                        elif issue['type'] == 'empty_names':
                            print(f"      FIX: Records with empty creators should be skipped in load_records()")


if __name__ == '__main__':
    main()
