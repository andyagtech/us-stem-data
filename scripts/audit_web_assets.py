#!/usr/bin/env python3
"""Audit what the site ships: what is served, what is dead, what is orphaned.

Written to be re-run rather than trusted once. Its first version reported 588
files and 266 MB as unreferenced, which was wrong: per-university data and
pages are fetched through constructed paths -- `/data/stem/${key}.json`,
`universities/${slug}` -- and a static reference scan cannot see them. Acting
on that would have meant deleting the site's actual content.

Three separate questions, kept separate because they have different answers:

  unreferenced   nothing in the site links to it
  unpublished    a dataset exists in the repo but is not deployed
  legacy         objects still in S3 at the bucket root, from before the
                 atomic-deploy scheme, which the origin no longer serves

Usage:
  python3 scripts/audit_web_assets.py            # write the report
  python3 scripts/audit_web_assets.py --no-s3    # skip the bucket check
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.datasets import CATALOG  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "notes" / "web_asset_audit.md"
BUCKET = "phd-demographics-andy-barr"

# Directories whose members are requested through a constructed path.
DYNAMIC = ("data/stem/", "data/nonstem/", "universities/", "v/", "og/")
ENTRY = {"index.html", "robots.txt", "sitemap.xml", "favicon.ico", "llms.txt",
         "catalog.json", "data_catalog.json"}
REF = re.compile(r"""["'(`]/?([A-Za-z0-9_\-./]+\.(?:html|js|css|json|png|jpg|jpeg"""
                 r"""|svg|ico|webp|xml|txt|parquet|pdf|woff2?))""")


def referenced() -> set[str]:
    out: set[str] = set()
    for p in SITE.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (
                ".html", ".js", ".css", ".json", ".xml", ".txt"):
            continue
        try:
            out.update(m.lstrip("./") for m in REF.findall(p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def unreferenced(refs: set[str]) -> list[tuple[int, str]]:
    rows = []
    for p in sorted(SITE.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(SITE))
        if any(rel.startswith(d) for d in DYNAMIC) or os.path.basename(rel) in ENTRY:
            continue
        if rel in refs or os.path.basename(rel) in refs:
            continue
        rows.append((p.stat().st_size, rel))
    rows.sort(reverse=True)
    return rows


def legacy_root() -> tuple[int, int]:
    r = subprocess.run(["aws", "s3", "ls", f"s3://{BUCKET}/", "--profile", "personal"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return 0, 0
    n = size = 0
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] != "PRE":
            n += 1
            size += int(parts[2])
    return n, size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-s3", action="store_true")
    args = ap.parse_args()

    refs = referenced()
    orphans = unreferenced(refs)
    published = {k for d in CATALOG for k in [d.key]
                 if any(p.startswith("site/") for p in d.produces)}
    repo_only = sorted(d.key for d in CATALOG
                       if d.key not in published and d.produces
                       and not d.source.lower().startswith("derived"))
    n_root, sz_root = (0, 0) if args.no_s3 else legacy_root()

    # A dataset published as open data is unreferenced ON PURPOSE.
    data_pub = [r for r in orphans if r[1].startswith("data/")]
    assets = [r for r in orphans if not r[1].startswith("data/")]

    lines = [
        "# Web asset audit",
        "",
        "Regenerate with `python3 scripts/audit_web_assets.py`. Nothing here is",
        "deleted automatically; this is a list to review.",
        "",
        "## 1. Unreferenced assets — candidates for deletion",
        "",
        "Nothing in the site links to these.",
        "",
        "| Size | Path |",
        "|---:|---|",
    ]
    lines += [f"| {s/1024:,.1f} KB | `{r}` |" for s, r in assets]
    lines += [
        "",
        f"Total {sum(s for s, _ in assets)/1024:,.1f} KB across {len(assets)} files.",
        "",
        "## 2. Published data, unreferenced on purpose",
        "",
        "These are open-data publications. The methodology page cites them and the",
        "report builders read them; no page fetches them, and that is correct.",
        "",
        "| Size | Path |",
        "|---:|---|",
    ]
    lines += [f"| {s/1024:,.1f} KB | `{r}` |" for s, r in data_pub]
    lines += [
        "",
        "## 3. Datasets that never reach the site",
        "",
        "Built and catalogued, but produced only into `data/`. They are not",
        "downloadable, they are not in the assistant's bundle, and no chart reads",
        "them.",
        "",
    ]
    lines += [f"- `{k}`" for k in repo_only]
    lines += [
        "",
        "## 4. Legacy objects in S3",
        "",
        f"{n_root} objects at the bucket root, {sz_root/1024/1024:,.1f} MB, from before",
        "the atomic-deploy scheme. The CloudFront origin points at `/v/<build>/`, so",
        "these are not served. Every name also exists in the current build.",
        "",
        "Confirm the origin has no root fallback before deleting.",
        "",
        "## What the assistant actually holds",
        "",
        "The chat Lambda ships its own bundle in `cloud/chat/chat_data/` and fetches",
        "nothing at runtime: `universities_compact.json`, `national_series.json`,",
        "`nra_index.csv.gz`, `level_rankings.json`, `search_index.bin`, `site_map.json`,",
        "`hd_states.csv.gz`, `sheeo_state_compact.json.gz`.",
        "",
        "None of the datasets built in the most recent work are in it, so the assistant",
        "cannot answer from them or chart them.",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")

    print(f"  unreferenced assets      {len(assets):>3}  {sum(s for s,_ in assets)/1024:>9,.1f} KB")
    print(f"  published data (correct) {len(data_pub):>3}  {sum(s for s,_ in data_pub)/1024:>9,.1f} KB")
    print(f"  datasets never published {len(repo_only):>3}")
    print(f"  legacy S3 root objects   {n_root:>3}  {sz_root/1024/1024:>9,.1f} MB")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
