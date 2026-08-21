"""A compact record of what the tools established, carried across a session.

THE PROBLEM

Conversation history is prose only. Charts, tables and stat blocks render in the
reader's browser and never come back, so by the next turn their values are gone.
A reader who asks "what was 2019 again?" is asking about numbers the model can
no longer see.

Worse, the model CAN see its own earlier sentences, and restating a figure from
them feels safe. It is not: the grounding ledger checks charts, tables and stat
blocks and never inspects prose, so a number carried forward that way reaches
the reader unchecked -- and if it gets rounded or paraphrased on the way, nothing
catches the drift.

WHAT THIS DOES

After each turn, the data tools that ran are distilled into a handful of short
labelled facts:

    nra_lookup(unitid=166683, 2015-2022) -> share 43.8, total 4368, nra 1913

Those travel to the browser in `meta.facts`, come back on the next request, and
are put in front of the model as established context. Two things follow:

  the model can answer a follow-up about an earlier figure without re-deriving
  it, which is what the reader expects; and

  every returned fact is re-added to the turn's ledger, so restating one is
  GROUNDED rather than remembered. A figure from three turns ago is as checkable
  as one fetched this second.

That second property is the point. This is not a convenience cache -- it extends
the grounding guarantee across turns instead of letting prose quietly escape it.

DELIBERATELY SMALL

MAX_FACTS caps what travels. The digest keeps scalar, headline-shaped values and
drops long series: a thirty-point trend is a chart, not a fact, and re-fetching
it is cheap and correct. Keeping this small also keeps the payload honest -- it
rides on every request, so it must not grow with conversation length.

Facts are scoped to the data version. A corpus rebuild makes them stale, so they
are dropped rather than carried into a world where they may no longer hold.
"""
from __future__ import annotations

import json
import re

MAX_FACTS = 12
MAX_LABEL = 90
MAX_VALUES_PER_FACT = 4

# Fields worth carrying: the headline scalars a reader refers back to.
# Ordered, because the first few are what a follow-up usually means.
INTERESTING = ("share", "pct", "percent", "nra", "total", "doctorates",
               "count", "median", "value", "rate", "federal_per_doctorate")

# Never carry these forward: identifiers and plumbing, not figures.
BORING = {"unitid", "cipcode", "cip2", "year", "years", "basis", "source",
          "key", "id", "index", "limit", "offset"}


def _scalars(obj, depth: int = 0):
    """Headline scalars from a tool result. Series are deliberately skipped."""
    out: list[tuple[str, float]] = []
    if depth > 2 or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        kl = str(k).lower()
        if kl in BORING:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            if any(t in kl for t in INTERESTING):
                out.append((str(k), float(v)))
        elif isinstance(v, dict):
            out.extend(_scalars(v, depth + 1))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            # First row only: a ranking's top entry is a fact, the tail is a table.
            out.extend(_scalars(v[0], depth + 1))
    return out


def _label(tool: str, args: dict) -> str:
    """A short human-readable stamp of what was asked."""
    bits = []
    for k in ("unitid", "university", "key", "cipcode", "cip", "field",
              "level", "year", "years", "start", "end", "state"):
        if k in args and args[k] not in (None, "", []):
            v = args[k]
            if isinstance(v, (list, tuple)):
                v = "-".join(str(x) for x in v[:2])
            bits.append(f"{k}={v}")
    return f"{tool}({', '.join(bits)})"[:MAX_LABEL] if bits else tool


def distil(tool: str, args: dict, result) -> dict | None:
    """One fact from one data-tool call, or None if it carried no figure."""
    vals = _scalars(result if isinstance(result, dict) else {})
    if not vals:
        return None
    seen, keep = set(), []
    for name, v in vals:
        if name in seen:
            continue
        seen.add(name)
        keep.append([name, round(v, 2)])
        if len(keep) >= MAX_VALUES_PER_FACT:
            break
    return {"q": _label(tool, args), "v": keep}


def merge(prior: list, new: list) -> list:
    """Newest first, de-duplicated by label, capped."""
    out, seen = [], set()
    for f in (new or []) + (prior or []):
        if not isinstance(f, dict) or "q" not in f:
            continue
        if f["q"] in seen:
            continue
        seen.add(f["q"])
        out.append(f)
        if len(out) >= MAX_FACTS:
            break
    return out


def clean(raw, version: str) -> list:
    """Validate what came back from the browser. Untrusted input."""
    if not isinstance(raw, dict):
        return []
    if str(raw.get("version") or "") != str(version):
        return []                      # stale: the data was rebuilt beneath it
    facts = raw.get("facts")
    if not isinstance(facts, list):
        return []
    out = []
    for f in facts[:MAX_FACTS]:
        if not isinstance(f, dict):
            continue
        q = str(f.get("q", ""))[:MAX_LABEL]
        vs = f.get("v")
        if not q or not isinstance(vs, list):
            continue
        vals = []
        for pair in vs[:MAX_VALUES_PER_FACT]:
            if (isinstance(pair, (list, tuple)) and len(pair) == 2
                    and isinstance(pair[1], (int, float))
                    and not isinstance(pair[1], bool)):
                vals.append([str(pair[0])[:40], float(pair[1])])
        if vals:
            out.append({"q": q, "v": vals})
    return out


def as_prompt(facts: list) -> str:
    """The block appended to the system prompt."""
    if not facts:
        return ""
    lines = ["# Figures already established in this conversation",
             "These came from data tools on earlier turns and are recorded in "
             "this turn's ledger, so you may quote them directly. Anything NOT "
             "listed here still has to be fetched.",
             ""]
    for f in facts:
        vals = ", ".join(f"{n} {v:g}" for n, v in f["v"])
        lines.append(f"  {f['q']} -> {vals}")
    return "\n".join(lines)


def replay_into_ledger(facts: list, ledger) -> None:
    """Re-ground earlier figures so restating one is checked, not remembered."""
    for f in facts or []:
        for _name, v in f.get("v", []):
            try:
                ledger.add(float(v))
            except (TypeError, ValueError):
                continue
