#!/usr/bin/env python3
"""The public-sector PERM data, slimmed for the assistant's bundle.

WHY A SEPARATE EXPORT

The published file is 18 MB because it carries all 38,705 records. The Lambda
does not need them: the assistant answers with totals, per-state cuts and the
87 state-agency filings, which together come to about 240 KB. Shipping the
whole file would be most of the bundle for data no tool reads.

WHAT IS KEPT, AND WHY EACH PIECE

  sectors, distributions   the national shape, for "how big is this"
  by_state_detail          every state's own figures, because the assistant
                           was asked about Washington and answered with the
                           national total -- 87 filings, when Washington has
                           six. A tool that can fetch the state is the fix.
  anomaly_totals           how many rows each test flagged
  caveats, window, source  so an answer can carry its own limits

What is dropped: `records` (all 38,705) and `anomalies` (the capped display
lists). Both are reachable on the page, which the assistant links to.

Usage:
    python3 scripts/build_chat_public_sector.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site" / "data" / "public_employer_perm.json"
OUT = ROOT / "cloud" / "chat" / "chat_data" / "public_employer_perm_compact.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402

DROP = ("records", "anomalies")


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC.relative_to(ROOT)} is missing. "
              f"Run scripts/build_public_employer_perm.py first.")
        return 1
    d = json.loads(SRC.read_text())
    slim = {k: v for k, v in d.items() if k not in DROP}

    #: Fail rather than ship a file whose state cut is missing, because the
    #: tool that reads it would then answer every state question with a
    #: national figure -- which is the exact failure this export exists to fix.
    if not slim.get("by_state_detail"):
        print("ERROR: by_state_detail is absent from the source. The assistant "
              "would answer state questions with the national total.")
        return 1

    agency = sum(len(v.get("agency_filings") or [])
                 for v in slim["by_state_detail"].values())
    write_text(OUT, json.dumps(slim, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}: {len(slim['by_state_detail'])} states, "
          f"{agency} state-agency filings, {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
