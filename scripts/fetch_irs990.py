#!/usr/bin/env python3
"""Harvest the public 501(c)(3) record: IRS bulk extracts, IRS Form 990
e-file XML, and the NCCS panel that reaches back to 1987.

WHY THIS IS A HARVESTER AND NOT A BUILDER

It writes no dataset. It retrieves roughly 62 GB of source material that
several builders will later read, and it is separate because the retrieval is
slow, resumable and mostly archival.

WHERE IT PUTS THINGS

The whole archive goes to s3://phd-demographics-raw-data/data/irs990/, because
26 GB of IRS XML and 35 GB of NCCS panel do not fit on this machine beside
everything else -- there is about 21 GB free. Each file is downloaded, checked,
uploaded and then deleted locally unless it is small enough and useful enough
to keep. Peak local use is one file.

The small structured extracts stay on disk: the Business Master File, the
Publication 78 list, the auto-revocation list and the e-Postcard dump come to
roughly 400 MB together and are what most questions actually need.

THE RULES THIS FOLLOWS, FROM CLAUDE.md

  * Retrieved data is append-only. An object is replaced only by a LARGER
    one. A local file smaller than the object already in S3 is the signature
    of a truncated download, and in that case S3 holds the good copy and the
    local file is discarded.
  * Never --delete. Nothing here removes an object.
  * Verify before deleting locally. A file whose size does not match what the
    server promised is never uploaded and never counted.
  * Declare where it went. Every run prints the restore command.

RESUMABLE. A file already in S3 at the expected size is skipped without being
downloaded, so an interrupted run costs only the file it was working on.

Usage:
  python3 scripts/fetch_irs990.py --list                 # what would be fetched
  python3 scripts/fetch_irs990.py --group irs_bulk       # one group
  python3 scripts/fetch_irs990.py                        # everything
  python3 scripts/fetch_irs990.py --restore nccs/harmonized   # pull back from S3
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "irs990"
BUCKET = "phd-demographics-raw-data"
PREFIX = "data/irs990"
#: On this machine the bucket needs the named profile. On EC2 the instance
#: profile supplies the credentials and passing --profile would break it, so
#: the flag is omitted when the role is present. CLAUDE.md requires both:
#: "Every restore uses --profile personal, and the EC2 rebuild job uses an
#: IAM instance profile."
PROFILE = os.environ.get("AWS_PROFILE_OVERRIDE", "personal")
ON_EC2 = os.environ.get("PHD_ON_EC2") == "1"
PROFILE_ARGS: list[str] = [] if ON_EC2 else ["--profile", PROFILE]

#: Keep locally after upload. Everything else is archival and is deleted.
#: These are the files a question is most likely to need in a hurry, and
#: together they are about 400 MB.
KEEP_LOCAL = ("irs_bulk/",)

UA = {"User-Agent": "phd-demographics research harvester (+https://phd-demographics.andy-barr.com)"}

IRS_990_INDEX = "https://www.irs.gov/charities-non-profits/form-990-series-downloads"
NCCS_INDEX = "https://urbaninstitute.github.io/nccs/catalogs/catalog-core.html"

#: The Business Master File comes in four regional extracts plus a fifth for
#: organisations with no state. All five are needed; eo_xx alone is the one
#: people forget and it carries the ones filed from abroad.
IRS_BULK = [
    ("https://www.irs.gov/pub/irs-soi/eo1.csv", "eo_bmf_region1.csv"),
    ("https://www.irs.gov/pub/irs-soi/eo2.csv", "eo_bmf_region2.csv"),
    ("https://www.irs.gov/pub/irs-soi/eo3.csv", "eo_bmf_region3.csv"),
    ("https://www.irs.gov/pub/irs-soi/eo4.csv", "eo_bmf_region4.csv"),
    ("https://www.irs.gov/pub/irs-soi/eo_xx.csv", "eo_bmf_no_state.csv"),
    ("https://apps.irs.gov/pub/epostcard/data-download-pub78.zip", "pub78.zip"),
    ("https://apps.irs.gov/pub/epostcard/data-download-revocation.zip",
     "auto_revocation.zip"),
    ("https://apps.irs.gov/pub/epostcard/data-download-epostcard.zip",
     "epostcard_990n.zip"),
]


#: A 930-file, 62 GB harvest over a home connection WILL hit a transient
#: failure. The first run lost six of eight files to one network blip and
#: reported them as failures, which is correct but useless: the job has to
#: survive the blip, not report it. Backoff is exponential and capped.
ATTEMPTS = 5
BACKOFF = 4


def retry(what: str, fn, attempts: int = ATTEMPTS):
    """Run fn, retrying transient failures. Returns (ok, value_or_error)."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return True, fn()
        except Exception as exc:                        # noqa: BLE001
            last = exc
            if i < attempts:
                wait = BACKOFF ** min(i, 4)
                print(f"\n      {what} attempt {i} failed "
                      f"({type(exc).__name__}); retrying in {wait}s ",
                      end="", flush=True)
                time.sleep(wait)
    return False, last


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def s3_sizes() -> dict[str, int]:
    """Every object already archived, by key suffix, with its size.

    One listing rather than a head per file: with 900 files the round trips
    dominate the run.
    """
    out: dict[str, int] = {}
    r = run(["aws", "s3", "ls", f"s3://{BUCKET}/{PREFIX}/", "--recursive"]
            + PROFILE_ARGS)
    if r.returncode != 0:
        print(f"  ! could not list S3: {r.stderr.strip()[:200]}")
        return out
    for line in r.stdout.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) == 4 and parts[3].startswith(PREFIX + "/"):
            out[parts[3][len(PREFIX) + 1:]] = int(parts[2])
    return out


def remote_size(url: str) -> int | None:
    """What the server says the file is, by HEAD or by a one-byte range.

    The NCCS bucket answers HEAD without a content-length, so a ranged GET is
    the fallback. Returning None means unknown, and an unknown size is never
    treated as a mismatch -- only as a thing that cannot be verified.
    """
    for attempt in range(3):
      try:
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            n = r.headers.get("Content-Length")
            if n:
                return int(n)
      except Exception:                                 # noqa: BLE001
        time.sleep(2 * (attempt + 1))
    for attempt in range(3):
      try:
        req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            cr = r.headers.get("Content-Range", "")
            m = re.search(r"/(\d+)$", cr)
            if m:
                return int(m.group(1))
      except Exception:                                 # noqa: BLE001
        time.sleep(2 * (attempt + 1))
    return None


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return str(n)


def fetch(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    tmp.replace(dest)
    return dest.stat().st_size


def upload(local: Path, key: str) -> bool:
    def once():
        r = run(["aws", "s3", "cp", str(local),
                 f"s3://{BUCKET}/{PREFIX}/{key}"] + PROFILE_ARGS
                + ["--only-show-errors"])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:160] or "aws s3 cp failed")
        return True
    ok, err = retry("upload", once)
    if not ok:
        print(f"\n    ! upload failed after {ATTEMPTS} attempts: "
              f"{str(err)[:160]}")
    return ok


#: The NCCS catalogue is itself served from an S3 bucket in us-east-1, and its
#: objects are readable with our own credentials even though the bucket
#: refuses a listing. That means AWS can copy them bucket to bucket without
#: the bytes ever reaching this machine -- 35 GB that does not touch the
#: author's home connection. The listing refusal is why the key list still
#: comes from the published catalogue page rather than from ListObjects.
NCCS_BUCKET = "nccsdata"


def copy_server_side(src_key: str, dst_key: str) -> tuple[bool, str]:
    def once():
        #: --copy-props none because the CLI otherwise calls
        #: GetObjectTagging on the source, which this bucket denies. Without
        #: it every copy fails AccessDenied on a file it can plainly read.
        r = run(["aws", "s3", "cp", f"s3://{NCCS_BUCKET}/{src_key}",
                 f"s3://{BUCKET}/{PREFIX}/{dst_key}",
                 "--copy-props", "none"] + PROFILE_ARGS
                + ["--only-show-errors"])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200] or "copy failed")
        return True
    ok, err = retry("copy", once)
    return ok, "" if ok else str(err)[:200]


def harvest_nccs_server_side(archived: dict[str, int], dry: bool) -> dict:
    """Bucket to bucket. Nothing is downloaded and nothing is uploaded."""
    stat = {"skipped": 0, "fetched": 0, "bytes": 0, "failed": 0,
            "truncated": 0, "kept": 0}
    items = nccs_items()
    print(f"  {len(items)} files, copied inside AWS")
    for i, (url, key) in enumerate(items, 1):
        src = url.split("amazonaws.com/", 1)[1]
        if key in archived:
            stat["skipped"] += 1
            continue
        if dry:
            stat["fetched"] += 1
            continue
        ok, err = copy_server_side(src, key)
        if ok:
            stat["fetched"] += 1
            if i % 25 == 0 or i == len(items):
                print(f"  [{i}/{len(items)}] copied", flush=True)
        else:
            stat["failed"] += 1
            print(f"  [{i}/{len(items)}] FAILED {key}: {err}", flush=True)
    return stat


def harvest(items: list[tuple[str, str]], archived: dict[str, int],
            keep_local: bool, dry: bool, refresh: bool = False) -> dict:
    stat = {"skipped": 0, "fetched": 0, "bytes": 0, "failed": 0,
            "truncated": 0, "kept": 0}
    for i, (url, key) in enumerate(items, 1):
        local = LOCAL / key
        want = remote_size(url)
        have = archived.get(key)

        if have is not None and want is not None and have >= want:
            #: Already archived at full size. The >= rather than == is
            #: deliberate: a later release that GREW is still a valid archive
            #: of this key, and re-uploading a smaller one would be the
            #: shrinking this repo's rules forbid.
            stat["skipped"] += 1
            continue
        if have is not None and want is None and not refresh:
            #: Archived, and the server will not say how big it should be --
            #: irs.gov serves the Business Master File chunked, with no
            #: content-length. Without this the file is re-downloaded on
            #: every run and the job stops being resumable, which on a 62 GB
            #: harvest is the difference between finishing and not. Use
            #: --refresh to pull it again; the BMF is a monthly snapshot and
            #: does want re-fetching, just not twice in one run.
            stat["skipped"] += 1
            continue
        if dry:
            print(f"  [{i}/{len(items)}] would fetch {key} "
                  f"({human(want) if want else 'size unknown'})")
            stat["fetched"] += 1
            stat["bytes"] += want or 0
            continue

        print(f"  [{i}/{len(items)}] {key} "
              f"({human(want) if want else 'size unknown'}) ", end="", flush=True)
        ok, got = retry("download", lambda: fetch(url, local))
        if not ok:
            print(f"FAILED after {ATTEMPTS} attempts: "
                  f"{type(got).__name__}")
            local.with_suffix(local.suffix + ".part").unlink(missing_ok=True)
            stat["failed"] += 1
            continue

        if want is not None and got < want:
            #: The 2026-08 incident's signature. A short file is a truncated
            #: download, never a smaller release, and it must not reach S3.
            print(f"TRUNCATED {human(got)} of {human(want)} -- discarded")
            local.unlink(missing_ok=True)
            stat["truncated"] += 1
            continue
        if have is not None and got < have:
            print(f"SMALLER than the archived copy ({human(got)} < "
                  f"{human(have)}) -- S3 keeps the good copy")
            local.unlink(missing_ok=True)
            stat["truncated"] += 1
            continue

        if not upload(local, key):
            stat["failed"] += 1
            local.unlink(missing_ok=True)
            continue

        stat["fetched"] += 1
        stat["bytes"] += got
        if keep_local:
            stat["kept"] += 1
            print(f"ok, kept locally")
        else:
            local.unlink(missing_ok=True)
            print("ok, archived")
    return stat


def irs_xml_items() -> list[tuple[str, str]]:
    with urllib.request.urlopen(
            urllib.request.Request(IRS_990_INDEX, headers=UA), timeout=120) as r:
        html = r.read().decode("utf-8", "replace")
    urls = sorted(set(re.findall(
        r'https://apps\.irs\.gov/pub/epostcard/990/xml/[^"\']+\.(?:zip|csv)', html)))
    if not urls:
        raise SystemExit(
            "no e-file XML links found on the IRS downloads page. The page "
            "layout changed; fix the pattern rather than shipping an empty "
            "harvest.")
    return [(u, "irs_efile_xml/" + "/".join(u.split("/")[-2:])) for u in urls]


def nccs_items() -> list[tuple[str, str]]:
    with urllib.request.urlopen(
            urllib.request.Request(NCCS_INDEX, headers=UA), timeout=120) as r:
        html = r.read().decode("utf-8", "replace")
    urls = sorted(set(re.findall(
        r'https://nccsdata\.s3[^"\']+\.(?:csv|parquet)', html)))
    if not urls:
        raise SystemExit(
            "no NCCS links found in the catalogue. The page layout changed.")
    out = []
    for u in urls:
        tail = u.split("amazonaws.com/", 1)[1]
        out.append((u, "nccs/" + tail))
    return out


GROUPS = {
    "irs_bulk": ("IRS bulk extracts: Business Master File, Publication 78, "
                 "auto-revocation, e-Postcard",
                 lambda: [(u, "irs_bulk/" + n) for u, n in IRS_BULK]),
    "irs_efile_xml": ("IRS Form 990 e-file XML, 2019 onward", irs_xml_items),
    "nccs": ("NCCS Core and harmonized panel, 1987 onward", nccs_items),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group", action="append", choices=sorted(GROUPS),
                    help="limit to one group; repeatable")
    ap.add_argument("--list", action="store_true",
                    help="say what would be fetched and stop")
    ap.add_argument("--keep-local", action="store_true",
                    help="keep every file on disk, not only the small ones")
    ap.add_argument("--via-wifi", action="store_true",
                    help="force NCCS through this machine instead of "
                         "copying it bucket to bucket inside AWS")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch files whose size the server will not "
                         "state, such as the monthly Business Master File")
    ap.add_argument("--restore", metavar="PREFIX",
                    help="pull a prefix back from S3 into data/irs990/")
    args = ap.parse_args()

    if args.restore:
        key = args.restore.strip("/")
        dest = LOCAL / key
        dest.mkdir(parents=True, exist_ok=True)
        print(f"restoring {PREFIX}/{key} -> {dest}")
        r = subprocess.run(["aws", "s3", "sync",
                            f"s3://{BUCKET}/{PREFIX}/{key}/", str(dest)]
                           + PROFILE_ARGS)
        return r.returncode

    groups = args.group or list(GROUPS)
    archived = {} if args.list else s3_sizes()
    if archived:
        print(f"{len(archived)} objects already archived under {PREFIX}/\n")

    totals = {"skipped": 0, "fetched": 0, "bytes": 0, "failed": 0,
              "truncated": 0, "kept": 0}
    t0 = time.time()
    for g in groups:
        label, resolver = GROUPS[g]
        print(f"=== {g}: {label}")
        if g == "nccs" and not args.via_wifi:
            st = harvest_nccs_server_side(archived, args.list)
            for k in totals:
                totals[k] += st[k]
            print()
            continue
        items = resolver()
        print(f"  {len(items)} files")
        keep = args.keep_local or any(g.startswith(k.rstrip("/"))
                                      for k in KEEP_LOCAL)
        st = harvest(items, archived, keep, args.list, args.refresh)
        for k in totals:
            totals[k] += st[k]
        print()

    mins = (time.time() - t0) / 60
    verb = "would fetch" if args.list else "fetched"
    print(f"{verb} {totals['fetched']} files, {human(totals['bytes'])}; "
          f"{totals['skipped']} already archived; {totals['kept']} kept on "
          f"disk; {totals['failed']} failed; {totals['truncated']} truncated "
          f"and discarded  [{mins:.1f} min]")
    if totals["failed"]:
        print(f"  Re-run to retry the {totals['failed']} that failed; "
              f"anything already archived is skipped.")
    if not args.list:
        print(f"\nRestore any of it with:\n"
              f"  python3 scripts/fetch_irs990.py --restore nccs/harmonized\n"
              f"  aws s3 sync s3://{BUCKET}/{PREFIX}/ data/irs990/ "
              f"--profile {PROFILE}")
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
