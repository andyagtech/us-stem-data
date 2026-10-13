#!/usr/bin/env python3
"""Every answer ends with somewhere to go next.

The prompt has said ALWAYS call suggest_followups since the block protocol
shipped. On 2026-10-13 three live answers in five came back with no chips at
all, one of them with no blocks but prose. The instruction was already
unconditional, so asking harder is not a fix. The assembler fills them in.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from chat import blocks as B                                        # noqa: E402
from chat import followups as F                                     # noqa: E402


def _suggest(blocks):
    return next((b for b in blocks if b["type"] == "suggest"), None)


# --- the bank --------------------------------------------------------------

def test_a_turn_that_used_no_tool_still_gets_chips():
    items = F.fallback([], "")
    assert len(items) >= F.MIN_ITEMS
    assert all(i["label"] and i["prompt"] for i in items)


def test_the_chips_follow_the_tool_the_turn_used():
    items = F.fallback(["field_extremes"], "")
    assert any("lowest" in i["prompt"].lower() for i in items)


def test_the_page_fills_what_the_tools_do_not():
    items = F.fallback([], "/labs.html")
    assert any("lab" in i["prompt"].lower() for i in items)


def test_never_more_than_three():
    items = F.fallback(["field_extremes", "caveats_for", "wages_for",
                        "by_state", "pipeline_for"], "/stem.html")
    assert len(items) <= F.MAX_ITEMS


def test_no_duplicate_prompts():
    items = F.fallback(["nra_lookup", "nra_lookup", "cip_search"], "/stem.html")
    prompts = [i["prompt"] for i in items]
    assert len(prompts) == len(set(prompts))


def test_an_unknown_tool_name_does_not_break_it():
    assert F.fallback(["no_such_tool"], "/nowhere.html")


def test_every_chip_fits_the_block_limits():
    """build_suggest truncates at 40 and 160 chars. A chip that renders
    half-written is worse than none."""
    for tool, pairs in F.BY_TOOL.items():
        for label, prompt in pairs:
            assert len(label) <= 40, (tool, label)
            assert len(prompt) <= 160, (tool, prompt)
            assert prompt.endswith(("?", ".")), (tool, prompt)


# --- the assembler ---------------------------------------------------------

def test_the_model_block_wins_when_it_sent_one():
    """It saw the answer and can be specific. The fallback is a floor."""
    sent = {"type": "suggest", "items": [{"label": "Its labs",
                                          "prompt": "Show me its labs."}]}
    blocks, _ = B.assemble([sent], "prose",
                           fallback_suggest=[{"label": "X", "prompt": "Y?"}])
    assert _suggest(blocks)["items"][0]["label"] == "Its labs"
    assert "generated" not in _suggest(blocks)


def test_the_fallback_fires_when_it_sent_none():
    blocks, _ = B.assemble([], "prose",
                           fallback_suggest=F.fallback(["field_extremes"], ""))
    sug = _suggest(blocks)
    assert sug is not None and sug["generated"] is True
    assert len(sug["items"]) >= F.MIN_ITEMS


def test_the_chips_are_still_the_last_block():
    """Contract 4.5.9 pins suggest last, and the block cap must not eat it."""
    noise = [{"type": "notice", "kind": "info", "md": f"n{i}",
              "placement": "after_text"} for i in range(12)]
    blocks, truncated = B.assemble(noise, "prose",
                                   fallback_suggest=F.fallback(["by_state"], ""))
    assert blocks[-1]["type"] == "suggest"
    assert truncated


def test_no_fallback_means_no_block():
    blocks, _ = B.assemble([], "prose", fallback_suggest=[])
    assert _suggest(blocks) is None


def test_malformed_fallback_items_are_dropped():
    blocks, _ = B.assemble([], "prose", fallback_suggest=[
        {"label": "ok", "prompt": "Fine?"}, {"label": "no prompt"}, "nonsense"])
    assert len(_suggest(blocks)["items"]) == 1
