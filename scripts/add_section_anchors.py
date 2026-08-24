#!/usr/bin/env python3
"""Bake descriptive anchor ids into the hand-written pages under site/.

Every h1-h4 outside the sidebar/nav/footer gets a stable, readable id — on its
enclosing card/panel/section when it has one (so :target frames the whole
block), otherwise on the heading itself. Ids already present are never
touched, so links that work today keep working.

The slug is the kebab-case of the visible heading text, capped at 48
characters on a word boundary, with any leading enumerator ("1. ", "A. ")
dropped. site/anchors.js computes the identical slug at runtime, so a heading
this script cannot reach still ends up addressable by the same name.

Also:
  * removes the hand-copied inline share buttons (they carried an emoji and
    duplicated the same clipboard snippet ~40 times); anchors.js renders one
    uniform control instead,
  * adds <script src="/anchors.js" defer></script> to every page.

Idempotent: safe to re-run. Never touches the generated pages (stem.html,
non_stem.html, universities/**) — those are owned by
scripts/generate_name_lists_html.py.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

# Generated elsewhere — do not rewrite.
SKIP = {
    "stem.html",
    "non_stem.html",
    "name_lists.html",
    "analytics.html",
    "chat-admin.html",
    "caltech_dashboard.html",
    "caltech_field_demographics.html",
    "caltech_ipeds_tables.html",
}

BLOCK_CLASSES = {
    "chart-box", "card", "panel", "table-wrap", "info-box", "section",
    "step-section", "tab-content", "uni-card", "link-card",
    # These are matched as whole class names, not substrings: a
    # <section class="chart-section"> did NOT match "section" above, so its
    # heading was treated as having no block and got an id of its own --
    # "institutions-2" beside the section's existing "institutions". Both
    # then resolved to nearly the same place, and the sidebar linked to one
    # while the copy-link control offered the other.
    "chart-section", "chart-wrap", "figure-wrap",
}
SKIP_ANCESTORS = {"nav", "footer"}
SKIP_CLASSES = {"sidebar", "sb-group", "sb-content"}
HEADINGS = {"h1", "h2", "h3", "h4"}

ENUMERATOR = re.compile(r"^(?:[0-9]{1,2}|[A-Za-z])[.)]\s+")
TAGS = re.compile(r"<[^>]+>")


def slugify(text: str) -> str:
    # The scanner reads raw source with convert_charrefs=False, so heading
    # text still holds entities. anchors.js slugs the same heading from
    # textContent, where the browser has already decoded them -- so without
    # this, "The Master&rsquo;s Expansion" baked as
    # "the-master-rsquo-s-expansion" here while the runtime looked for
    # "the-master-s-expansion", and the two never agreed on any heading
    # containing an entity.
    s = unescape(text or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = ENUMERATOR.sub("", s)
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 48:
        cut = s[:48]
        last = cut.rfind("-")
        s = cut[:last] if last > 20 else cut
    return s


class Scanner(HTMLParser):
    """Collect headings with their enclosing block, tracking byte offsets."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.lines = [0]
        for line in html.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.stack: list[dict] = []
        self.headings: list[dict] = []
        self.share_spans: list[tuple[int, int]] = []
        self._open_heading: dict | None = None
        self._share_start: int | None = None
        self._share_depth = 0

    def _off(self) -> int:
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self._off()
        end = start + len(self.get_starttag_text() or "")
        adict = dict(attrs)
        classes = set((adict.get("class") or "").split())
        entry = {
            "tag": tag, "attrs": adict, "classes": classes,
            "start": start, "end": end, "has_heading": False,
        }
        if tag == "a" and "share-btn" in classes and self._share_start is None:
            self._share_start = start
            self._share_depth = 0
        elif tag == "a" and self._share_start is not None:
            self._share_depth += 1

        if tag in HEADINGS and self._open_heading is None:
            if not self._skipped():
                block = None
                for anc in reversed(self.stack):
                    if anc["classes"] & BLOCK_CLASSES:
                        block = anc if not anc["has_heading"] else None
                        break
                for anc in reversed(self.stack):
                    if anc["classes"] & BLOCK_CLASSES:
                        anc["has_heading"] = True
                        break
                self._open_heading = {
                    "start": start, "end": end, "attrs": adict,
                    "block": block, "text_from": end, "tag": tag,
                    # Every id this heading already sits inside. If one of
                    # them is the slug we would generate, the heading is
                    # already reachable under that exact name and adding a
                    # numbered variant only creates a second anchor for the
                    # same content.
                    "ancestor_ids": {a["attrs"]["id"] for a in self.stack
                                     if a["attrs"].get("id")},
                }
        if tag not in ("br", "img", "input", "meta", "link", "hr", "source"):
            self.stack.append(entry)

    def _skipped(self) -> bool:
        for anc in self.stack:
            if anc["tag"] in SKIP_ANCESTORS:
                return True
            if anc["classes"] & SKIP_CLASSES:
                return True
            if anc["attrs"].get("id") in ("sidebar", "site-footer"):
                return True
        return False

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        start = self._off()
        if tag == "a" and self._share_start is not None:
            if self._share_depth == 0:
                self.share_spans.append((self._share_start, start + 4))
                self._share_start = None
            else:
                self._share_depth -= 1
        if self._open_heading and tag == self._open_heading["tag"]:
            h = self._open_heading
            raw = self.html[h["text_from"]:start]
            raw = re.sub(r"<a\b[^>]*class=\"[^\"]*share-btn[^\"]*\"[^>]*>.*?</a>", "", raw, flags=re.S)
            h["text"] = TAGS.sub(" ", raw)
            h["close"] = start
            self.headings.append(h)
            self._open_heading = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break


def existing_ids(html: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', html))


def process(path: Path, dry: bool = False) -> tuple[int, int, bool]:
    html = path.read_text()
    original = html
    sc = Scanner(html)
    sc.feed(html)

    taken = existing_ids(html)
    edits: list[tuple[int, int, str]] = []  # (start, end, replacement)

    added = 0
    for h in sc.headings:
        block = h["block"]
        holder_attrs = block["attrs"] if block else h["attrs"]
        if holder_attrs.get("id"):
            continue
        base = slugify(h.get("text", ""))
        if not base:
            continue
        if base in h.get("ancestor_ids", ()):
            continue  # already addressable at exactly this name
        cand, n = base, 2
        while cand in taken:
            cand = f"{base}-{n}"
            n += 1
        taken.add(cand)
        tag_start = block["start"] if block else h["start"]
        tag_end = block["end"] if block else h["end"]
        tag_text = html[tag_start:tag_end]
        m = re.match(r"<([a-zA-Z0-9]+)", tag_text)
        if not m:
            continue
        insert_at = tag_start + m.end()
        edits.append((insert_at, insert_at, f' id="{cand}"'))
        added += 1

    removed = 0
    for start, end in sc.share_spans:
        edits.append((start, end, ""))
        removed += 1

    for start, end, repl in sorted(edits, key=lambda e: -e[0]):
        html = html[:start] + repl + html[end:]

    script_added = False
    if 'src="/anchors.js"' not in html and "</body>" in html:
        html = html.replace(
            "</body>", '<script src="/anchors.js" defer></script>\n</body>', 1
        )
        script_added = True

    if html != original and not dry:
        path.write_text(html)
    return added, removed, script_added


def main() -> None:
    dry = "--dry-run" in sys.argv
    targets = sorted(p for p in SITE.glob("*.html") if p.name not in SKIP)
    total_ids = total_share = 0
    for path in targets:
        added, removed, script = process(path, dry)
        total_ids += added
        total_share += removed
        flag = " +anchors.js" if script else ""
        if added or removed or script:
            print(f"  {path.name:28s} +{added:3d} ids  -{removed:2d} inline share{flag}")
    print(f"{'(dry run) ' if dry else ''}{total_ids} ids added, {total_share} inline share buttons removed")


if __name__ == "__main__":
    main()
