#!/usr/bin/env python3
"""
Build cloud/chat/chat_data/search_index.bin — the term index behind the chat
assistant's `search_records` tool.

WHAT IT INDEXES

  The TITLE text of every harvested dissertation / thesis record in
  site/data/{stem,nonstem}/{key}.json.  Nothing else: author names, repository
  URLs, degree labels and abstracts are not indexed and cannot be searched.

WHAT A POSTING RESOLVES TO

  A cell = (university, department, year), not a record.  So a posting says
  "this term occurs in N titles from this department in this year", which is
  what the tool reports.  It cannot reconstruct a title, and cannot answer
  "which record" — deliberately, on both size and privacy grounds.

WHY NOT RECORD LEVEL (measured, not assumed)

  517,715 records, 99 MB of per-university JSON.
    packed (uni, dept, year, title, degree) TSV : 56.7 MB raw, 17.5 MB gzip
    titles alone                                : 39.9 MB raw, 15.2 MB gzip
    record-level postings, df>=5                : 3.68 M postings,
                                                  6.24 MB raw, 5.69 MB gzip
    cell-level postings, df>=5 (this file)      : 2.97 M postings,
                                                  6.81 MB raw, 3.67 MB lzma
  The Lambda ships 2.0 MB of data today against a ~6 MB budget.  Record-level
  search does not fit even before a table to render a hit from.

FILE FORMAT

  lzma( uint32 header_len | header JSON (utf-8) | binary sections )

  The header stays small on purpose: json.loads of a 1.4 MB header cost 1.9 s
  of cold start, six times the cost of the LZMA inflate itself.  Everything
  with one entry per term or per cell therefore lives in a binary section that
  the reader maps with array.array (little-endian; the reader byteswaps on a
  big-endian host).

  header  = {records, universities[105], departments[], year_min, year_max,
             min_df, n_terms, n_cells, sections{name: [offset, length]}, ...}
  vocab     section  vocabulary terms, newline separated, utf-8, sorted
  cell_u/d/y         one entry per cell: uint8 university, uint16 department,
                     uint16 year (0 = year unknown), cells sorted by (u, d, y)
  dlen/clen section  uint32 byte-length per term, vocab order, one for each
                     postings stream
  pdelta    section  per term, a varint run of ascending cell-id deltas
  pcount    section  per term, a varint run of record counts, same order
                     (kept apart from pdelta because the two streams have very
                     different statistics and LZMA models them better split)

  The tokenizer and stopword list live in cloud/chat/tools_search.py and are
  imported here so the index and the query path cannot drift apart.

Usage:
    python3 scripts/build_chat_search_index.py
    python3 scripts/build_chat_search_index.py --out-dir /some/where --min-df 5
"""
from __future__ import annotations

import argparse
import array
import collections
import datetime
import glob
import json
import lzma
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DATA = os.path.join(ROOT, "site", "data")
DEFAULT_OUT = os.path.join(ROOT, "cloud", "chat", "chat_data")

sys.path.insert(0, os.path.join(ROOT, "cloud", "chat"))
from tools_search import MIN_DF, tokenize  # noqa: E402

# Record tuple layout in site/data/{stem,nonstem}/{key}.json:
#   0 department, 1 year, 2 author, 3 name_origin, 4 confidence,
#   5 title, 6 url, 7 degree
DEPT, YEAR, TITLE = 0, 1, 5


def varint(n: int, out: bytearray) -> None:
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)


def read_records(site_data: str):
    """Yield (university_key, department, year, title)."""
    for sub in ("stem", "nonstem"):
        for path in sorted(glob.glob(os.path.join(site_data, sub, "*.json"))):
            base = os.path.basename(path)
            if base.startswith("_"):          # _search.json is a browser artifact
                continue
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            key = doc.get("key") or base[:-5]
            for r in doc.get("records") or []:
                if len(r) <= TITLE:
                    continue
                try:
                    year = int(r[YEAR])
                except (TypeError, ValueError):
                    continue
                yield key, (r[DEPT] or "").strip(), year, r[TITLE] or ""


def build(site_data: str, min_df: int):
    records = list(read_records(site_data))
    if not records:
        raise SystemExit(f"no records found under {site_data}")

    unis = sorted({k for k, _d, _y, _t in records})
    depts = sorted({d for _k, d, _y, _t in records})
    uni_i = {k: i for i, k in enumerate(unis)}
    dept_i = {d: i for i, d in enumerate(depts)}

    cell_keys = sorted({(uni_i[k], dept_i[d], y) for k, d, y, _t in records})
    cell_i = {c: i for i, c in enumerate(cell_keys)}

    df = collections.Counter()
    per_cell = []
    for k, d, y, title in records:
        terms = set(tokenize(title))
        per_cell.append((cell_i[(uni_i[k], dept_i[d], y)], terms))
        df.update(terms)

    vocab = sorted(t for t, c in df.items() if c >= min_df)
    keep = set(vocab)
    post = collections.defaultdict(collections.Counter)
    for cid, terms in per_cell:
        for t in terms:
            if t in keep:
                post[t][cid] += 1

    # Cell deltas and counts go into SEPARATE contiguous streams rather than
    # interleaved (delta, count, delta, count) pairs.  Same bytes of varint,
    # but the two streams have very different statistics -- 87.6% of all counts
    # are 1 -- and LZMA models them far better apart: 3.67 MB interleaved
    # against 3.21 MB split, for identical answers.
    dblob, cblob = bytearray(), bytearray()
    dlen, clen = [], []
    for t in vocab:
        ds_, cs_ = len(dblob), len(cblob)
        prev = 0
        cids = sorted(post[t])
        for cid in cids:
            varint(cid - prev, dblob)
            prev = cid
        for cid in cids:
            varint(post[t][cid], cblob)
        dlen.append(len(dblob) - ds_)
        clen.append(len(cblob) - cs_)

    def le(typecode, values):
        arr = array.array(typecode, values)
        if sys.byteorder != "little":
            arr.byteswap()
        return arr.tobytes()

    sections, body = {}, bytearray()

    def add(name, payload_bytes):
        sections[name] = [len(body), len(payload_bytes)]
        body.extend(payload_bytes)

    add("vocab", "\n".join(vocab).encode("utf-8"))
    add("cell_u", le("B", [c[0] for c in cell_keys]))
    add("cell_d", le("H", [c[1] for c in cell_keys]))
    add("cell_y", le("H", [c[2] if 1900 <= c[2] <= 2100 else 0 for c in cell_keys]))
    add("dlen", le("I", dlen))
    add("clen", le("I", clen))
    add("pdelta", bytes(dblob))
    add("pcount", bytes(cblob))

    # A handful of records carry no usable year; the source file stores 0.  They
    # stay in the index (they are real records) but must not set the range.
    years = [y for _k, _d, y, _t in records if 1900 <= y <= 2100]
    header = {
        "records": len(records),
        "universities": unis,
        "departments": depts,
        "n_cells": len(cell_keys),
        "n_terms": len(vocab),
        "sections": sections,
        "year_min": min(years),
        "year_max": max(years),
        "records_without_year": sum(1 for _k, _d, y, _t in records if not (1900 <= y <= 2100)),
        "min_df": min_df,
        "grain": "institution x department x year",
        "built": datetime.date.today().isoformat(),
        "indexes": "dissertation and thesis TITLE text only",
    }
    hb = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload = struct.pack("<I", len(hb)) + hb + bytes(body)
    return (header, payload, len(dblob) + len(cblob),
            sum(len(v) for v in post.values()), len(hb))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-data", default=SITE_DATA)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--min-df", type=int, default=MIN_DF)
    a = ap.parse_args()

    header, payload, blob_len, n_post, hlen = build(a.site_data, a.min_df)
    out = os.path.join(a.out_dir, "search_index.bin")
    os.makedirs(a.out_dir, exist_ok=True)
    comp = lzma.compress(payload, preset=6)
    with open(out, "wb") as fh:
        fh.write(comp)

    print(f"wrote {out}")
    print(f"  records   {header['records']:,}")
    print(f"  years     {header['year_min']}-{header['year_max']}")
    print(f"  unis      {len(header['universities'])}")
    print(f"  depts     {len(header['departments'])}")
    print(f"  cells     {header['n_cells']:,}")
    print(f"  vocab     {header['n_terms']:,} terms (df >= {a.min_df})")
    print(f"  postings  {n_post:,}")
    print(f"  header    {hlen / 1e3:.0f} kB JSON")
    print(f"  blob      {blob_len / 1e6:.2f} MB raw")
    print(f"  payload   {len(payload) / 1e6:.2f} MB raw -> {len(comp) / 1e6:.2f} MB lzma")


if __name__ == "__main__":
    main()
