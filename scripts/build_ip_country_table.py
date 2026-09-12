#!/usr/bin/env python3
"""Build the IPv4 -> country table the analytics collector looks up.

WHY THIS EXISTS. The analytics Lambda read country and city from
`cloudfront-viewer-country` headers, but the collector is served by API
Gateway, not CloudFront, so those headers never arrived: zero of 1,088
recorded events carried a country, and the dashboard's country and city
charts had been empty since July. The full IP is stored, so the country is
recoverable from the IP itself.

THE SOURCE IS THE REGISTRIES, NOT A COMMERCIAL DATABASE. The five regional
internet registries each publish a delegation file listing every block they
have allocated and the country it was allocated to. They are free of licence
conditions, updated daily, and authoritative for allocation -- which is what
a country attribution can honestly claim.

WHAT IT CANNOT DO. This is the country an address block was ALLOCATED to, not
where the person sat. A VPN, a cloud region, a satellite link or a multinational
carrier will all read as the allocation country. There are no cities: the
registries do not publish them. Anyone quoting these figures should say
"allocated to", not "visitors from".

FORMAT. A sorted binary table of 6-byte records -- 4-byte big-endian range
start, 2-byte country code -- so a lookup is one bisect over an immutable
bytes object with no parsing and no per-request allocation. The range a lookup
lands in ends where the next one begins; a gap is encoded as the country "??".

Usage:
  python3 scripts/build_ip_country_table.py           # rebuild from data/geo/rir
  python3 scripts/build_ip_country_table.py --check    # verify, write nothing
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RIR = ROOT / "data" / "geo" / "rir"
OUT = ROOT / "data" / "geo" / "ip_country.bin"
REGISTRIES = ("arin", "ripencc", "apnic", "lacnic", "afrinic")
UNKNOWN = b"??"


def ranges() -> list[tuple[int, int, bytes]]:
    """(start, end_exclusive, cc) for every allocated IPv4 block."""
    out = []
    for name in REGISTRIES:
        path = RIR / f"delegated-{name}-extended-latest"
        if not path.exists():
            sys.exit(f"missing {path.relative_to(ROOT)}; see the module docstring "
                     "for the five URLs")
        for line in path.read_text(errors="replace").splitlines():
            if not line or line[0] == "#":
                continue
            f = line.split("|")
            # registry|cc|type|start|value|date|status|opaque-id
            if len(f) < 7 or f[2] != "ipv4" or f[6] not in ("allocated", "assigned"):
                continue
            cc = f[1].strip().upper()
            if len(cc) != 2:
                continue                      # summary lines carry no country
            try:
                a, b, c, d = (int(x) for x in f[3].split("."))
                start = (a << 24) | (b << 16) | (c << 8) | d
                count = int(f[4])
            except (ValueError, AttributeError):
                continue
            out.append((start, start + count, cc.encode()))
    out.sort()
    return out


def table(rs: list[tuple[int, int, bytes]]) -> bytes:
    """Sorted 6-byte records, with gaps between blocks marked unknown.

    Adjacent blocks of the same country are merged, which removes about half
    the rows: the registries hand out many small consecutive blocks to the
    same place.
    """
    recs: list[tuple[int, bytes]] = []
    prev_end = 0
    for start, end, cc in rs:
        if start < prev_end:
            continue                          # overlap; first allocation wins
        if start > prev_end:
            recs.append((prev_end, UNKNOWN))   # unallocated gap
        if not recs or recs[-1][1] != cc:
            recs.append((start, cc))
        prev_end = max(prev_end, end)
    if prev_end < 1 << 32:
        recs.append((prev_end, UNKNOWN))
    return b"".join(struct.pack(">I2s", s, cc) for s, cc in recs)


def lookup(blob: bytes, ip: str) -> str:
    """The country an address was allocated to, or '' if unknown.

    Mirrors the Lambda's copy; both are exercised by tests/test_ip_country.py.
    """
    try:
        a, b, c, d = (int(x) for x in ip.split("."))
    except ValueError:
        return ""                             # IPv6 or malformed
    if not all(0 <= x <= 255 for x in (a, b, c, d)):
        return ""
    n = (a << 24) | (b << 16) | (c << 8) | d
    lo, hi = 0, len(blob) // 6
    while lo < hi:                            # last record with start <= n
        mid = (lo + hi) // 2
        if struct.unpack_from(">I", blob, mid * 6)[0] <= n:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return ""
    cc = blob[(lo - 1) * 6 + 4:(lo - 1) * 6 + 6]
    return "" if cc == UNKNOWN else cc.decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rs = ranges()
    blob = table(rs)
    rows = len(blob) // 6
    countries = {cc for _s, _e, cc in rs}
    print(f"  {len(rs):,} allocated blocks -> {rows:,} table rows "
          f"({len(blob)/1024:.0f} KB), {len(countries)} countries")
    # Spot checks against well-known allocations, so a broken parse is loud.
    for ip, want in (("8.8.8.8", "US"), ("1.1.1.1", "AU"), ("193.0.6.139", "NL"),
                     ("139.130.4.5", "AU"), ("196.25.1.1", "ZA")):
        got = lookup(blob, ip)
        print(f"    {ip:15} -> {got or '(unknown)':9} expected {want}"
              f"{'' if got == want else '   MISMATCH'}")
    if not args.check:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_bytes(blob)
        print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
