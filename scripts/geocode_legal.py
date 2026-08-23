#!/usr/bin/env python3
"""Put the immigration firms and attorneys on the map, entirely offline.

No geocoding service, no API key, no per-request cost. Coordinates come from
the vendored GeoNames postal table (scripts/download_geonames.py), which is
0.6 MB and resolves both of the shapes the LCA addresses actually take:

    "800 NW 62nd Avenue, Suite 590, Miami, FL, 33126"  -> by postcode
    "CORAL GABLES, FL"                                 -> by city and state

PRECISION, STATED HONESTLY
    A postcode centroid is not a rooftop. It is the right resolution for this
    question -- these are office suites, and the map answers "where do the
    firms that file for universities sit", not "which door". Every output
    record carries how it was matched (`postal`, `city`, or `none`) so a
    reader can tell a postcode centroid from a city centroid, and nothing is
    silently upgraded.

USAGE
    python3 scripts/geocode_legal.py
    python3 scripts/geocode_legal.py --report
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "data" / "geo" / "US_postal.txt"
SRC = ROOT / "data" / "h1b" / "lca_legal_by_university.json"
OUT = ROOT / "data" / "h1b" / "lca_legal_geo.json"


# GeoNames writes these out in full; LCA filers abbreviate them. Without this
# "ST. LOUIS, MO" misses "Saint Louis, MO" and the attorney goes unlocated.
_CITY_WORDS = {"ST": "SAINT", "STE": "SAINTE", "FT": "FORT", "MT": "MOUNT",
               "PT": "POINT", "N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST"}


def _city_key(name: str) -> str:
    """Normalise a city name so abbreviations and spellings agree."""
    words = re.sub(r"[.,]", " ", (name or "").upper()).split()
    return " ".join(_CITY_WORDS.get(w, w) for w in words)


class OfflineGeocoder:
    """Postcode and city/state lookup over the GeoNames table."""

    def __init__(self, path: Path = GEO):
        if not path.exists():
            raise SystemExit(f"{path} missing. Run scripts/download_geonames.py")
        self.by_zip: dict[str, tuple[float, float, str, str]] = {}
        city_pts: dict[tuple[str, str], list[tuple[float, float]]] = \
            collections.defaultdict(list)
        for line in path.open(encoding="utf-8"):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 11 or not f[9] or not f[10]:
                continue
            try:
                lat, lon = float(f[9]), float(f[10])
            except ValueError:
                continue
            zipc, city, st = f[1].strip(), f[2].strip(), f[4].strip().upper()
            if zipc and zipc not in self.by_zip:
                self.by_zip[zipc] = (lat, lon, city, st)
            if city and st:
                city_pts[(_city_key(city), st)].append((lat, lon))
        # A city spans several postcodes; its centroid is their mean.
        self.by_city = {k: (sum(p[0] for p in v) / len(v),
                            sum(p[1] for p in v) / len(v), len(v))
                        for k, v in city_pts.items()}

    def locate(self, address: str) -> dict | None:
        a = (address or "").strip()
        if not a:
            return None
        m = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", a)
        if m and m.group(1) in self.by_zip:
            lat, lon, city, st = self.by_zip[m.group(1)]
            return {"lat": lat, "lon": lon, "city": city, "state": st,
                    "zip": m.group(1), "matched_on": "postal"}
        # Fall back to the trailing ", CITY, ST" of the address.
        parts = [p.strip() for p in a.split(",") if p.strip()]
        for i in range(len(parts) - 1, 0, -1):
            st = parts[i].upper()
            key = (_city_key(parts[i - 1]), st)
            if len(st) == 2 and key in self.by_city:
                lat, lon, n = self.by_city[key]
                return {"lat": round(lat, 4), "lon": round(lon, 4),
                        "city": parts[i - 1].title(), "state": st, "zip": None,
                        "matched_on": "city", "postcodes_averaged": n}
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if not SRC.exists():
        raise SystemExit(f"{SRC} missing. Build it with scripts/aws_lca_rebuild.sh")
    d = json.loads(SRC.read_text())
    geo = OfflineGeocoder()
    print(f"  gazetteer: {len(geo.by_zip):,} postcodes, {len(geo.by_city):,} cities")

    out_att, stats = {}, collections.Counter()
    for name, v in d["attorneys"].items():
        loc = None
        for addr, _n in v["addresses"]:          # most-used address first
            loc = geo.locate(addr)
            if loc:
                break
        stats[loc["matched_on"] if loc else "none"] += 1
        out_att[name] = {"filings": v["filings"], "location": loc,
                         "firm": v["firms"][0][0] if v["firms"] else None}

    # A firm sits where its attorneys file from, weighted by filing volume.
    firm_pts: dict[str, list] = collections.defaultdict(list)
    for name, v in out_att.items():
        if v["location"] and v["firm"]:
            firm_pts[v["firm"]].append((v["location"], v["filings"]))
    out_firm = {}
    for firm, pts in firm_pts.items():
        w = sum(n for _, n in pts)
        out_firm[firm] = {
            "filings": d["firms"].get(firm, {}).get("filings"),
            "lat": round(sum(p["lat"] * n for p, n in pts) / w, 4),
            "lon": round(sum(p["lon"] * n for p, n in pts) / w, 4),
            "offices": sorted({(p["city"], p["state"]) for p, _ in pts}),
            "attorneys_located": len(pts),
            "matched_on": "weighted mean of its attorneys' locations",
        }

    payload = {"_meta": {
        "gazetteer": "GeoNames US postal codes, CC-BY 4.0, vendored offline",
        "precision": ("postcode or city centroid, never rooftop; each record "
                      "states which via matched_on"),
        "attorneys_located": f"{stats['postal'] + stats['city']} of {len(out_att)}",
        "by_method": dict(stats),
    }, "attorneys": out_att, "firms": out_firm}
    tmp = OUT.with_suffix(".json.partial")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    os.replace(tmp, OUT)

    print(f"  attorneys located: {stats['postal']} by postcode, "
          f"{stats['city']} by city, {stats['none']} unlocated")
    print(f"  firms located:     {len(out_firm)}")
    print(f"  wrote {OUT}")

    if args.report:
        st = collections.Counter()
        for v in out_att.values():
            if v["location"]:
                st[v["location"]["state"]] += v["filings"]
        print("\n  FILINGS BY STATE OF THE FILING ATTORNEY")
        for s, n in st.most_common(12):
            print(f"    {s}  {n:>7,}  {'#' * max(1, round(46 * n / st.most_common(1)[0][1]))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
