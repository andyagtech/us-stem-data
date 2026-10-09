#!/usr/bin/env python3
"""Who holds the postdoctoral appointments American research money pays for?

THE POPULATION NAMED. On 2026-10-08 the administration opened an investigation
into J-1 use at nine universities and said that about 61% of postdoctoral
researchers and federally funded workers at those institutions are foreign
nationals, against a national average of 38%. Postdocs are a distinct
population from graduate students, and the project already measures graduate
students -- scripts/build_gss_institution_ranking.py. This measures postdocs,
because that is the population under subpoena and nothing here covered it.

WHAT THE SOURCE SAYS. The NSF/NCSES Survey of Graduate Students and
Postdoctorates asks every doctorate-granting institution for a headcount of
its postdoctoral appointees each autumn, split by citizenship and by the
mechanism and source of their support. It is a census of institutions, not a
sample of people, and the postdoc fields carry the pd_ prefix.

'FOREIGN' MEANS A TEMPORARY VISA. The GSS splits postdocs into pd_tot_us_v --
US citizens and permanent residents -- and pd_tot_forgn_v, temporary visa
holders. The two sum to the total exactly, which this builder asserts rather
than assumes. So a foreign postdoc here is someone on a visa, and a green-card
holder counts as American. That is the stricter reading and it is the one that
matches how the J-1 and H-1B programmes are argued about.

TWO MEANINGS OF 'forgn' IN ONE FILE, as the sibling builder also warns. Beside
pd_tot_us_v it is citizenship. Beside pd_tot_nfed_inst_v it is a foreign
SOURCE OF FUNDS. Only the citizenship fields are read here.

THE UNIT IS AN ORGANISATIONAL UNIT, NOT AN INSTITUTION. A university files one
row per school or department, so every figure here is summed by UNITID first.
Reading a row as an institution understates every large university.

FEDERAL SUPPORT IS A SEPARATE QUESTION FROM CITIZENSHIP, and the file does not
cross them: it reports how many postdocs are federally supported and how many
are foreign, but not how many are both. A page may not multiply the two.
check_consistency enforces that this caveat ships.

Usage:
  python3 scripts/build_postdoc_citizenship.py
"""
from __future__ import annotations

import io
import json
import sys
import warnings
import zipfile
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                               # noqa: E402

SRC = ROOT / "data" / "nsf_gss" / "graduate_students_postdocs_2024.zip"
INNER = "gss2024_code.sas7bdat"
OUT = ROOT / "site" / "data" / "postdoc_citizenship.json"

#: The nine named in the 2026-10-08 Department of Labor announcement. Matched
#: on UNITID, never on name: "Brown University" also matches Brown Mackie
#: College and a name match silently swaps one institution for another.
NAMED = {
    "166027": "Harvard University",
    "130794": "Yale University",
    "243744": "Stanford University",
    "217156": "Brown University",
    "215293": "University of Pittsburgh",
    "110644": "University of California, Davis",
    "110404": "California Institute of Technology",
    "104151": "Arizona State University",
    "166683": "Massachusetts Institute of Technology",
}

#: A floor, as in the sibling builder. A unit with nine postdocs and six
#: foreign ones is 67% and tells a reader nothing.
FLOOR = 50
TOP_N = 40

NEED = ["UNITID", "Institution_Name", "year",
        "pd_tot_all_races_v", "pd_tot_us_v", "pd_tot_forgn_v",
        "pd_tot_fed_all_v", "pd_tot_all_v",
        "pd_degr_us_v", "pd_degr_forgn_v"]

AGENCIES = [("nih", "NIH"), ("nsf", "NSF"), ("dod", "Defense"),
            ("doe", "Energy"), ("nasa", "NASA"), ("hhs", "HHS"),
            ("doa", "Agriculture")]


def load():
    import pandas as pd
    if not SRC.exists():
        raise SystemExit(
            f"missing {SRC.relative_to(ROOT)}\n"
            f"  restore: aws s3 cp s3://phd-demographics-raw-data/"
            f"{SRC.relative_to(ROOT)} {SRC.relative_to(ROOT)} --profile personal")
    with zipfile.ZipFile(SRC) as z:
        blob = z.read(INNER)
    frames, cols = [], None
    for ch in pd.read_sas(io.BytesIO(blob), format="sas7bdat",
                          encoding="latin-1", chunksize=20000):
        if cols is None:
            cols = set(ch.columns)
            missing = [c for c in NEED if c not in cols]
            if missing:
                #: Fail the build. A silently absent postdoc column reads as an
                #: institution with no postdocs, which is worse than a crash.
                raise SystemExit(f"GSS postdoc columns not found: {missing}")
        keep = NEED + [f"pd_tot_fed_{a}_v" for a, _ in AGENCIES
                       if f"pd_tot_fed_{a}_v" in cols]
        frames.append(ch[keep])
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    import pandas as pd
    df = load()
    year = str(df.year.max())
    d = df[df.year == df.year.max()]
    g = (d.groupby("UNITID", as_index=False)
           .agg({"Institution_Name": "first",
                 **{c: "sum" for c in d.columns
                    if c.startswith("pd_")}}))
    g["UNITID"] = g.UNITID.astype(str).str.replace(r"\.0$", "", regex=True)

    tot = float(g.pd_tot_all_races_v.sum())
    us = float(g.pd_tot_us_v.sum())
    forgn = float(g.pd_tot_forgn_v.sum())
    #: The split must be exhaustive or 'share foreign' means nothing.
    if abs(us + forgn - tot) > 1:
        raise SystemExit(
            f"citizenship does not sum: us {us:,.0f} + foreign {forgn:,.0f} "
            f"!= total {tot:,.0f}. The field meanings have changed.")

    def row(r):
        t = float(r.pd_tot_all_races_v)
        return {
            "unitid": str(r.UNITID),
            "institution": str(r.Institution_Name),
            "postdocs": int(t),
            "foreign": int(r.pd_tot_forgn_v),
            "us": int(r.pd_tot_us_v),
            "share": round(r.pd_tot_forgn_v / t * 100, 1) if t else 0.0,
            "federally_supported": int(r.pd_tot_fed_all_v),
        }

    named, miss = [], []
    for uid, label in NAMED.items():
        m = g[g.UNITID == uid]
        if m.empty:
            miss.append(f"{label} ({uid})")
            continue
        r = row(m.iloc[0])
        r["named_as"] = label
        named.append(r)
    if miss:
        raise SystemExit(f"named institutions not in the GSS file: {miss}")
    named.sort(key=lambda r: -r["share"])

    nt = sum(r["postdocs"] for r in named)
    nf = sum(r["foreign"] for r in named)

    ranked = [row(r) for r in g.itertuples()
              if float(r.pd_tot_all_races_v) >= FLOOR]
    ranked.sort(key=lambda r: -r["share"])

    fed = {}
    for a, label in AGENCIES:
        c = f"pd_tot_fed_{a}_v"
        if c in g.columns:
            fed[label] = int(g[c].sum())

    out = {
        "source": "NSF NCSES, Survey of Graduate Students and Postdoctorates",
        "source_url": "https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-s-e/",
        "year": year,
        "caveats": [
            "A postdoc counted as foreign holds a temporary visa. US citizens "
            "and permanent residents are counted as American.",
            "The survey reports how many postdocs are federally supported and "
            "how many are foreign. It does not report how many are both, so "
            "the two figures cannot be multiplied.",
            "Figures are summed from organisational units to the institution. "
            "A single GSS row is a school or department, not a university.",
            "This counts postdoctoral appointees. Graduate students are a "
            "different population and are measured separately.",
        ],
        "national": {
            "postdocs": int(tot),
            "foreign": int(forgn),
            "us": int(us),
            "share": round(forgn / tot * 100, 1),
            "federally_supported": int(g.pd_tot_fed_all_v.sum()),
            "federally_supported_share": round(
                g.pd_tot_fed_all_v.sum() / tot * 100, 1),
            "institutions": int(len(g[g.pd_tot_all_races_v > 0])),
            "doctorate_earned_abroad": int(g.pd_degr_forgn_v.sum()),
        },
        "federal_support_by_agency": fed,
        "named_institutions": {
            "announced": "2026-10-08, Department of Labor and Department of "
                         "Justice, J-1 visa investigation",
            "count": len(named),
            "postdocs": nt,
            "foreign": nf,
            "share": round(nf / nt * 100, 1),
            "institutions": named,
        },
        "ranking": {"floor": FLOOR, "top": ranked[:TOP_N],
                    "ranked_institutions": len(ranked)},
    }
    write_text(OUT, json.dumps(out, indent=2))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {year}: {int(tot):,} postdocs at {out['national']['institutions']} "
          f"institutions, {forgn/tot*100:.1f}% foreign")
    print(f"  the nine named: {nt:,} postdocs, {nf/nt*100:.1f}% foreign")
    print(f"  national federally supported: "
          f"{out['national']['federally_supported_share']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
