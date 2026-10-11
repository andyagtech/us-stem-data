#!/usr/bin/env python3
"""Archive each declared lab's roster and attach its PI's NSF awards.

The roster gives composition; the award record gives the public money.
The second is the fact the page rests on, because it is exact and
carries an identifier. The first is context and is reported with its
denominator every time.

Run:
  python3 scripts/harvest_research_labs.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
import harvest_lab_rosters as hl                               # noqa: E402
from research_labs import LABS                                 # noqa: E402

OUT = ROOT / "data" / "labs" / "research_labs.json"
SNAP = ROOT / "data" / "labs" / "snapshots"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


def nsf_awards(pi: str) -> dict:
    """Awards naming this PI, with the signal that it is not one person."""
    q = urllib.parse.quote(f'"{pi}"')
    url = (f"https://api.nsf.gov/services/v1/awards.json?pdPIName={q}"
           f"&printFields=id,title,awardeeName,fundsObligatedAmt,startDate")
    try:
        r = requests.get(url, headers=UA, timeout=40)
        aw = (r.json().get("response") or {}).get("award") or [] \
            if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        aw = []
    total, insts, years = 0, set(), []
    for a in aw:
        try:
            total += int(a.get("fundsObligatedAmt") or 0)
        except (TypeError, ValueError):
            pass
        if a.get("awardeeName"):
            insts.add(a["awardeeName"])
        if a.get("startDate"):
            years.append(a["startDate"][-4:])
    return {
        "awards": len(aw), "obligated": total,
        "awardee_institutions": sorted(insts),
        #: More than three awardees means the name is shared and the
        #: total belongs to several people. Same test as the mobility
        #: pipeline, same reason.
        "likely_name_collision": len(insts) > 3,
        "first": min(years) if years else None,
        "last": max(years) if years else None,
        "titles": [a.get("title", "")[:70] for a in aw[:6]],
    }


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for lab in LABS:
        print(f"\n{lab.pi} - {lab.name[:48]}")
        try:
            r = requests.get(lab.roster_url, headers=UA, timeout=30)
            html, code = r.text, r.status_code
        except requests.RequestException as e:
            print(f"  roster unreachable: {type(e).__name__}")
            html, code = "", 0

        names = hl.best_names(html) if code == 200 else []
        comp = hl.composition(names) if names else {}
        snap = ""
        if html:
            import hashlib
            from datetime import datetime, timezone
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            h = hashlib.sha256(lab.roster_url.encode()).hexdigest()[:12]
            f = SNAP / f"lab_{h}_{stamp}.html"
            write_text(f, html)
            snap = str(f.relative_to(ROOT))

        nsf = nsf_awards(lab.pi)
        n = comp.get("members_detected") or 0
        print(f"  roster  {code}  {n} names listed")
        if n:
            print(f"          {comp.get('markers_chinese')} of {n} carry a "
                  f"Chinese name marker ({comp.get('share_chinese_markers')}%)")
        print(f"  NSF     {nsf['awards']} awards, ${nsf['obligated']:,}"
              f"{'  <- SHARED NAME' if nsf['likely_name_collision'] else ''}")

        rows.append({
            "name": lab.name, "pi": lab.pi, "institution": lab.institution,
            "department": lab.department, "field": lab.field,
            "roster_url": lab.roster_url, "home_url": lab.home_url,
            "note": lab.note,
            "http_status": code,
            "members_listed": n,
            #: TOTALS ONLY. No per-person label is written here.
            "composition": comp,
            "snapshot": snap,
            "nsf": nsf,
        })
        time.sleep(1.5)

    write_text(OUT, json.dumps({
        "what_this_is": (
            "Research groups with a public member list, archived, with the "
            "principal investigator's federal award record. The awards are "
            "exact and carry identifiers. The composition is a count of "
            "names carrying a marker, which is an INFERENCE from names and "
            "not a statement of anyone's citizenship, and it is reported "
            "with its denominator because a share of twelve is twelve."),
        "ordinary_explanations": (
            "A principal investigator recruits from who applies, from "
            "collaborators abroad, from a shared language, from a technique "
            "taught in a few places. None of that shows in a roster and all "
            "of it is common. This records what a laboratory publishes "
            "about itself."),
        "count": len(rows), "labs": rows}, indent=2))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
