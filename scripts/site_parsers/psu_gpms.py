#!/usr/bin/env python3
"""Penn State's Graduate Program Management System.

The author found it: every graduate programme at Penn State has a
faculty roster behind one URL, keyed by a programme code, and the
system's own dropdown lists all 343 of them. The generic extractor
read six names off one of these pages, two of which were the form's
"First Name" and "Last Name" labels, because the roster is a TABLE
with the given name and the surname in separate columns.

A parser written for the table reads all of them. One parser, 343
programmes -- which is why a site like this is worth the hand work
and an ordinary lab page is not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from follow_lab_links import get                              # noqa: E402

INDEX = "https://secure.gradsch.psu.edu/gpms/index.cfm"
ROSTER = INDEX + "?searchType=fac&prog={code}"
INSTITUTION = "Pennsylvania State University-Main Campus"

#: the programme dropdown, "CODE|00123" with a readable label
_OPTION = re.compile(
    r"value=[\"']([A-Z0-9]{2,8})\|\d+[\"'][^>]*>([^<]{2,80})<", re.I)

#: campus is in the label; only University Park grants most doctorates
_MAIN_CAMPUS = re.compile(r"University Park|^(?![^,]*,)", re.I)

FIELD = [
    ("statistic", "stats"), ("mathemat", "math"),
    ("computer sci", "ai"), ("informatics", "ai"), ("data scien", "ai"),
    ("electrical", "ee"), ("comput engineer", "ee"),
    ("mechanical", "mecheng"), ("aerospace", "aerospace"),
    ("civil", "civileng"), ("architectural engineer", "civileng"),
    ("chemical engineer", "chemeng"), ("chemistry", "chemistry"),
    ("materials", "materials"), ("physics", "physics"),
    ("nuclear", "nuclear"), ("industrial engineer", "industrial"),
    ("biomedical", "biomed"), ("bioengineer", "biomed"),
    ("biology", "biology"), ("agricultural", "agriculture"),
    ("petroleum", "petroleum"), ("mining", "mining"),
    ("energy", "energy"), ("environmental engineer", "civileng"),
    ("geoscience", "geoscience"), ("meteorolog", "geoscience"),
]


def field_of(label: str) -> str:
    low = label.lower()
    for key, val in FIELD:
        if key in low:
            return val
    return ""


def targets() -> list[dict]:
    """Every programme roster the system exposes."""
    html = get(INDEX)
    if not html:
        return []
    out, seen = [], set()
    for code, label in _OPTION.findall(html):
        if code in seen:
            continue
        seen.add(code)
        label = re.sub(r"\s+", " ", label).strip()
        #: skip the degree dropdown, whose codes repeat as labels
        if label.lower().startswith(("doctor of", "master of")):
            continue
        out.append({
            "url": ROSTER.format(code=code),
            "institution": INSTITUTION,
            "department_field": field_of(label),
            "title": label,
            "roster_kind": "programme faculty",
        })
    return out


def parse(url: str, html: str) -> list[str] | None:
    """Names from the GPMS faculty table, or None if this is not one."""
    if "gradsch.psu.edu/gpms" not in url:
        return None
    body = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I)
    names, head = [], None
    for row in rows:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",
                                     row, re.S | re.I)]
        cells = [c.replace("&nbsp;", "").strip() for c in cells]
        if head is None:
            low = [c.lower() for c in cells]
            if "first name" in low and "last name" in low:
                head = (low.index("first name"), low.index("last name"))
            continue
        fi, li = head
        if len(cells) <= max(fi, li):
            continue
        first, last = cells[fi], cells[li]
        if not first or not last:
            continue
        full = f"{first} {last}".strip()
        if full not in names:
            names.append(full)
    return names or None
