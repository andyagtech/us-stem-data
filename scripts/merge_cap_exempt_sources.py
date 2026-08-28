#!/usr/bin/env python3
"""Fold the smaller cap-exempt sources into the main directory.

Four public cap-exempt sources were examined. Two could be collected and two
could not, and the reasons matter:

  ellis.com              robots.txt Allow: /   2,388 employers   COLLECTED
  h1bcapexemptjobs.com   robots.txt Allow: /   21 companies      COLLECTED
  avisajob.com           robots.txt Allow: /   29 names          COLLECTED
  myvisajobs.com         robots.txt names ClaudeBot in a Disallow: / rule
  h1bgrader.com          403 from its edge protection, to a real browser too

The two job boards are not employer registries -- they list current openings
-- so their pages mix institutions with job titles and section headings. Rows
are kept only if they look like an organisation and carry an institutional
word, and the noise that survives is reported rather than silently merged.

Their value is marginal and worth stating plainly: after filtering they add
around a dozen names the 2,388-entry directory does not have, mostly national
laboratories and hospital systems.

Usage:
  python3 scripts/merge_cap_exempt_sources.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import join_fellowship_employers as J  # noqa: E402

DIR = ROOT / "data" / "cap_exempt" / "directory.json"
BOARDS = ROOT / "data" / "cap_exempt" / "jobboard_raw.json"
OUT = ROOT / "data" / "cap_exempt" / "merged_employers.json"

INSTITUTION = re.compile(
    r"\b(universit|college|institute|hospital|medical|health|foundation|"
    r"laborator|clinic|cancer center|school of)\b", re.I)
# Section headings and job postings that pass a naive name test.
NOISE = re.compile(
    r"\b(nurse|physician|nocturnist|engineer|analyst|manager|director|"
    r"orgs|tied to|community colleges|universities &|biomedical, life|"
    r"& colleges|full[- ]time|part[- ]time|nights|shift)\b", re.I)


def main() -> int:
    if not (DIR.exists() and BOARDS.exists()):
        print("  missing directory.json or jobboard_raw.json")
        return 1
    directory = json.loads(DIR.read_text())["employers"]
    known = {J.norm(e["name"]) for e in directory}

    added, rejected = [], []
    for source, names in json.loads(BOARDS.read_text()).items():
        for name in names:
            n = re.sub(r"\s+", " ", name).strip()
            if len(n.split()) < 2 or NOISE.search(n) or not INSTITUTION.search(n):
                rejected.append({"source": source, "name": n})
                continue
            k = J.norm(n)
            if not k or k in known:
                continue
            known.add(k)
            added.append({"name": n, "source": source})

    merged = ([{"name": e["name"], "source": "ellis.com",
                "city": e.get("city"), "state": e.get("state")}
               for e in directory] +
              [{"name": a["name"], "source": a["source"]} for a in added])

    OUT.write_text(json.dumps({
        "_comment": ("Cap-exempt employer candidates from every public source "
                     "that could be collected. NOT AUTHORITATIVE: USCIS does "
                     "not publish cap status, so each entry is somebody's "
                     "inference from employer type. Use it to choose which "
                     "employers to look up in USCIS data. Two sources are "
                     "absent -- myvisajobs.com names ClaudeBot in a Disallow "
                     "rule, and h1bgrader.com returns 403 from its edge "
                     "protection even to a real browser."),
        "sources": {
            "ellis.com": {"employers": len(directory), "collected": True},
            "job_boards": {"added": len(added), "rejected_as_noise": len(rejected),
                           "collected": True},
            "myvisajobs.com": {"collected": False,
                               "reason": "robots.txt names ClaudeBot in a Disallow: / rule"},
            "h1bgrader.com": {"collected": False,
                              "reason": "403 from edge protection, browser included"},
        },
        "total": len(merged),
        "added_by_job_boards": added,
        "rejected_examples": rejected[:12],
        "employers": merged,
    }, indent=1) + "\n")

    print(f"  directory: {len(directory):,}")
    print(f"  job boards added: {len(added)}  (rejected as noise: {len(rejected)})")
    for a in added:
        print(f"     + {a['name'][:52]:54} [{a['source']}]")
    print(f"  merged total: {len(merged):,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
