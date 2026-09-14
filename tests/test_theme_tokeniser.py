#!/usr/bin/env python3
"""The deploy-time pass that swaps hard-coded colours for the page's tokens.

It runs on every page at every deploy and nobody reads its output, so a fault
in it ships silently. One did: a semicolon inside a CSS comment let it rewrite
a token's own definition into `--spend-bar: var(--spend-bar)`, a cycle the
browser discards, and the analytics dashboard's spend chart went invisible in
dark mode on the live site. These tests pin the three rules it must keep.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from add_theme_toggle import tokenise_literals                      # noqa: E402


def page(css: str) -> str:
    return (":root { --accent:#0284c7; --warn:#d97706; }\n" + css)


def styled(css: str) -> str:
    return f"<html><head><style>{page(css)}</style></head><body></body></html>"


def test_a_literal_in_a_rule_becomes_the_token():
    out, n = tokenise_literals(styled(".x { color:#0284c7; }"))
    assert ".x { color:var(--accent); }" in out and n == 1


def test_a_token_definition_is_never_rewritten_into_itself():
    out, _ = tokenise_literals(styled(""))
    assert "--accent:#0284c7" in out
    assert "var(--accent)" not in out


def test_a_semicolon_inside_a_comment_does_not_expose_a_definition():
    """The shape that shipped: prose with a ';' in a comment above the token."""
    html = ("<html><head><style>:root { --bg:#111111;\n"
            "  /* validated against each surface; the brighter one failed */\n"
            "  --spend-bar:#0284c7; }\n"
            ".bar { background:#0284c7; }</style></head></html>")
    out, _ = tokenise_literals(html)
    assert "--spend-bar:#0284c7" in out, "the definition must keep its literal"
    assert "var(--spend-bar)" in out, "a use elsewhere is still tokenised"
    assert "--spend-bar:var(--spend-bar)" not in out


def test_a_comment_between_the_name_and_the_value_does_not_expose_it():
    html = ("<html><head><style>:root { --accent: /* sky */ #0284c7; }\n"
            ".x { color:#0284c7; }</style></head></html>")
    out, _ = tokenise_literals(html)
    assert "--accent: /* sky */ #0284c7" in out


def test_comments_are_never_rewritten():
    out, _ = tokenise_literals(styled("/* old value was #0284c7 */ .x { color:#0284c7; }"))
    assert "/* old value was #0284c7 */" in out


def test_a_colour_the_page_does_not_define_is_left_alone():
    out, n = tokenise_literals(styled(".x { color:#123456; }"))
    assert "#123456" in out and n == 0


def test_scripts_are_never_touched():
    html = styled(".x{color:#0284c7}") + "<script>const c = '#0284c7';</script>"
    out, _ = tokenise_literals(html)
    assert "const c = '#0284c7';" in out
