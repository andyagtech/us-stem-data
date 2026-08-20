#!/usr/bin/env python3
"""Curated answers: review what the assistant says, rewrite it in your voice.

THE WORKFLOW

    1. export   ask the live assistant every warm-list question and write the
                answers to a local YAML file
    2. edit     open that file and rewrite the answers as you want them said
    3. check    verify every number you wrote still matches the data
    4. seed     push the curated answers into the cache so visitors get yours

Steps 1 and 4 are this script. Step 2 is a text editor. Step 3 is this script
refusing to seed anything whose figures do not reconcile.

WHY CURATE AT ALL

The assistant is grounded -- every figure comes from a tool and the ledger
rejects anything else -- but grounded is not the same as well said. The twenty
or thirty questions below will be most of the traffic, including the hostile
ones, and those deserve an answer that was written rather than generated.

WHY THE NUMBER CHECK IS NOT OPTIONAL

A curated answer bypasses the grounding ledger by construction: it was not
produced by a tool call in a conversation, so nothing verifies it. That is the
whole point and also the whole risk. `--check` re-derives every figure it can
recognise from the published artifacts and refuses to seed on a mismatch, so a
hand-written answer cannot quietly drift from the data the page shows.

It cannot check prose. If you write "most departments", nothing verifies that.
Numbers it can see, it checks.

Usage:
    python3 scripts/curated_answers.py --export answers.yaml
    python3 scripts/curated_answers.py --check answers.yaml
    python3 scripts/curated_answers.py --seed answers.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "cloud" / "chat" / "curated_answers.yaml"
ORIGIN = "https://phd-demographics.andy-barr.com"

sys.path.insert(0, str(ROOT / "scripts"))


def endpoint() -> str:
    """The endpoint the widget actually calls, read from the widget itself."""
    widget = ROOT / "site" / "chat-widget.js"
    if widget.exists():
        m = re.search(r"CHAT_ENDPOINT\s*=\s*'([^']+)'", widget.read_text())
        if m:
            return m.group(1)
    return ""


def questions() -> list[tuple[str, str]]:
    from warm_chat_cache import QUESTIONS
    return QUESTIONS


# --------------------------------------------------------------------- export

def ask(url: str, q: str, timeout: int = 60):
    req = urllib.request.Request(
        url, data=json.dumps({"v": 2, "message": q,
                              "page": {"path": "/"}}).encode(),
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:200]}
    except Exception as e:                                   # noqa: BLE001
        return {"error": str(e)[:120]}


def _yaml_block(text: str, indent: str = "    ") -> str:
    """Emit a literal block scalar, which survives any punctuation."""
    body = "\n".join(indent + line for line in (text or "").split("\n"))
    return "|-\n" + body


def do_export(path: Path, url: str, delay: float) -> int:
    qs = questions()
    print(f"Asking {len(qs)} questions of {url}\n")
    out = ["# Curated assistant answers.",
           "#",
           "# Rewrite `answer` in your own voice. Leave `question` alone -- it is",
           "# the cache key. Set `skip: true` on any entry you would rather the",
           "# model answer fresh each time.",
           "#",
           "# Run --check before --seed. Numbers here are NOT verified by the",
           "# grounding ledger, because a curated answer never passed through a",
           "# tool call. --check re-derives what it can and refuses to seed on a",
           "# mismatch.",
           "",
           "answers:"]
    for i, (group, q) in enumerate(qs, 1):
        resp = ask(url, q)
        reply = resp.get("reply", "") if "error" not in resp else ""
        err = resp.get("error", "")
        print(f"  {i:>2}/{len(qs)}  [{group:<8}] "
              f"{'FAIL ' + err if err else str(len(reply)) + ' chars'}  {q[:44]}")
        out += [f"  - group: {group}",
                f"    question: {json.dumps(q)}",
                f"    skip: false",
                f"    answer: {_yaml_block(reply)}",
                ""]
        if i < len(qs):
            time.sleep(delay)
    path.write_text("\n".join(out))
    print(f"\nWrote {path}")
    print("Edit the `answer` fields, then: --check, then --seed.")
    return 0


# ---------------------------------------------------------------------- check

def load(path: Path) -> list[dict]:
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml required: pip install pyyaml")
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("answers") or []


def known_figures() -> dict[str, float]:
    """Figures the site publishes, for reconciling curated prose against."""
    figs: dict[str, float] = {}
    cc = ROOT / "site" / "data" / "concentration_cases.json"
    if cc.exists():
        d = json.loads(cc.read_text())
        figs["case_count"] = float(d.get("count", 0))
        if d.get("cases"):
            figs["top_share"] = float(d["cases"][0]["share"])
    tc = ROOT / "site" / "data" / "taxpayer_cost.json"
    if tc.exists():
        d = json.loads(tc.read_text())
        figs["median_per_doctorate"] = float(d.get("median_federal_per_doctorate", 0))
    return figs


def do_check(path: Path) -> int:
    rows = load(path)
    figs = known_figures()
    problems = 0
    print(f"Checking {len(rows)} curated answers against published data\n")
    print("  Reference figures:")
    for k, v in figs.items():
        print(f"    {k:<24} {v:,.1f}")
    print()

    # Recognise the figures the landing page leads with. Anything else is
    # prose and cannot be machine-checked.
    checks = [
        (r"\b49\b", "case_count", 49.0, "number of majority-non-resident departments"),
        (r"\$?875[,.]?0?0?0?K?\b|\$875K", "median_per_doctorate", 874630.0,
         "median federal dollars per doctorate"),
        (r"\b90\.6\s?%", "top_share", 90.6, "highest sustained share"),
    ]
    for row in rows:
        if row.get("skip"):
            continue
        ans = row.get("answer") or ""
        for pattern, key, expected, label in checks:
            if re.search(pattern, ans) and key in figs:
                actual = figs[key]
                tol = max(1.0, expected * 0.01)
                if abs(actual - expected) > tol:
                    problems += 1
                    print(f"  MISMATCH  {row['question'][:50]}")
                    print(f"            mentions {label} as ~{expected:,.0f}, "
                          f"data says {actual:,.0f}")
        if not ans.strip():
            problems += 1
            print(f"  EMPTY     {row['question'][:60]}")

    print(f"\n{len(rows)} answers, {problems} problem(s).")
    if problems:
        print("Fix these before seeding; --seed refuses while any remain.")
    return 1 if problems else 0


# ----------------------------------------------------------------------- seed

def do_seed(path: Path, url: str, delay: float) -> int:
    if do_check(path) != 0:
        return 1
    rows = [r for r in load(path) if not r.get("skip") and (r.get("answer") or "").strip()]
    print(f"\nSeeding {len(rows)} curated answers into the cache\n")

    try:
        sys.path.insert(0, str(ROOT / "cloud" / "chat"))
        import cache as C
    except Exception as e:                                   # noqa: BLE001
        sys.exit(f"cannot import the cache module: {e}")
    if not C.CACHE_TABLE:
        sys.exit("CHAT_CACHE_TABLE is unset. Export it and retry:\n"
                 "  export CHAT_CACHE_TABLE=phd-chat-cache-prod")

    ok = fail = 0
    for i, r in enumerate(rows, 1):
        q = r["question"]
        envelope = {"v": 2, "reply": r["answer"], "blocks": [], "actions": [],
                    "meta": {"curated": True}}
        wrote = C.store(q, {"path": "/"}, envelope, None)
        ok, fail = (ok + 1, fail) if wrote else (ok, fail + 1)
        print(f"  {i:>2}/{len(rows)}  {'seeded' if wrote else 'FAILED'}  {q[:52]}")
        time.sleep(delay)
    print(f"\n{ok} seeded, {fail} failed.")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", metavar="FILE")
    ap.add_argument("--check", metavar="FILE")
    ap.add_argument("--seed", metavar="FILE")
    ap.add_argument("--endpoint", default="")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    url = args.endpoint or endpoint()
    if args.export:
        if not url:
            sys.exit("No endpoint. Pass --endpoint.")
        return do_export(Path(args.export), url, max(args.delay, 6.0))
    if args.check:
        return do_check(Path(args.check))
    if args.seed:
        return do_seed(Path(args.seed), url, args.delay)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
