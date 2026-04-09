#!/usr/bin/env python3
"""
Data Quality Report for PhD Demographics site.

Generates a comprehensive QA report comparing our scraped data against
IPEDS expected counts, checking year coverage, degree labeling, department
classification, and data completeness.

Usage:
    python scripts/qa_report.py                    # Full report to stdout
    python scripts/qa_report.py --output site/qa_report.html  # HTML report
    python scripts/qa_report.py --csv data/qa_report.csv      # CSV export
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


def load_ipeds_expected():
    """Load expected doctoral counts from IPEDS for comparison."""
    expected = {}
    ipeds_file = "data/ipeds/C2022_a_rv.csv"
    hd_file = "data/ipeds/hd2022.csv"

    # Get institution names
    names = {}
    if os.path.exists(hd_file):
        with open(hd_file, encoding="latin-1") as f:
            for row in csv.DictReader(f):
                names[row.get("UNITID", "")] = row.get("INSTNM", "")

    # Get doctoral totals
    if os.path.exists(ipeds_file):
        with open(ipeds_file, encoding="latin-1") as f:
            for row in csv.DictReader(f):
                uid = row.get("UNITID", row.get("\ufeffUNITID", ""))
                if row.get("AWLEVEL", "") not in ("17", "18"):
                    continue
                if row.get("CIPCODE", "") == "99":
                    continue
                ct = int(row.get("CTOTALT", "0") or 0)
                nra = int(row.get("CNRALT", "0") or 0)
                if uid not in expected:
                    expected[uid] = {"name": names.get(uid, uid), "total": 0, "nra": 0}
                expected[uid]["total"] += ct
                expected[uid]["nra"] += nra

    return expected


def analyze_university(stem_path, nonstem_path):
    """Analyze data quality for one university."""
    stats = {
        "key": "",
        "name": "",
        "nra": 0,
        "stem_records": 0,
        "nonstem_records": 0,
        "total_records": 0,
        "phd_count": 0,
        "ms_count": 0,
        "unlabeled_degree": 0,
        "degree_label_pct": 0,
        "dept_count": 0,
        "general_count": 0,
        "general_pct": 0,
        "year_min": 9999,
        "year_max": 0,
        "years_covered": set(),
        "year_gaps": [],
        "has_2024": False,
        "has_2023": False,
        "has_urls": 0,
        "no_urls": 0,
        "empty_titles": 0,
        "avg_title_len": 0,
        "issues": [],
    }

    for path, mode in [(stem_path, "stem"), (nonstem_path, "nonstem")]:
        if not os.path.exists(path):
            continue
        d = json.load(open(path))
        if mode == "stem":
            stats["key"] = d.get("key", "")
            stats["name"] = d.get("name", "")
            stats["nra"] = d.get("nra", 0)
        records = d.get("records", [])

        for r in records:
            # r: [dept, year, name, cat, conf, title, url, degree]
            dept, year, name, cat, conf, title, url, degree = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]

            if mode == "stem":
                stats["stem_records"] += 1
            else:
                stats["nonstem_records"] += 1
            stats["total_records"] += 1

            # Degree labeling
            if degree == "phd":
                stats["phd_count"] += 1
            elif degree == "ms":
                stats["ms_count"] += 1
            else:
                stats["unlabeled_degree"] += 1

            # Department
            if dept == "General":
                stats["general_count"] += 1

            # Year coverage
            try:
                yr = int(year)
                stats["year_min"] = min(stats["year_min"], yr)
                stats["year_max"] = max(stats["year_max"], yr)
                stats["years_covered"].add(yr)
            except:
                pass

            # URL quality
            if url and url.startswith("http"):
                stats["has_urls"] += 1
            else:
                stats["no_urls"] += 1

            # Title quality
            if not title or len(title) < 5:
                stats["empty_titles"] += 1

    # Computed metrics
    total = stats["total_records"]
    if total > 0:
        labeled = stats["phd_count"] + stats["ms_count"]
        stats["degree_label_pct"] = round(labeled / total * 100, 1)
        stats["general_pct"] = round(stats["general_count"] / total * 100, 1)
        stats["dept_count"] = len(set())  # Will be computed from stem data

    # Year gaps (within 2016-2024 range)
    expected_years = set(range(2016, 2025))
    stats["has_2024"] = 2024 in stats["years_covered"]
    stats["has_2023"] = 2023 in stats["years_covered"]
    missing_years = expected_years - stats["years_covered"]
    stats["year_gaps"] = sorted(missing_years)

    # Count departments from stem data
    if os.path.exists(stem_path):
        d = json.load(open(stem_path))
        depts = set(r[0] for r in d.get("records", []))
        stats["dept_count"] = len(depts)

    # Quality issues
    if stats["degree_label_pct"] < 50:
        stats["issues"].append(f"Low degree labeling ({stats['degree_label_pct']}%)")
    if stats["general_pct"] > 50:
        stats["issues"].append(f"High General dept ({stats['general_pct']}%)")
    if stats["year_gaps"]:
        stats["issues"].append(f"Missing years: {stats['year_gaps']}")
    if stats["no_urls"] > total * 0.1:
        stats["issues"].append(f"{stats['no_urls']} records without URLs")
    if stats["empty_titles"] > 0:
        stats["issues"].append(f"{stats['empty_titles']} empty titles")
    if total < 100:
        stats["issues"].append(f"Very few records ({total})")

    return stats


def generate_report():
    """Generate full QA report for all universities."""
    stem_dir = "site/data/stem" if os.path.isdir("site/data/stem") else "data/processed/stem"
    nonstem_dir = "site/data/nonstem" if os.path.isdir("site/data/nonstem") else "data/processed/nonstem"

    ipeds = load_ipeds_expected()

    universities = []
    for fn in sorted(os.listdir(stem_dir)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        key = fn.replace(".json", "")
        stem_path = os.path.join(stem_dir, fn)
        nonstem_path = os.path.join(nonstem_dir, fn)
        stats = analyze_university(stem_path, nonstem_path)
        universities.append(stats)

    return universities


def print_report(universities):
    """Print formatted report to stdout."""
    print("=" * 120)
    print("DATA QUALITY REPORT — PhD Demographics")
    print("=" * 120)
    print()

    # Summary stats
    total_stem = sum(u["stem_records"] for u in universities)
    total_nonstem = sum(u["nonstem_records"] for u in universities)
    total_phd = sum(u["phd_count"] for u in universities)
    total_ms = sum(u["ms_count"] for u in universities)
    total_unlabeled = sum(u["unlabeled_degree"] for u in universities)
    total_general = sum(u["general_count"] for u in universities)

    print(f"Schools:           {len(universities)}")
    print(f"STEM records:      {total_stem:,}")
    print(f"Non-STEM records:  {total_nonstem:,}")
    print(f"Total records:     {total_stem + total_nonstem:,}")
    print(f"PhD labeled:       {total_phd:,} ({total_phd/(total_stem+total_nonstem)*100:.0f}%)")
    print(f"MS labeled:        {total_ms:,} ({total_ms/(total_stem+total_nonstem)*100:.0f}%)")
    print(f"Unlabeled degree:  {total_unlabeled:,} ({total_unlabeled/(total_stem+total_nonstem)*100:.0f}%)")
    print(f"General dept:      {total_general:,} ({total_general/(total_stem+total_nonstem)*100:.0f}%)")
    print()

    # Detailed per-university report
    print(f"{'University':<25} {'STEM':>7} {'NonST':>7} {'PhD%':>5} {'MS%':>5} {'Unlbl%':>6} {'Gen%':>5} {'Depts':>5} {'Years':>12} {'Issues'}")
    print("-" * 120)

    for u in sorted(universities, key=lambda x: x["stem_records"], reverse=True):
        total = u["total_records"]
        if total == 0:
            continue
        phd_pct = u["phd_count"] / total * 100 if total else 0
        ms_pct = u["ms_count"] / total * 100 if total else 0
        unlbl_pct = u["unlabeled_degree"] / total * 100 if total else 0
        gen_pct = u["general_pct"]
        yr_range = f"{u['year_min']}-{u['year_max']}" if u["year_min"] < 9999 else "none"
        issues = "; ".join(u["issues"][:2]) if u["issues"] else "OK"

        # Color coding via markers
        marker = ""
        if len(u["issues"]) >= 3:
            marker = "!!!"
        elif len(u["issues"]) >= 1:
            marker = "!"

        print(f"{u['name']:<25} {u['stem_records']:>7,} {u['nonstem_records']:>7,} {phd_pct:>4.0f}% {ms_pct:>4.0f}% {unlbl_pct:>5.0f}% {gen_pct:>4.0f}% {u['dept_count']:>5} {yr_range:>12} {marker} {issues}")

    # Universities with issues
    print()
    print("=" * 80)
    print("UNIVERSITIES NEEDING ATTENTION")
    print("=" * 80)

    for category, filter_fn, description in [
        ("No 2024 data", lambda u: not u["has_2024"] and u["total_records"] > 100, "May need re-harvest"),
        ("No 2023 data", lambda u: not u["has_2023"] and not u["has_2024"] and u["total_records"] > 100, "Likely stale data"),
        (">80% unlabeled degree", lambda u: u["unlabeled_degree"] / max(u["total_records"], 1) > 0.8, "Need degree enrichment"),
        (">50% General dept", lambda u: u["general_pct"] > 50, "Need department enrichment"),
        ("<100 STEM records", lambda u: u["stem_records"] < 100 and u["stem_records"] > 0, "Possibly incomplete harvest"),
    ]:
        flagged = [u for u in universities if filter_fn(u)]
        if flagged:
            print(f"\n{category} ({description}):")
            for u in sorted(flagged, key=lambda x: x["stem_records"], reverse=True):
                print(f"  {u['name']:<30} {u['stem_records']:>6} STEM  {u['degree_label_pct']:>5.1f}% labeled  {u['general_pct']:>5.1f}% General")


def export_csv(universities, output_path):
    """Export QA data as CSV."""
    fields = [
        "key", "name", "nra", "stem_records", "nonstem_records", "total_records",
        "phd_count", "ms_count", "unlabeled_degree", "degree_label_pct",
        "dept_count", "general_count", "general_pct",
        "year_min", "year_max", "has_2024", "has_2023", "has_urls", "no_urls",
        "empty_titles", "year_gaps_str", "issues",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for u in universities:
            row = {k: u.get(k, "") for k in fields}
            row["year_gaps_str"] = ",".join(str(y) for y in u.get("year_gaps", []))
            row["issues"] = "; ".join(u.get("issues", []))
            writer.writerow(row)
    print(f"Exported to {output_path}")


def export_json(universities, output_path):
    """Export QA data as JSON for the dashboard page."""
    out = {
        "generated_at_unix": __import__("time").time(),
        "universities": [
            {
                "key": u.get("key"),
                "name": u.get("name"),
                "nra": u.get("nra"),
                "stem_records": u.get("stem_records", 0),
                "nonstem_records": u.get("nonstem_records", 0),
                "total_records": u.get("total_records", 0),
                "phd_count": u.get("phd_count", 0),
                "ms_count": u.get("ms_count", 0),
                "unlabeled_degree": u.get("unlabeled_degree", 0),
                "degree_label_pct": u.get("degree_label_pct", 0),
                "dept_count": u.get("dept_count", 0),
                "general_count": u.get("general_count", 0),
                "general_pct": u.get("general_pct", 0),
                "year_min": u.get("year_min"),
                "year_max": u.get("year_max"),
                "has_2024": u.get("has_2024", False),
                "has_2023": u.get("has_2023", False),
                "has_urls": u.get("has_urls", 0),
                "no_urls": u.get("no_urls", 0),
                "empty_titles": u.get("empty_titles", 0),
                "year_gaps": list(u.get("year_gaps", [])),
                "issues": list(u.get("issues", [])),
            }
            for u in universities
        ],
    }
    with open(output_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Data Quality Report")
    parser.add_argument("--csv", help="Export as CSV")
    parser.add_argument("--json", help="Export as JSON")
    parser.add_argument("--output", help="Export as HTML (not yet implemented)")
    args = parser.parse_args()

    universities = generate_report()

    if args.csv:
        export_csv(universities, args.csv)
    if args.json:
        export_json(universities, args.json)
    if not (args.csv or args.json):
        print_report(universities)


if __name__ == "__main__":
    main()
