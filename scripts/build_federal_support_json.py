#!/usr/bin/env python3
"""Build per-university federal S&E obligations from NCSES Federal Support Survey.

Source: NSF 25-339 Table 17, "Federal obligations for science and engineering to
universities and colleges, ranked by total amount received, by type of activity".
Unlike NSF Award Search and NIH RePORTER, which cover one agency each, this
counts obligations from every federal agency — and it breaks out S&E
fellowships, traineeships and training grants, which is federal money spent
specifically on graduate training rather than on research generally.

Institution names follow the same NCSES convention as the HERD survey, so the
existing HERD name for each university is the join key. The two differ in
campus suffixes and stray "The" tokens ("Cornell U." vs "Cornell U., Ithaca",
"U. Utah" vs "U. Utah, The"), so matching is done on normalised tokens.

Usage:
    python scripts/build_federal_support_json.py            # build
    python scripts/build_federal_support_json.py --report   # show match quality
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl required: pip install openpyxl")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "federal_support" / "nsf25339-tab017.xlsx"
HERD = ROOT / "data" / "herd" / "funding_by_university.json"
OUT = ROOT / "data" / "federal_support" / "federal_support_by_university.json"

FIELDS = [
    ("all_federal_obligations", 2),
    ("rd", 3),
    ("rd_plant", 4),
    ("facilities_equipment", 5),
    ("fellowships_traineeships_training", 6),
    ("other_general_support", 7),
]

# Two universities need naming help. Buffalo because token matching cannot
# safely distinguish "State U. New York, The, U. at Buffalo" from the entirely
# separate "State U. New York at Buffalo State U."; LSU because Table 17
# reports it only at system level, exactly as the USCIS H-1B data does, so the
# figure covers more than the Baton Rouge campus and is flagged as such.
NAME_OVERRIDES = {
    "ubuffalo": "State U. New York, The, U. at Buffalo",
    "lsu": "Louisiana State U., system office",
}
SYSTEM_LEVEL = {"lsu"}

# Words that carry no identifying information in NCSES institution names.
# "u" and "c" are deliberately NOT stripped: NCSES abbreviates University as
# "U." and College as "C.", and dropping them collapses genuinely different
# institutions onto each other — Boston U. and Boston C., U. Central Florida
# and C. Central Florida, Wayne State U. and Wayne State C. Both sides of the
# join use the same convention, so keeping them costs nothing.
STOP = {"the", "and", "of", "at"}


def normalize(name: str) -> frozenset[str]:
    """Reduce an institution name to its identifying tokens."""
    n = name.lower()
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    return frozenset(t for t in n.split() if t and t not in STOP)


def score(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard overlap, with a penalty when neither side contains the other."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    # A subset match ("u washington" inside "u washington seattle") is strong.
    if a <= b or b <= a:
        return 0.95 + 0.05 * (inter / max(len(a), len(b)))
    return inter / len(a | b)


def load_table():
    """Return (token_index, exact_index).

    Distinct institutions can normalise to the same token set — "State U. New
    York, The, U. at Buffalo" and "State U. New York at Buffalo State U." both
    reduce to {state, new, york, buffalo}, and they are different schools with
    a 900-fold difference in federal funding. Keying only by tokens silently
    drops one of them, so an exact-name index is kept alongside and the
    overrides resolve against it.
    """
    wb = openpyxl.load_workbook(SRC, data_only=True)
    rows = list(wb["Table 17"].iter_rows(values_only=True))
    tokens, exact = {}, {}
    for r in rows[4:]:
        if not r or not r[0]:
            continue
        name = str(r[0]).strip()
        if name.lower().startswith("all institutions"):
            continue
        exact[name] = r
        tokens.setdefault(normalize(name), (name, r))
    return tokens, exact


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="Print match quality and exit")
    ap.add_argument("--min-score", type=float, default=0.6)
    args = ap.parse_args()

    table, exact = load_table()
    herd = json.load(open(HERD))
    unis = herd.get("universities", herd)

    matched, unmatched, weak = {}, [], []
    for key, entry in unis.items():
        herd_name = (entry.get("name") or "").strip()
        if not herd_name:
            unmatched.append((key, "(no HERD name)"))
            continue
        override = NAME_OVERRIDES.get(key)
        if override:
            if override not in exact:
                unmatched.append((key, f"{herd_name} (override {override!r} not in source)"))
                continue
            best, best_score = (override, exact[override]), 1.0
        else:
            target = normalize(herd_name)
            best, best_score = None, 0.0
            for toks, (name, row) in table.items():
                s = score(target, toks)
                if s > best_score:
                    best, best_score = (name, row), s
        if not best or best_score < args.min_score:
            unmatched.append((key, herd_name))
            continue
        name, row = best

        def num(i):
            v = row[i] if i < len(row) else None
            try:
                # Source is in thousands of dollars.
                return int(round(float(v) * 1000))
            except (TypeError, ValueError):
                return 0

        matched[key] = {
            "source_name": name,
            "system_level": key in SYSTEM_LEVEL,
            "matched_from": herd_name,
            "match_score": round(best_score, 3),
            "fiscal_year": 2023,
            "rank": int(row[1]) if isinstance(row[1], (int, float)) else None,
            **{field: num(idx) for field, idx in FIELDS},
        }
        if best_score < 0.85:
            weak.append((key, herd_name, name, round(best_score, 3)))

    if args.report:
        print(f"matched {len(matched)}/{len(unis)}")
        if weak:
            print(f"\nweak matches ({len(weak)}) — verify these:")
            for k, h, n, s in sorted(weak, key=lambda x: x[3]):
                print(f"  {k:<16} {s:<6} {h!r} -> {n!r}")
        if unmatched:
            print(f"\nunmatched ({len(unmatched)}):")
            for k, h in unmatched:
                print(f"  {k:<16} {h!r}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_metadata": {
            "source": "NSF NCSES Federal Support Survey, NSF 25-339 Table 17",
            "source_url": "https://ncses.nsf.gov/pubs/nsf25339",
            "fiscal_year": 2023,
            "units": "US dollars (source reports thousands; converted here)",
            "note": (
                "Obligations from all federal agencies, not just NSF and NIH. "
                "fellowships_traineeships_training is federal money for graduate "
                "training specifically."
            ),
            "matched": len(matched),
            "unmatched": [k for k, _ in unmatched],
        },
        "universities": matched,
    }
    OUT.write_text(json.dumps(payload, indent=1))
    total = sum(v["all_federal_obligations"] for v in matched.values())
    fell = sum(v["fellowships_traineeships_training"] for v in matched.values())
    print(f"Wrote {OUT}")
    print(f"  {len(matched)}/{len(unis)} universities matched")
    print(f"  ${total/1e9:.1f}B total federal obligations, "
          f"${fell/1e9:.2f}B of it fellowships/traineeships/training")
    return 0


if __name__ == "__main__":
    sys.exit(main())
