#!/usr/bin/env python3
"""Turn the Census state boundary shapefile into a compact offline basemap.

WHY NOT A TILE SERVICE
    A slippy map needs a tile server, which is a hosted dependency and a
    recurring cost, and the artifact CSP blocks external hosts anyway. The
    firms only need to be seen against state outlines, which is 0.17 MB of
    public-domain Census data rendered once into an inline SVG path set.

WHY NO SHAPEFILE LIBRARY
    pyshp/geopandas would be a new pinned dependency for a one-time
    conversion. The polygon subset of the shapefile format is a documented
    little-endian record layout and reads in about forty lines of struct, so
    the conversion is done here and only the result is kept.

    Reference: ESRI Shapefile Technical Description, shape type 5 (Polygon).

OUTPUT
    data/geo/us_states.json -- {abbr: [[ [x,y], ... ], ...]} in Albers USA
    projected coordinates, already simplified, ready to emit as SVG paths.

USAGE
    python3 scripts/build_us_basemap.py
"""
from __future__ import annotations

import io
import json
import math
import os
import struct
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "geo" / "us_states.json"
URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip"

# Alaska and Hawaii are moved and scaled, as every US map does, so the lower 48
# are not squeezed into a corner. Territories are dropped.
SKIP = {"PR", "VI", "GU", "MP", "AS"}


def read_polygons(shp: bytes) -> list[list[list[tuple[float, float]]]]:
    """Every polygon record's rings. Shape type 5 only."""
    out, pos, n = [], 100, len(shp)          # 100-byte file header
    while pos < n:
        _num, clen = struct.unpack(">ii", shp[pos:pos + 8])
        body = shp[pos + 8: pos + 8 + clen * 2]
        pos += 8 + clen * 2
        if len(body) < 4 or struct.unpack("<i", body[:4])[0] != 5:
            continue
        nparts, npoints = struct.unpack("<ii", body[36:44])
        parts = struct.unpack(f"<{nparts}i", body[44:44 + 4 * nparts])
        px = 44 + 4 * nparts
        pts = struct.unpack(f"<{2 * npoints}d", body[px:px + 16 * npoints])
        rings = []
        for i, s in enumerate(parts):
            e = parts[i + 1] if i + 1 < nparts else npoints
            rings.append([(pts[2 * j], pts[2 * j + 1]) for j in range(s, e)])
        out.append(rings)
    return out


def read_dbf_field(dbf: bytes, want: str) -> list[str]:
    """One character column out of the .dbf, by name."""
    hlen, rlen = struct.unpack("<HH", dbf[8:12])
    fields, pos = [], 32
    while dbf[pos] != 0x0D:
        name = dbf[pos:pos + 11].split(b"\0")[0].decode("latin-1")
        flen = dbf[pos + 16]
        fields.append((name, flen))
        pos += 32
    off = {}
    o = 1
    for nm, fl in fields:
        off[nm] = (o, fl)
        o += fl
    if want not in off:
        raise SystemExit(f"no {want} column; have {[f[0] for f in fields]}")
    s, ln = off[want]
    vals, p = [], hlen
    while p + rlen <= len(dbf):
        rec = dbf[p:p + rlen]
        if rec[:1] != b"*":                  # not deleted
            vals.append(rec[s:s + ln].decode("latin-1").strip())
        p += rlen
    return vals


def albers(lon: float, lat: float) -> tuple[float, float]:
    """Albers equal-area conic, the standard projection for a US map."""
    lo, la = math.radians(lon), math.radians(lat)
    lo0, la0 = math.radians(-96.0), math.radians(37.5)
    p1, p2 = math.radians(29.5), math.radians(45.5)
    n = 0.5 * (math.sin(p1) + math.sin(p2))
    c = math.cos(p1) ** 2 + 2 * n * math.sin(p1)
    rho0 = math.sqrt(c - 2 * n * math.sin(la0)) / n
    rho = math.sqrt(c - 2 * n * math.sin(la)) / n
    th = n * (lo - lo0)
    return rho * math.sin(th), rho0 - rho * math.cos(th)


def simplify(ring, tol=0.0022):
    """Drop points closer than tol, keeping the ring closed."""
    out = [ring[0]]
    for p in ring[1:]:
        if (p[0] - out[-1][0]) ** 2 + (p[1] - out[-1][1]) ** 2 > tol * tol:
            out.append(p)
    if len(out) > 2 and out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) > 3 else None


def main() -> int:
    print(f"  fetching {URL}")
    r = requests.get(URL, timeout=180)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        shp = zf.read(next(n for n in zf.namelist() if n.endswith(".shp")))
        dbf = zf.read(next(n for n in zf.namelist() if n.endswith(".dbf")))
    polys, abbrs = read_polygons(shp), read_dbf_field(dbf, "STUSPS")
    if len(polys) != len(abbrs):
        print(f"  ABORT: {len(polys)} shapes vs {len(abbrs)} names")
        return 1

    states: dict[str, list] = {}
    for abbr, rings in zip(abbrs, polys):
        if abbr in SKIP:
            continue
        keep = []
        for ring in rings:
            pr = [albers(x, y) for x, y in ring]
            if abbr == "AK":                 # inset, scaled and moved
                pr = [(x * 0.34 - 0.42, y * 0.34 + 0.52) for x, y in pr]
            elif abbr == "HI":
                pr = [(x * 0.9 + 0.34, y * 0.9 + 0.32) for x, y in pr]
            s = simplify(pr)
            if s:
                keep.append([[round(x, 5), round(y, 5)] for x, y in s])
        if keep:
            # Biggest rings first, so a renderer can drop small islands.
            keep.sort(key=len, reverse=True)
            states[abbr] = keep[:6]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.partial")
    tmp.write_text(json.dumps(states, separators=(",", ":")))
    os.replace(tmp, OUT)
    pts = sum(len(r) for v in states.values() for r in v)
    print(f"  {len(states)} states, {pts:,} points -> {OUT} "
          f"({OUT.stat().st_size/1024:.0f} KB)")
    print("  Source: US Census Bureau cartographic boundary files, public domain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
