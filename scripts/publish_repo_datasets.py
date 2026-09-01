#!/usr/bin/env python3
"""Publish the analysis files that were only ever written into data/.

Several builders write their output beside their inputs rather than into
site/data/, which is where the site serves from. The result is a dozen real
analyses -- OPT by university, the cap-exempt sponsor ranking, PERM by status
held, the nonprofit filings -- that exist, are catalogued and are tested, and
that nobody outside the repository can reach.

Copying is the right fix rather than moving. Those paths are what their own
builders write and what other scripts read, so changing them would break the
pipeline to fix a publishing problem. The copy is regenerated on every run
and the manifest records where each file came from.

INTERNAL FILES ARE DELIBERATELY LEFT OUT: the assistant's bundle, the curated
answers, the social images, the IPEDS index metadata and the university
configuration are plumbing, not findings, and publishing them would only
invite them to be read as analysis.

Usage:
  python3 scripts/publish_repo_datasets.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "data"
OUT = SITE / "repo_datasets.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

# source path -> published name. Only analysis outputs; plumbing is excluded
# and the reason is in the module docstring.
PUBLISH = {
    "data/h1b/opt_national.json": "opt_national.json",
    "data/h1b/opt_employers.json": "opt_employers.json",
    "data/h1b/opt_by_university.json": "opt_by_university.json",
    "data/h1b/eb2_niw.json": "eb2_niw.json",
    "data/h1b/h1b_cap_exempt.json": "h1b_cap_exempt.json",
    "data/h1b/j1_scholars.json": "j1_scholars.json",
    "data/h1b/nonprofit_990s.json": "nonprofit_990s.json",
    "data/h1b/perm_pipeline.json": "perm_pipeline.json",
    "data/h1b/lca_by_university.json": "lca_by_university.json",
    "data/h1b/build_fellowship_partners.json": "build_fellowship_partners.json",
    "data/cap_exempt/directory.json": "cap_exempt_directory.json",
    "data/cap_exempt/proxy_comparison.json": "cap_exempt_proxy_comparison.json",
    "data/cap_exempt/merged_employers.json": "cap_exempt_merged_employers.json",
    "data/cap_exempt/sponsor_ranking.json": "cap_exempt_sponsor_ranking.json",
    "data/federal_support/federal_support_by_university.json":
        "federal_support_by_university.json",
    "data/nsf_workforce/workforce_dashboard.json": "workforce_dashboard.json",
    "data/buildfellowship/projects.json": "buildfellowship_projects.json",
    "data/buildfellowship/project_links.json": "buildfellowship_project_links.json",
}


def main() -> int:
    SITE.mkdir(parents=True, exist_ok=True)
    published, missing = [], []
    for src, name in sorted(PUBLISH.items()):
        p = ROOT / src
        if not p.exists():
            missing.append(src)
            continue
        dest = SITE / name
        shutil.copy2(p, dest)
        published.append({"published_as": f"/data/{name}",
                          "built_at": src,
                          "kb": round(dest.stat().st_size / 1024, 1)})

    doc = {
        "_comment": (
            "Analysis files whose builders write them beside their inputs "
            "rather than into site/data/. They are COPIES, regenerated on "
            "every run: the path under data/ remains what the builder writes "
            "and what other scripts read, because changing that to fix a "
            "publishing problem would break the pipeline. Each published file "
            "carries its own _comment with the limits on how it may be read. "
            "The assistant's bundle, curated answers, social images, IPEDS "
            "index metadata and university configuration are deliberately NOT "
            "here -- they are plumbing, and publishing them would invite them "
            "to be read as findings."),
        "count": len(published),
        "total_kb": round(sum(x["kb"] for x in published), 1),
        "files": published,
        "missing_sources": missing,
    }
    write_json(OUT, doc)

    print(f"  published {len(published)} files, "
          f"{doc['total_kb'] / 1024:.1f} MB into site/data/")
    for x in sorted(published, key=lambda r: -r["kb"])[:6]:
        print(f"   {x['published_as']:44}{x['kb']:>9.0f} KB")
    for m in missing:
        print(f"  MISSING {m}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
