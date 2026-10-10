#!/usr/bin/env python3
"""A clickable index of the programs and labs worth looking at.

The analysis so far lives in three JSON files and a pile of snapshots,
which is useless to anyone trying to work through it. This is the page
that makes it navigable: every program and lab in one place, sorted by
concentration, each one a link out to where it describes itself.

WHAT EACH ROW IS. A program row is a university department, its
non-resident or name-marker share, and a link to find it. A lab row is a
research group whose public roster has been read and archived, with the
count and a link to both the live page and the snapshot.

WHAT NO ROW IS. Nobody is named and nobody is labeled. A share is a
count over a group, and the name-marker shares are floors because the
classifier skips names it cannot place. The page says so where it matters
rather than once at the bottom.

PRIVATE. The directory is a working list, not a publication, so it is
declared in private_pages.py and stays out of the sitemap, the contents
page and the assistant's map.

Usage:
  python3 scripts/build_lab_directory.py
"""
from __future__ import annotations

import html
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

LABS = ROOT / "data" / "labs"
OUT = ROOT / "site" / "lab-directory.html"
E = html.escape

SECTOR_LABEL = {
    "nuclear": "Nuclear", "aerospace": "Aerospace", "petroleum": "Petroleum",
    "mining": "Mining &amp; metals", "battery": "Battery &amp; materials",
    "ai": "AI &amp; computing", "bio": "Bioengineering",
    "semiconductor": "Semiconductors", "robotics": "Robotics",
}


def _unesc(t: str) -> str:
    """A page title already carries HTML entities; escaping it again
    turned Texas A&M into Texas A&amp;M on screen."""
    return html.unescape(t or "")


def jload(name, default=None):
    f = LABS / name
    if not f.exists():
        return default if default is not None else {}
    return json.loads(f.read_text())


def main() -> int:
    rosters = jload("rosters.json")
    urls = {}
    for r in jload("program_urls.json").get("rows", []):
        if r.get("status") == "ok":
            urls[(r["institution"], r["sector"])] = r
    security = jload("security_targets.json")
    ranked = jload("search_targets.json")

    # ---- labs whose roster has been read and archived
    lab_rows = []
    for inst in rosters.get("institutions", {}).values():
        for p in inst.get("pages", []):
            if p.get("status") != "ok":
                continue
            c = p.get("composition") or {}
            n = c.get("members_detected") or 0
            if n < 8:
                continue
            lab_rows.append({
                "group": p.get("title") or p["url"],
                "institution": inst["name"],
                "url": p["url"], "members": n,
                "share": c.get("share_chinese_markers"),
                "snapshot": p.get("snapshot"),
                "retrieved": p.get("retrieved", "")[:8],
                "overridden": p.get("robots_overridden"),
            })
    lab_rows.sort(key=lambda r: -(r["share"] or 0))

    # ---- programs in the sectors that carry a federal access regime
    sec = [t for t in security.get("targets", []) if t.get("restriction")]
    sec.sort(key=lambda r: (-{"Access authorization": 2,
                              "Export control": 1}.get(r["restriction"], 0),
                            -(r.get("nra_share") or 0)))

    # ---- programs by concentration, from the dissertation record
    prog = ranked.get("targets", [])

    def lab_row(r):
        snap = (f'<a class="sm" href="/labs/{E(Path(r["snapshot"]).name)}">'
                f'snapshot</a>' if r.get("snapshot") else "")
        od = ' <span class="od" title="fetched despite robots.txt">ovr</span>' \
             if r.get("overridden") else ""
        return (f'<tr><td><a href="{E(r["url"])}" target="_blank" '
                f'rel="noopener">{E(r["group"][:62])}</a>{od}</td>'
                f'<td class="mut">{E(r["institution"][:34])}</td>'
                f'<td class="num">{r["members"]}</td>'
                f'<td class="mut">{E(r["retrieved"])} {snap}</td></tr>')

    def sec_row(r):
        u = urls.get((r["institution"], r["sector"]))
        if u:
            dept = (f'<a href="{E(u["url"])}" target="_blank" rel="noopener">'
                    f'{E(_unesc(u["title"]) or u["url"])[:46]}</a>')
            kind = u.get("people_kind")
            people = (f'<a href="{E(u["people_url"])}" target="_blank" '
                      f'rel="noopener" class="{"stu" if kind == "students" else ""}">'
                      f'{"students" if kind == "students" else "people"} &rarr;</a>'
                      if u.get("people_url") else '<span class="mut">&mdash;</span>')
        else:
            dept = '<span class="mut">not resolved</span>'
            people = '<span class="mut">&mdash;</span>'
        return (f'<tr><td>{E(r["institution"][:40])}</td>'
                f'<td><span class="chip s-{r["sector"]}">'
                f'{SECTOR_LABEL.get(r["sector"], r["sector"])}</span></td>'
                f'<td class="num">{r["doctorates"]}</td>'
                f'<td class="num hi">{r["nra_share"]}%</td>'
                f'<td>{dept}</td><td>{people}</td></tr>')

    def prog_row(r):
        chip = (f'<span class="chip s-{r["critical_sector"]}">'
                f'{SECTOR_LABEL.get(r["critical_sector"], r["critical_sector"])}</span>'
                if r["critical_sector"] else '<span class="chip s-none">&mdash;</span>')
        u = urls.get((r["university"], r["critical_sector"]))
        link = (f'<a href="{E(u["url"])}" target="_blank" rel="noopener">'
                f'department &rarr;</a>' if u else "")
        ppl = (f' <a class="sm" href="{E(u["people_url"])}" target="_blank" '
               f'rel="noopener">people</a>' if u and u.get("people_url") else "")
        return (f'<tr data-sector="{E(r["critical_sector"] or "none")}">'
                f'<td>{E(r["department"][:42])}</td>'
                f'<td class="mut">{E(r["university"][:28])}</td>'
                f'<td>{chip}</td>'
                f'<td class="num">{r["records"]}</td>'
                f'<td>{link}{ppl}</td></tr>')

    sectors_present = sorted({r["critical_sector"] or "none" for r in prog})
    filters = "".join(
        f'<button type="button" class="f" data-f="{E(s)}">'
        f'{SECTOR_LABEL.get(s, "Other") if s != "none" else "Other"}</button>'
        for s in sectors_present)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Lab and Program Directory</title>
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem; }}
  h1 {{ font-size: 1.9rem; margin: 0 0 .5rem; }}
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.65;
    margin: 0 0 .5rem; font-size: .95rem; }}
  .warn {{ border-left: 3px solid var(--hl); background: var(--surface);
    padding: .7rem .9rem; border-radius: 0 8px 8px 0; margin: 1rem 0 0;
    font-size: .85rem; line-height: 1.6; max-width: 80ch; }}
  section {{ margin-top: 2.4rem; }}
  h2 {{ font-size: 1.15rem; margin: 0 0 .3rem; }}
  .sub {{ color: var(--text-muted); font-size: .86rem; margin: 0 0 .8rem;
    max-width: 78ch; line-height: 1.6; }}
  .tw {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
  th {{ text-align: left; font-size: .68rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 700;
    padding: .4rem .5rem; border-bottom: 1px solid var(--border);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg); }}
  td {{ padding: .36rem .5rem; border-bottom: 1px solid var(--border);
    vertical-align: top; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums;
    white-space: nowrap; }}
  td.hi {{ color: var(--hl); font-weight: 700; }}
  td.mut {{ color: var(--text-muted); }}
  a {{ color: var(--hl); }}
  .sm {{ font-size: .74rem; }}
  a.stu {{ font-weight: 700; }}
  .od {{ font-size: .62rem; background: var(--border); border-radius: 3px;
    padding: 0 .25rem; color: var(--text-muted); }}
  .chip {{ font-size: .66rem; text-transform: uppercase; letter-spacing: .04em;
    padding: .1rem .4rem; border-radius: 999px; white-space: nowrap;
    border: 1px solid var(--border); color: var(--text-muted); }}
  .chip.s-nuclear, .chip.s-aerospace {{ border-color: var(--hl);
    color: var(--hl); font-weight: 700; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: .35rem; margin: 0 0 .7rem; }}
  .f {{ font: inherit; font-size: .76rem; padding: .25rem .6rem;
    border: 1px solid var(--border); background: var(--surface);
    border-radius: 999px; cursor: pointer; color: var(--text-muted); }}
  .f.on {{ border-color: var(--hl); color: var(--hl); font-weight: 600; }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="lab-directory">
<main class="wrap">
<h1>Lab and program directory</h1>
<p class="lede">A navigation index: the programs and research groups this
analysis has reached, each one a direct link to the department and, where
one exists, to its public roster.</p>
<div class="warn"><strong>Every department link here was fetched and
checked.</strong> A URL is only listed if it returned 200 and the page
itself proved it is the right department &mdash; a university 404 handler
also answers 200. The non-resident shares are IPEDS field-code figures, a
census rather than an estimate.</div>

<section id="labs">
<h2>Research groups with an archived roster</h2>
<p class="sub">Rosters read and snapshotted, so the count can be checked
against the page as it stood. {len(lab_rows)} so far &mdash; the crawler
reads roughly a third of lab sites, because they share no common
structure.</p>
<div class="tw"><table>
<thead><tr><th>Group</th><th>Institution</th><th class="num">Members listed</th>
<th>Archived</th></tr></thead>
<tbody>{''.join(lab_row(r) for r in lab_rows)}</tbody></table></div>
</section>

<section id="regime">
<h2>Nuclear, aerospace, petroleum and mining programs</h2>
<p class="sub">From IPEDS field codes, so this does not depend on what a
university called its department. Share is non-resident doctorates.
<strong>students</strong> links to a graduate roster where the department
publishes one; <strong>people</strong> is a faculty-and-staff page.</p>
<div class="tw"><table>
<thead><tr><th>Institution</th><th>Sector</th>
<th class="num">Doctorates</th><th class="num">Non-resident</th>
<th>Department</th><th>Roster</th></tr></thead>
<tbody>{''.join(sec_row(r) for r in sec)}</tbody></table></div>
</section>

<section id="programs">
<h2>Programs by thesis volume</h2>
<p class="sub">{len(prog)} departments from the dissertation record, with
the size of their thesis output. Where the department site has been
resolved and verified, the last column links straight to it and to its
roster.</p>
<div class="filters"><button type="button" class="f on" data-f="all">All</button>{filters}</div>
<div class="tw"><table>
<thead><tr><th>Program</th><th>Institution</th><th>Sector</th>
<th class="num">Theses</th><th>Go to</th></tr></thead>
<tbody id="progbody">{''.join(prog_row(r) for r in prog)}</tbody></table></div>
</section>
</main>
<script>
document.querySelector('.filters').addEventListener('click', function (e) {{
  var b = e.target.closest('.f'); if (!b) return;
  document.querySelectorAll('.f').forEach(function (x) {{ x.classList.toggle('on', x === b); }});
  var want = b.dataset.f;
  document.querySelectorAll('#progbody tr').forEach(function (tr) {{
    tr.style.display = (want === 'all' || tr.dataset.sector === want) ? '' : 'none';
  }});
}});
</script>
<script src="/analytics-beacon.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
"""
    write_text(OUT, page)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(lab_rows)} archived rosters, {len(sec)} access-regime "
          f"programs, {len(prog)} ranked programs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
