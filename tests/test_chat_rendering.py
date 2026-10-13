#!/usr/bin/env python3
"""What the assistant may put on screen, and what the panel actually renders.

Three markers used to fall through the widget's markdown parser and come out
as run-on text: `*` bullets, `1.` numbered lists, and pipe tables. The `*`
case was the worst, because the inline italic rule then matched across the
whole line and set the list in italics.

The column cap is the other half. The panel is 420px wide; an eight-column
table scrolled sideways and the measure the prose cited was often off-screen.

See cloud/chat/RENDERING.md.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WIDGET = ROOT / "site" / "chat-widget.js"

sys.path.insert(0, str(ROOT / "cloud"))
from chat import blocks as B                                        # noqa: E402


# --------------------------------------------------------------------------
# Server side: the cap is enforced where the block is built.
# --------------------------------------------------------------------------

class _Ledger:
    def check(self, numbers, where):          # every number here is allowed
        return None

    def note_source(self, src):
        return None


class _Ctx:
    ledger = _Ledger()
    site_map = {"pages": []}


def _table(n_cols):
    cols = [{"key": f"c{i}", "label": f"Col {i}", "format": "text"} for i in range(n_cols)]
    rows = [{f"c{i}": "x" for i in range(n_cols)}]
    return {"columns": cols, "rows": rows, "source": "test"}


def test_three_columns_is_the_cap():
    assert B.MAX_COLUMNS == 3


def test_three_columns_builds():
    block = B.build_table(_table(3), _Ctx())
    assert len(block["columns"]) == 3


def test_a_fourth_column_is_trimmed_and_the_note_says_so():
    """Rejecting it was tried on 2026-10-13 against the live assistant. The
    model answered a rejected show_table by writing a pipe table in the prose
    and dropping its follow-up chips: no table block at all. A trimmed table
    that names the missing column is the better failure."""
    block = B.build_table(_table(4), _Ctx())
    assert len(block["columns"]) == 3
    assert "4 columns sent, 3 shown" in block["note"]
    assert "Col 3" in block["note"]


def test_the_authors_own_note_survives_the_trim():
    args = _table(4)
    args["note"] = "Cohorts under 10 excluded."
    block = B.build_table(args, _Ctx())
    assert block["note"].startswith("Cohorts under 10 excluded.")
    assert "3 shown" in block["note"]


def test_the_tool_schema_says_three():
    from chat import tools
    spec = next(f for f in tools.TOOLS
                if f.get("function", f).get("name") == "show_table")
    cols = spec.get("function", spec)["parameters"]["properties"]["columns"]
    assert "1-3 columns" in cols["description"]
    assert "1-8" not in json.dumps(spec)
    # Prose alone did not hold it: the live model sent four columns anyway on
    # 2026-10-13 and lost the NRA share off the end. maxItems is the lever
    # that actually binds a function-calling model.
    assert cols["maxItems"] == B.MAX_COLUMNS


# --------------------------------------------------------------------------
# The prompt has to ask for the shape we render well.
# --------------------------------------------------------------------------

def test_the_prompt_states_the_bullet_preference():
    from chat import prompt
    body = prompt.SYSTEM if isinstance(getattr(prompt, "SYSTEM", None), str) else \
        Path(prompt.__file__).read_text()
    assert "Prefer a bulleted list" in body


def test_the_prompt_forbids_a_table_written_in_prose():
    body = Path(ROOT / "cloud" / "chat" / "prompt.py").read_text()
    assert "Never write a table in prose" in body
    assert "THREE columns" in body


# --------------------------------------------------------------------------
# Client side: run the widget's own parser under node.
# --------------------------------------------------------------------------

pytestmark_node = pytest.mark.skipif(
    shutil.which("node") is None or not WIDGET.exists(),
    reason="needs node and site/chat-widget.js (the site lives in the private repo)",
)


def _parse(md: str):
    """Lift parseMdBlocks out of the widget and run it on `md`."""
    src = WIDGET.read_text()
    start = src.index("  var BULLET_RE")
    marker = "    flushPara(); flushList();\n    return out;\n  }\n"
    end = src.index(marker, start) + len(marker)
    harness = src[start:end] + textwrap.dedent("""
        console.log(JSON.stringify(parseMdBlocks(process.env.MD_IN)));
    """)
    out = subprocess.run(["node", "-e", harness], capture_output=True, text=True,
                         check=True, env={**os.environ, "MD_IN": md})
    return json.loads(out.stdout)


@pytestmark_node
def test_star_bullets_are_a_list_and_not_italic_prose():
    assert _parse("* One\n* Two") == [
        {"t": "list", "ordered": False, "items": [{"text": "One"}, {"text": "Two"}]}]


@pytestmark_node
def test_dash_bullets_still_work():
    assert _parse("- One\n- Two")[0]["t"] == "list"


@pytestmark_node
def test_numbered_lists_are_ordered():
    got = _parse("1. First\n2. Second")[0]
    assert got["ordered"] is True and len(got["items"]) == 2


@pytestmark_node
def test_one_level_of_nesting_survives():
    got = _parse("- Top\n  - Child\n- Next")[0]
    assert got["items"][0]["children"] == ["Child"]
    assert len(got["items"]) == 2


@pytestmark_node
def test_a_pipe_table_becomes_a_table_not_a_paragraph():
    got = _parse("| Lab | Share |\n| --- | --- |\n| NLP | 88% |")
    assert got == [{"t": "mdtable", "head": ["Lab", "Share"], "rows": [["NLP", "88%"]]}]


@pytestmark_node
def test_prose_that_merely_contains_a_star_is_left_alone():
    """`*emphasis*` and `3*4` must not start a list."""
    got = _parse("This *matters* and 3*4 is 12")
    assert got[0]["t"] == "p"


@pytestmark_node
def test_a_rule_with_no_header_is_dropped_not_printed():
    got = _parse("Some prose\n---\nmore prose")
    assert all("---" not in b.get("text", "") for b in got), got


@pytestmark_node
def test_the_widget_caps_columns_at_three_too():
    src = WIDGET.read_text()
    assert "tableColumns: 3," in src


@pytestmark_node
def test_cells_clip_rather_than_scroll_sideways():
    """table-layout:fixed plus an ellipsis. Without the fixed layout one long
    institution name widens its column past the panel."""
    src = WIDGET.read_text()
    assert "table-layout:fixed" in src
    assert "text-overflow:ellipsis" in src
