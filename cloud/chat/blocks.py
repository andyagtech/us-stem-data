"""
Block construction, validation and clamping for the v2 chat response contract.

Two jobs:

1. Enforce every cap in contract section 4.7 and every URL rule in 4.5.5 /
   4.8 *server side*, before serialising.  The widget enforces them again;
   neither side trusts the other.

2. Make a fabricated number hard rather than merely discouraged.  See
   ``Ledger``.  Every numeric value the model puts in a chart, table or stat
   must have been returned by a data tool earlier in the same turn.  A block
   containing an ungrounded number is rejected and the model is told which
   number failed, so it can re-call the data tool instead of inventing.
"""
from __future__ import annotations

import json
import re

MAX_BLOCKS = 8
MAX_MD = 4000
MAX_DATASETS = 4
MAX_POINTS = 40
MAX_LABELS = 40
MAX_COLUMNS = 8
MAX_ROWS = 25
MAX_CELL = 120
MAX_STAT_ITEMS = 4
MAX_SUGGEST_ITEMS = 4
MAX_URL = 300
MAX_FRAGMENT = 128
MAX_QUERY = 256
MAX_BODY_BYTES = 128 * 1024

# "histogram" is a bar chart over ordered bins rather than categories: the
# x axis is a continuous quantity cut into bands, so the bars are adjacent
# and the order carries meaning. Kept distinct from "bar" so the renderer
# can close the gap between bars and the model cannot reorder the bands.
CHART_TYPES = {"line", "bar", "hbar", "stacked_bar", "area", "doughnut",
               "scatter", "histogram"}
ROLES = {"nra", "domestic", "total", "alt1", "alt2", "alt3", "neutral"}
FORMATS = {"int", "float1", "pct", "pct1", "usd", "usd_k", "usd_m", "compact", "text"}
ALIGNS = {"left", "right", "center"}
NOTICE_KINDS = {"info", "ok", "warn", "bad"}
PLACEMENTS = {"before_text", "after_text"}

# RFC 3986 fragment production.
_FRAG_CHARS = r"[A-Za-z0-9._~!$&'()*+,;=:@/?%-]"
FRAGMENT_RE = re.compile("^" + _FRAG_CHARS + "{1," + str(MAX_FRAGMENT) + "}$")
QUERY_RE = re.compile("^" + _FRAG_CHARS + "{1," + str(MAX_QUERY) + "}$")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SQL_BANNED = ("insert", "update", "delete", "drop", "alter", "create",
              "attach", "copy", "pragma", "grant", "revoke", "truncate",
              "replace", "vacuum")


class BlockError(Exception):
    """Raised with a message that is fed back to the model as a tool result."""


# ---------------------------------------------------------------------------
# scalar helpers
# ---------------------------------------------------------------------------
def text(value, limit: int) -> str:
    """Plain-text field: control chars stripped, whitespace collapsed, capped."""
    if value is None:
        return ""
    s = CTRL_RE.sub(" ", str(value))
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s[:limit]


_NAV_TOKEN_SLASH_FIRST = re.compile(r"\[\[(/[^|\]]{1,300})\|([^\]]{1,80})\]\]")
_NAV_TOKEN_LABEL_FIRST = re.compile(r"\[\[([^/|\]][^|\]]{0,79})\|(/[^\]]{1,300})\]\]")
_NAV_TOKEN_BARE = re.compile(r"\[\[(/[^|\]]{1,300})\]\]")


def normalize_nav_tokens(s: str) -> str:
    """Repair the two ways models get the inline nav token backwards.

    The contract grammar is ``[[nav:/url|Label]]``.  Models routinely emit
    ``[[Label|/url]]`` or ``[[/url|Label]]``.  Both are unambiguous, so fix
    them rather than letting the widget render them as literal text.  The
    grammar itself is unchanged; this only widens what the server accepts.
    """
    s = _NAV_TOKEN_LABEL_FIRST.sub(lambda m: f"[[nav:{m.group(2)}|{m.group(1)}]]", s)
    s = _NAV_TOKEN_SLASH_FIRST.sub(lambda m: f"[[nav:{m.group(1)}|{m.group(2)}]]", s)
    s = _NAV_TOKEN_BARE.sub(lambda m: f"[[nav:{m.group(1)}]]", s)
    return s


def md(value, limit: int = MAX_MD) -> str:
    """Markdown field: newlines survive, control chars do not."""
    if value is None:
        return ""
    s = CTRL_RE.sub(" ", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    s = normalize_nav_tokens(s)
    if len(s) <= limit:
        return s.strip()
    cut = s[:limit]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit * 0.6 else cut).rstrip() + "…"


def as_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return default


def as_number(value):
    """None for gaps; float/int otherwise; raises for anything non-numeric."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise BlockError("boolean is not a chart value")
    if isinstance(value, (int, float)):
        n = value
    else:
        s = str(value).replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            n = float(s)
        except ValueError:
            raise BlockError(f"non-numeric value {value!r}")
    if n != n or n in (float("inf"), float("-inf")):
        raise BlockError("NaN or infinite value")
    return n


# ---------------------------------------------------------------------------
# the grounding ledger
# ---------------------------------------------------------------------------
class Ledger:
    """Every number a data tool returned during this turn.

    A render tool's numbers are checked against it.  Three things pass:

      * an exact ledger value, at 1 dp or at 0 dp (the model is allowed to
        round 61.43 to 61.4 or to 61);
      * a difference of two ledger values (``gap = mit - national`` is a
        legitimate derivation, and refusing it would push the model back to
        prose-only answers);
      * a four-digit year in 1900-2100 (axis labels, not statistics).

    Everything else is a number the model produced from nowhere.
    """

    def __init__(self):
        self.values = set()   # raw floats, for the difference check
        self.keys = set()     # rounded forms, for membership
        self.sources = []     # human-readable provenance, for `source` fields

    def _add_number(self, n: float):
        if n != n or n in (float("inf"), float("-inf")):
            return
        self.values.add(float(n))
        self.keys.add(round(float(n), 1))
        self.keys.add(float(round(float(n))))

    def add(self, obj):
        """Walk a tool result and record every number in it."""
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            self._add_number(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self.add(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self.add(v)
        elif isinstance(obj, str):
            # numbers embedded in strings ("43.8%") still count as returned
            for m in re.findall(r"-?\d+(?:\.\d+)?", obj):
                try:
                    self._add_number(float(m))
                except ValueError:
                    pass

    def note_source(self, label: str):
        if label and label not in self.sources:
            self.sources.append(label)

    def grounded(self, n) -> bool:
        if n is None:
            return True
        f = float(n)
        if round(f, 1) in self.keys or float(round(f)) in self.keys:
            return True
        if f == int(f) and 1900 <= f <= 2100:
            return True
        for a in self.values:                      # derived difference
            if round(a - f, 1) in self.keys:
                return True
        return False

    def check(self, numbers, where: str):
        bad = [n for n in numbers if n is not None and not self.grounded(n)]
        if bad:
            sample = ", ".join(str(b) for b in bad[:5])
            raise BlockError(
                f"{where}: {len(bad)} value(s) did not come from any data tool "
                f"result in this conversation ({sample}). Call a data tool "
                f"(nra_lookup, get_university_facts, get_national_series, "
                f"list_universities) and use the numbers it returns verbatim. "
                f"Do not state figures from memory."
            )


# ---------------------------------------------------------------------------
# URL handling (contract 4.5.5) — path validated, fragment opaque
# ---------------------------------------------------------------------------
def split_url(url: str):
    """('/path.html', 'query', 'fragment') or raise."""
    if not isinstance(url, str):
        raise BlockError("url must be a string")
    u = CTRL_RE.sub("", url).strip()
    if not u or len(u) > MAX_URL:
        raise BlockError("url missing or longer than 300 chars")
    if not u.startswith("/") or u.startswith("//") or u.startswith("/\\"):
        raise BlockError("site url must start with a single '/' and name no host")
    if "\\" in u:
        raise BlockError("backslash in url")
    frag = ""
    if "#" in u:
        u, frag = u.split("#", 1)
    query = ""
    if "?" in u:
        u, query = u.split("?", 1)
    if frag and not FRAGMENT_RE.match(frag):
        raise BlockError("fragment is not a well-formed RFC 3986 fragment")
    if query and not QUERY_RE.match(query):
        raise BlockError("query string is not well formed")
    return u, query, frag


def validate_site_url(url: str, ctx) -> tuple:
    """Returns (normalised_url, path, fragment).  Raises BlockError if unusable."""
    path, query, frag = split_url(url)
    # The site serves /industries/mining and /industries/mining.html as one
    # page, and the site map now carries the clean form. Accept either and
    # normalise: a link written with the extension still resolves, which
    # matters for answers cached before the change and for anything the model
    # recalls from training rather than reads from the map.
    if path not in ctx.site_paths and path.endswith(".html"):
        stripped = path[:-5]
        if stripped in ctx.site_paths:
            path = stripped
    if path not in ctx.site_paths:
        raise BlockError(
            f"'{path}' is not a page on this site. Use a path from the site map."
        )
    enumerated = ctx.enumerated_anchors.get(path)
    # Fragments are opaque unless the page explicitly declares its anchors
    # enumerable.  Never pattern-match a fragment here (contract 4.5.5 rule 1).
    if frag and enumerated is not None and frag not in enumerated:
        frag = ""
    out = path + (("?" + query) if query else "") + (("#" + frag) if frag else "")
    return out, path, frag


def validate_external_url(url: str) -> str:
    if not isinstance(url, str):
        raise BlockError("url must be a string")
    u = CTRL_RE.sub("", url).strip()
    if len(u) > MAX_URL:
        raise BlockError("url too long")
    if not re.match(r"^https://[A-Za-z0-9.\-]+(:\d+)?(/[^\s]*)?$", u):
        raise BlockError("external url must be an absolute https:// URL")
    return u


# ---------------------------------------------------------------------------
# build context
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, site_paths, enumerated_anchors, ledger):
        self.site_paths = site_paths
        self.enumerated_anchors = enumerated_anchors
        self.ledger = ledger


# ---------------------------------------------------------------------------
# per-block builders
# ---------------------------------------------------------------------------
def _placement(args):
    p = args.get("placement")
    return p if p in PLACEMENTS else "after_text"


def _nav_stub(value, ctx):
    """{'url','label'} sub-object used by chart.nav / table.footer_nav / row.nav."""
    if not isinstance(value, dict):
        return None
    try:
        url, path, frag = validate_site_url(value.get("url", ""), ctx)
    except BlockError:
        return None
    label = text(value.get("label"), 60)
    if not label:
        return None
    out = {"url": url, "label": label, "path": path.lstrip("/")}
    if frag:
        out["fragment"] = frag
    return out


def build_chart(args, ctx):
    kind = args.get("chart") or args.get("type")
    if kind not in CHART_TYPES:
        raise BlockError(f"chart must be one of {sorted(CHART_TYPES)}")
    title = text(args.get("title"), 90)
    if not title:
        raise BlockError("chart.title is required")
    source = text(args.get("source"), 120)
    if not source:
        raise BlockError(
            "chart.source is required and must name the data tool the numbers "
            "came from, e.g. 'IPEDS Completions via nra_lookup'."
        )

    raw_labels = args.get("labels") or []
    if not isinstance(raw_labels, list):
        raise BlockError("chart.labels must be an array")
    labels = [text(x, 24) for x in raw_labels[:MAX_LABELS]]
    if kind != "scatter" and not labels:
        raise BlockError("chart.labels is required for every chart type except scatter")
    if len(raw_labels) > MAX_LABELS:
        raise BlockError(
            f"chart has {len(raw_labels)} labels; the cap is {MAX_LABELS}. "
            "Narrow the year range or aggregate."
        )

    raw_sets = args.get("datasets")
    if not isinstance(raw_sets, list) or not raw_sets:
        raise BlockError("chart.datasets must be a non-empty array")

    datasets, all_numbers = [], []
    for dsr in raw_sets[:MAX_DATASETS]:
        if not isinstance(dsr, dict):
            continue
        label = text(dsr.get("label"), 40)
        data = dsr.get("data")
        if not isinstance(data, list) or not data:
            raise BlockError(f"dataset '{label}' has no data array")
        if len(data) > MAX_POINTS:
            raise BlockError(
                f"dataset '{label}' has {len(data)} points; the cap is {MAX_POINTS}. "
                "A silently truncated series is a lying chart, so narrow the range."
            )
        if kind == "scatter":
            points = []
            for p in data:
                if not isinstance(p, dict):
                    raise BlockError("scatter data must be {x, y} objects")
                x, y = as_number(p.get("x")), as_number(p.get("y"))
                points.append({"x": x, "y": y})
                all_numbers += [x, y]
            values = points
        else:
            values = [as_number(v) for v in data]
            if len(values) != len(labels):
                raise BlockError(
                    f"dataset '{label}' has {len(values)} points but there are "
                    f"{len(labels)} labels; they must match exactly."
                )
            all_numbers += values
        ds = {"label": label or "series", "data": values}
        role = dsr.get("role")
        ds["role"] = role if role in ROLES else "neutral"
        for flag in ("fill", "dashed"):
            if flag in dsr:
                ds[flag] = as_bool(dsr.get(flag))
        if dsr.get("axis") in ("left", "right"):
            ds["axis"] = dsr["axis"]
        datasets.append(ds)
    if not datasets:
        raise BlockError("chart has no usable dataset")

    ctx.ledger.check(all_numbers, "chart data")

    block = {"type": "chart", "chart": kind, "title": title,
             "datasets": datasets, "source": source,
             "placement": _placement(args)}
    if labels:
        block["labels"] = labels
    sub = text(args.get("subtitle"), 140)
    if sub:
        block["subtitle"] = sub
    for axis in ("y", "y2", "x"):
        spec = args.get(axis)
        if isinstance(spec, dict):
            a = {}
            if spec.get("format") in FORMATS:
                a["format"] = spec["format"]
            lab = text(spec.get("label"), 40)
            if lab:
                a["label"] = lab
            if "begin_at_zero" in spec:
                a["begin_at_zero"] = as_bool(spec.get("begin_at_zero"))
            if a:
                block[axis] = a
    nav = _nav_stub(args.get("nav"), ctx)
    if nav:
        block["nav"] = nav
    return block


def build_table(args, ctx):
    title = text(args.get("title"), 120)
    source = text(args.get("source"), 120)
    if not source:
        raise BlockError(
            "table.source is required and must name the data tool the rows "
            "came from, e.g. 'IPEDS Completions via nra_lookup'."
        )
    raw_cols = args.get("columns")
    if not isinstance(raw_cols, list) or not raw_cols:
        raise BlockError("table.columns must be a non-empty array")
    columns = []
    for c in raw_cols[:MAX_COLUMNS]:
        if not isinstance(c, dict) or not c.get("key"):
            continue
        fmt = c.get("format") if c.get("format") in FORMATS else "text"
        align = c.get("align")
        if align not in ALIGNS:
            align = "left" if fmt == "text" else "right"
        col = {"key": text(c["key"], 40), "label": text(c.get("label") or c["key"], 40),
               "align": align, "format": fmt}
        if as_bool(c.get("emphasis")):
            col["emphasis"] = True
        columns.append(col)
    if not columns:
        raise BlockError("table has no usable columns")

    raw_rows = args.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise BlockError("table.rows must be a non-empty array")
    numeric_keys = {c["key"] for c in columns if c["format"] != "text"}

    rows, numbers, truncated = [], [], len(raw_rows) > MAX_ROWS
    for r in raw_rows[:MAX_ROWS]:
        if not isinstance(r, dict):
            continue
        row = {}
        for c in columns:
            v = r.get(c["key"])
            if v is None:
                row[c["key"]] = None
            elif c["key"] in numeric_keys:
                n = as_number(v)
                row[c["key"]] = n
                numbers.append(n)
            else:
                row[c["key"]] = text(v, MAX_CELL)
        nav = _nav_stub(r.get("nav"), ctx)
        if nav:
            row["nav"] = nav
        rows.append(row)
    if not rows:
        raise BlockError("table has no usable rows")

    ctx.ledger.check(numbers, "table cells")

    note = text(args.get("note"), 160)
    if truncated:
        extra = f"showing first {MAX_ROWS} of {len(raw_rows)}"
        note = f"{note} ({extra})" if note else extra
    block = {"type": "table", "columns": columns, "rows": rows,
             "source": source, "placement": _placement(args)}
    if title:
        block["title"] = title
    if note:
        block["note"] = note[:200]
    fn = _nav_stub(args.get("footer_nav"), ctx)
    if fn:
        block["footer_nav"] = fn
    return block


_NUM_IN_STRING = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def build_stat(args, ctx):
    raw = args.get("items")
    if not isinstance(raw, list) or not raw:
        raise BlockError("stat.items must be a non-empty array")
    items, numbers = [], []
    for it in raw[:MAX_STAT_ITEMS]:
        if not isinstance(it, dict):
            continue
        label = text(it.get("label"), 60)
        value = text(it.get("value"), 24)
        if not label or not value:
            continue
        item = {"label": label, "value": value}
        for m in _NUM_IN_STRING.findall(value):
            try:
                numbers.append(float(m.replace(",", "")))
            except ValueError:
                pass
        delta = text(it.get("delta"), 16)
        if delta:
            item["delta"] = delta
            for m in _NUM_IN_STRING.findall(delta):
                try:
                    numbers.append(float(m.replace(",", "")))
                except ValueError:
                    pass
        if it.get("delta_dir") in ("up", "down", "flat"):
            item["delta_dir"] = it["delta_dir"]
        note = text(it.get("note"), 80)
        if note:
            item["note"] = note
        if as_bool(it.get("emphasis")):
            item["emphasis"] = True
        if it.get("bar") is not None:
            bar = as_number(it.get("bar"))
            if bar is not None:
                item["bar"] = max(0.0, min(100.0, float(bar)))
                numbers.append(bar)
        items.append(item)
    if not items:
        raise BlockError("stat has no usable items")
    ctx.ledger.check(numbers, "stat values")
    block = {"type": "stat", "items": items, "placement": _placement(args)}
    source = text(args.get("source"), 120)
    if source:
        block["source"] = source
    return block


def build_nav(args, ctx):
    url = args.get("url")
    if not url:
        # Legacy navigate_user(page, section_id) — normalise into a url.
        page = text(args.get("page"), 120).lstrip("/")
        section = text(args.get("section_id"), MAX_FRAGMENT)
        if not page:
            raise BlockError("navigate_user needs a url")
        url = "/" + page + (("#" + section) if section else "")
    norm, path, frag = validate_site_url(url, ctx)
    label = text(args.get("label"), 60)
    if not label:
        raise BlockError("nav.label is required")
    block = {"type": "nav", "url": norm, "label": label,
             "path": path.lstrip("/"), "auto": as_bool(args.get("auto")),
             "highlight": as_bool(args.get("highlight"), bool(frag)),
             "placement": _placement(args)}
    if frag:
        block["fragment"] = frag
    reason = text(args.get("reason"), 140)
    if reason:
        block["reason"] = reason
    return block


def build_link(args, ctx):
    kind = args.get("kind")
    if kind not in ("site", "external"):
        raise BlockError("link.kind must be 'site' or 'external'")
    raw = args.get("url", "")
    if kind == "site":
        url, _path, _frag = validate_site_url(raw, ctx)
        copyable = as_bool(args.get("copyable"), True)
    else:
        url = validate_external_url(raw)
        copyable = as_bool(args.get("copyable"), False)
    label = text(args.get("label"), 70)
    if not label:
        raise BlockError("link.label is required")
    block = {"type": "link", "kind": kind, "url": url, "label": label,
             "copyable": copyable, "placement": _placement(args)}
    note = text(args.get("note"), 160)
    if note:
        block["note"] = note
    return block


def build_query(args, _ctx):
    sql = args.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise BlockError("query.sql is required")
    sql = CTRL_RE.sub(" ", sql).replace("\r\n", "\n").strip()[:2000]
    probe = re.sub(r"\s+", " ", sql).strip().lower()
    if ";" in sql or "--" in sql or "/*" in sql:
        raise BlockError("SQL must contain no ';', '--' or '/*'")
    if not probe.startswith("select"):
        raise BlockError("SQL must start with SELECT")
    if "limit" not in probe:
        raise BlockError("SQL must include a LIMIT clause")
    for word in SQL_BANNED:
        if re.search(r"\b" + word + r"\b", probe):
            raise BlockError(f"SQL must be read-only; '{word}' is not allowed")
    block = {"type": "query", "sql": sql,
             "explanation": text(args.get("explanation"), 300),
             "placement": _placement(args)}
    tbl = text(args.get("table"), 40)
    if tbl:
        block["table"] = tbl
    return block


def build_suggest(args, _ctx):
    raw = args.get("items")
    if not isinstance(raw, list) or not raw:
        raise BlockError("suggest.items must be a non-empty array")
    items = []
    for it in raw[:MAX_SUGGEST_ITEMS]:
        if not isinstance(it, dict):
            continue
        label = text(it.get("label"), 40)
        prompt = text(it.get("prompt"), 160)
        if label and prompt:
            items.append({"label": label, "prompt": prompt})
    if not items:
        raise BlockError("suggest has no usable items")
    return {"type": "suggest", "items": items, "placement": "after_text"}


def build_notice(args, _ctx):
    kind = args.get("kind")
    if kind not in NOTICE_KINDS:
        raise BlockError(f"notice.kind must be one of {sorted(NOTICE_KINDS)}")
    body = md(args.get("md") or args.get("body"), MAX_MD)
    if not body:
        raise BlockError("notice.md is required")
    block = {"type": "notice", "kind": kind, "md": body,
             "placement": _placement(args)}
    title = text(args.get("title"), 60)
    if title:
        block["title"] = title
    icon = text(args.get("icon"), 4)
    if icon:
        block["icon"] = icon
    return block


BUILDERS = {
    "show_chart": build_chart,
    "show_table": build_table,
    "show_stats": build_stat,
    "navigate_user": build_nav,
    "show_link": build_link,
    "suggest_query": build_query,
    "suggest_followups": build_suggest,
    "show_notice": build_notice,
}

BLOCK_FOR_TOOL = {
    "show_chart": "chart", "show_table": "table", "show_stats": "stat",
    "navigate_user": "nav", "show_link": "link", "suggest_query": "query",
    "suggest_followups": "suggest", "show_notice": "notice",
}


# ---------------------------------------------------------------------------
# assembly (contract 4.6) and final caps (4.7)
# ---------------------------------------------------------------------------
def assemble(pre_post_blocks, reply_text):
    """blocks = pre + [text] + post + [suggest], with a single auto nav."""
    pre = [b for b in pre_post_blocks
           if b.get("placement") == "before_text" and b["type"] != "suggest"]
    post = [b for b in pre_post_blocks
            if b.get("placement") != "before_text" and b["type"] != "suggest"]
    sug = [b for b in pre_post_blocks if b["type"] == "suggest"][:1]

    txt = []
    if reply_text and reply_text.strip():
        txt = [{"type": "text", "md": md(reply_text)}]

    body = pre + txt + post
    truncated = False

    # Cap at MAX_BLOCKS by dropping from the end of the render list. The
    # suggest block is pinned last by contract 4.5.9, so it must not be the
    # thing the cap eats; the prose is never dropped either.
    budget = max(1, MAX_BLOCKS - len(sug))
    if len(body) > budget:
        keep = body[:budget]
        if not any(b["type"] == "text" for b in keep):
            txt_block = next((b for b in body if b["type"] == "text"), None)
            if txt_block is not None:
                keep[-1] = txt_block
        body, truncated = keep, True

    blocks = body + sug
    for b in blocks:
        b.pop("placement", None)

    seen_auto = False
    for b in blocks:
        if b["type"] == "nav" and b.get("auto"):
            if seen_auto:
                b["auto"] = False
            else:
                seen_auto = True

    # 128 KB body budget: shed chart/table blocks from the end until it fits.
    while len(json.dumps(blocks).encode("utf-8")) > MAX_BODY_BYTES:
        idx = next((i for i in range(len(blocks) - 1, -1, -1)
                    if blocks[i]["type"] in ("chart", "table")), None)
        if idx is None:
            break
        blocks.pop(idx)
        truncated = True
    return blocks, truncated


def mirror_actions(blocks):
    """v1 `actions` mirror (contract 4.9).  Query-carrying navs are omitted."""
    out = []
    for b in blocks:
        if b["type"] == "nav":
            if "?" in b["url"]:
                continue
            act = {"type": "navigate", "page": b.get("path", ""), "label": b["label"]}
            if b.get("fragment"):
                act["section_id"] = b["fragment"]
            out.append(act)
        elif b["type"] == "query":
            out.append({"type": "query", "sql": b["sql"],
                        "explanation": b.get("explanation", "")})
    return out
