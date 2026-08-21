#!/usr/bin/env python3
"""Assert what the deployed assistant SAYS, not just what it serves.

WHY THIS EXISTS. Every other check in this project verifies an artifact -- a
file, a page, a JSON payload. scripts/test_site.py makes 121 assertions and
scripts/check_consistency.py another 7, and not one of them could observe the
assistant's answers. So this shipped to production:

    Q: which university has the highest non-resident share at master's level?
    A: Missouri S&T, 74.3%            <- a DOCTORATE figure, 2015-2022
    correct: New England College, 98.5%

The number was real. It answered a different question. No artifact was wrong,
so no artifact check failed. The assistant is the surface that generates novel
text and it had the least verification of anything here.

Each case below states the question, what must appear, and what must NOT. The
must-not list is the important half: it is how a doctorate figure quoted as a
master's figure gets caught, and a bare percentage without its denominator.

This calls the live endpoint with fresh=true so the semantic cache cannot serve
a stale correct answer over a broken tool path.

Usage:
    python3 scripts/test_chat_answers.py
    python3 scripts/test_chat_answers.py --endpoint https://...
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = ("https://lamsi2swef2o2ark2ylnupz5wy0vedcw.lambda-url."
            "us-east-1.on.aws/")

# (question, page, must_contain_any_of_each_group, must_not_contain)
CASES = [
    (
        "Which university has the highest non-resident share at masters level?",
        "/rankings.html",
        [["New England College"], ["98.5"], ["2,563", "2563"]],
        ["Missouri S&T", "74.3"],
    ),
    (
        "Which university has the highest non-resident share at doctorate level?",
        "/rankings.html",
        [["Lamar"], ["88.9"], ["63"]],
        ["New England College", "98.5"],
    ),
    (
        "What is the non-resident share of core-STEM masters degrees nationally?",
        "/expansion.html",
        [["40.2"]],
        ["38.8"],                       # the doctorate national share
    ),
    (
        # Assert BEHAVIOUR, not vocabulary. An earlier version of this case
        # demanded the words "degrees conferred" and "not individuals"; the
        # model expresses the same refusal a dozen different ways and the test
        # failed on a correct answer. What must never happen is a combined
        # total appearing, so the forbidden list carries the actual sums.
        "How many non-resident graduate students are there in total if you add "
        "the masters and doctorate numbers together?",
        "/expansion.html",
        [["cannot", "can't", "do not support", "does not", "not support",
          "separately", "not yield", "would be counted twice"]],
        ["550,836", "550836", "147,789", "147789", "147,768"],
    ),
    (
        "What is the masters expansion worth in tuition?",
        "/expansion.html",
        [["3.36", "3.4"], ["sticker", "estimate", "published"]],
        ["federal money is", "taxpayers paid"],
    ),
    (
        "Are American students being displaced?",
        "/",
        [["not", "does not", "cannot"]],
        [],
    ),
]


class RateLimited(Exception):
    """The endpoint refused us, not a wrong answer."""


def ask(endpoint: str, message: str, page: str, timeout: int = 90) -> str:
    body = json.dumps({"v": 2, "message": message, "page": page,
                       "fresh": True}).encode()
    req = urllib.request.Request(endpoint, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimited(exc.headers.get("Retry-After") or "60") from exc
        raise
    # A 200 can still carry an error envelope.
    if isinstance(payload, dict) and payload.get("error") == "rate_limited":
        raise RateLimited(str(payload.get("retry_after_s") or 60))
    return str(payload.get("reply") or payload.get("message") or "")


def ask_with_backoff(endpoint: str, message: str, page: str,
                     attempts: int = 4) -> str:
    """Retry through rate limiting rather than reporting it as a wrong answer.

    Running this suite twice in quick succession produced 1/6 once, and every
    'failure' was the rate limiter. A behavioural test that cries wolf gets
    muted, and a muted test protects nothing -- so a refusal must be waited
    out, and only a real answer is ever judged.
    """
    delay = 20
    for attempt in range(attempts):
        try:
            return ask(endpoint, message, page)
        except RateLimited as exc:
            if attempt == attempts - 1:
                raise
            try:
                wait = max(int(float(str(exc))), delay)
            except ValueError:
                wait = delay
            print(f"        rate limited, waiting {wait}s "
                  f"(attempt {attempt + 1}/{attempts})", flush=True)
            time.sleep(wait)
            delay *= 2
    raise RateLimited("exhausted")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", default=ENDPOINT)
    args = ap.parse_args()

    failures = 0
    for question, page, required, forbidden in CASES:
        label = question[:58] + ("..." if len(question) > 58 else "")
        try:
            answer = ask_with_backoff(args.endpoint, question, page)
        except RateLimited as exc:
            print(f"  ERROR {label}\n        still rate limited after retries "
                  f"({exc}) -- not judged as a wrong answer")
            failures += 1
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"  ERROR {label}\n        {type(exc).__name__}: {exc}")
            failures += 1
            continue

        low = answer.lower()
        missing = [g for g in required
                   if not any(v.lower() in low for v in g)]
        present = [v for v in forbidden if v.lower() in low]

        if missing or present:
            failures += 1
            print(f"  FAIL  {label}")
            for g in missing:
                print(f"        missing any of: {g}")
            for v in present:
                print(f"        must not say:   {v!r}")
            print(f"        answered: {answer[:190].strip()}...")
        else:
            print(f"  pass  {label}")

    total = len(CASES)
    print(f"\n{total - failures}/{total} assistant answers correct")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
