"""Follow-up chips the server can always produce.

The prompt has said ALWAYS finish with `suggest_followups` since the block
protocol shipped. The model does not always do it: on 2026-10-13, three live
answers out of five came back with no chips at all, including one where the
only block was prose. Asking harder is not a fix -- the instruction was
already unconditional.

So the chips are guaranteed here instead. If the model sends a suggest block,
that one wins: it saw the answer and can be specific. If it sends none, the
assembler fills one from this bank, keyed on the data tools the turn actually
used. Both paths cost nothing extra -- no model call, no round trip.

A chip is a real next question, not a restatement of the answer. It has to be
answerable by a tool this assistant has, or it sends the reader into a dead
end, so each one below was written against a specific tool's output.
"""
from __future__ import annotations

# Keyed by data tool. The first tool a turn used is the one closest to what
# the reader asked, so it leads.
BY_TOOL: dict[str, list[tuple[str, str]]] = {
    "nra_lookup": [
        ("The trend", "How has that share moved over the last ten years?"),
        ("Compare", "How does that compare with the national average?"),
    ],
    "cip_search": [
        ("Who awards it", "Which universities award the most doctorates in that field?"),
        ("The extremes", "Which programmes in that field lean hardest on foreign students?"),
    ],
    "field_extremes": [
        ("The other end", "Which programmes in that field have the lowest foreign share?"),
        ("Over time", "How has that share moved since 2015?"),
        ("Who funds it", "What federal funding goes to those programmes?"),
    ],
    "get_national_series": [
        ("What changed", "What happened around the inflection in that series?"),
        ("By field", "Which fields drove that movement?"),
    ],
    "get_university_facts": [
        ("Its departments", "Which departments there have the highest foreign share?"),
        ("Where they go", "Where do that university's graduates work afterwards?"),
    ],
    "compare_institutions": [
        ("Add one", "How does the national average compare with those?"),
        ("By field", "Does that gap hold in a single field?"),
    ],
    "pipeline_for": [
        ("The wages", "What wages are these workers paid?"),
        ("The queue", "How long is the green card queue for them?"),
    ],
    "wages_for": [
        ("Against local pay", "How does that compare with the local prevailing wage?"),
        ("Who files", "Which employers file the most at that level?"),
    ],
    "funding_per_doctorate": [
        ("Who pays", "Which federal agencies fund that work?"),
        ("Per state", "How does that differ by state?"),
    ],
    "training_grants": [
        ("The recipients", "Which institutions hold the most of those grants?"),
    ],
    "by_state": [
        ("The outliers", "Which states are furthest from the national average?"),
        ("Against funding", "How does state funding track that?"),
    ],
    "state_funding_vs_output": [
        ("The outliers", "Which states get the least output per dollar?"),
    ],
    "find_departments": [
        ("The roster", "Are any of those departments' labs almost entirely foreign?"),
        ("The records", "Show me the underlying dissertation records."),
    ],
    "search_records": [
        ("Narrow it", "Can you narrow that to the last five years?"),
    ],
    "similar_to": [
        ("What differs", "What separates those from the one I asked about?"),
    ],
    "coverage_for": [
        ("The gaps", "What is missing from that coverage?"),
    ],
    "caveats_for": [
        ("The sources", "Which federal files is that built from?"),
    ],
    "level_rankings": [
        ("The other levels", "How does that look at the other wage levels?"),
    ],
    "completions_breakdown": [
        ("The trend", "How has that breakdown changed over time?"),
    ],
    "nra_distribution": [
        ("The tail", "Which programmes sit in the top of that distribution?"),
    ],
    "public_sector_overview": [
        ("By state", "How does that break down by state?"),
    ],
    "public_sector_by_state": [
        ("The national picture", "How does that compare with the national total?"),
    ],
    "key_figures": [
        ("The argument", "What is the case this site is making?"),
    ],
    "list_universities": [
        ("The extremes", "Which of those has the highest foreign share?"),
    ],
}

# Where the reader already is. Used after the tool bank, and only to fill.
BY_PAGE: dict[str, list[tuple[str, str]]] = {
    "/departments-stem.html": [("Lowest fields", "Which STEM fields have the lowest foreign share?")],
    "/labs.html": [("The method", "How is a lab's composition measured?")],
    "/bodyshops.html": [("The wages", "What do the biggest filers pay?")],
    "/pipeline.html": [("The queue", "How long is the employment-based green card queue?")],
    "/query.html": [("An example", "Show me a query I can run against the records.")],
}

# Last resort. These are answerable from the knowledge base alone, so they
# work even on a turn that used no data tool at all.
UNIVERSAL: list[tuple[str, str]] = [
    ("The finding", "What is the central finding of this site?"),
    ("The sources", "Which federal datasets is this built from?"),
    ("The limits", "What can this data not tell me?"),
]

MIN_ITEMS = 2
MAX_ITEMS = 3


def fallback(tools_used, page_path: str = "") -> list[dict]:
    """Chips for a turn whose model forgot to ask for any.

    Returns 2-3 items shaped like `suggest_followups` would have sent them.
    Never empty: UNIVERSAL always has enough.
    """
    out: list[dict] = []
    seen: set[str] = set()

    def take(pairs):
        for label, prompt in pairs:
            if len(out) >= MAX_ITEMS or prompt in seen:
                continue
            seen.add(prompt)
            out.append({"label": label, "prompt": prompt})

    for name in (tools_used or []):
        take(BY_TOOL.get(name, ()))
        if len(out) >= MAX_ITEMS:
            break
    if len(out) < MAX_ITEMS:
        take(BY_PAGE.get(page_path or "", ()))
    if len(out) < MIN_ITEMS:
        take(UNIVERSAL)
    return out[:MAX_ITEMS]
