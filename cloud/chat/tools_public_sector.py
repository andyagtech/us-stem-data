"""
Public-sector PERM filings for the chat assistant.

WHY THIS MODULE EXISTS. Asked which Washington state agencies had sponsored
foreign workers and where those workers were from, the assistant answered that
the PERM files do not record nationality. They do -- citizenship and country of
birth, FY2013 to FY2024 -- and it is the only federal disclosure file in this
project that does. Given a knowledge file saying so, the model then answered
the same question with "87 certified filings", which is the NATIONAL total.
Washington has six.

Both failures have the same cause: prose can tell the model that a figure
exists, but only a tool can hand it the right one. A knowledge file carrying a
headline total and a reader asking about one state is a trap, because the
headline is the only number in reach.

So this module gives state questions somewhere correct to go, and every
payload names its own scope -- "national" or the state -- in the data the model
reads back, not only in a schema description it saw once.

Exports the two names the registry expects:

    SCHEMAS : list of tool schema dicts
    IMPL    : dict tool name -> callable(args: dict) -> dict
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_CACHE: dict | None = None

PAGE = "/public-sector-visas"

#: Both spellings, so a model that says "WA" and a reader who says "Washington"
#: reach the same state. The data is keyed on the full name.
_ABBR = {
    "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS",
    "CA": "CALIFORNIA", "CO": "COLORADO", "CT": "CONNECTICUT",
    "DE": "DELAWARE", "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA",
    "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO", "IL": "ILLINOIS",
    "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS", "KY": "KENTUCKY",
    "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND",
    "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA",
    "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA",
    "NE": "NEBRASKA", "NV": "NEVADA", "NH": "NEW HAMPSHIRE",
    "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK",
    "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO",
    "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA",
    "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA",
    "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH", "VT": "VERMONT",
    "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
    "WI": "WISCONSIN", "WY": "WYOMING", "PR": "PUERTO RICO",
    "GU": "GUAM", "VI": "VIRGIN ISLANDS",
    "MP": "NORTHERN MARIANA ISLANDS", "AS": "AMERICAN SAMOA",
}

#: Repeated on every payload. The model reads this back; a schema description
#: it saw once does not survive into the answer.
_SCOPE_NOTE = (
    "A PERM filing is an employer asking for permission to sponsor permanent "
    "residence. It is not a hire, not a visa and not a green card. Nothing "
    "here says any employer or worker broke a rule."
)
_WINDOW_NOTE = (
    "FY2013-FY2024 only. The Department of Labor removed citizenship, country "
    "of birth and class of admission from the FY2025 file onward, so this "
    "series has ended and cannot be brought up to date."
)


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        here = Path(__file__).resolve().parent
        for cand in (here / "chat_data" / "public_employer_perm_compact.json",
                     Path(os.environ.get("CHAT_DATA_DIR", "chat_data"))
                     / "public_employer_perm_compact.json"):
            if cand.exists():
                _CACHE = json.loads(cand.read_text())
                break
        else:
            _CACHE = {}
    return _CACHE


def _resolve(name: str) -> str | None:
    v = " ".join(str(name or "").upper().split())
    if not v:
        return None
    if v in _ABBR:
        return _ABBR[v]
    return v if v in (_load().get("by_state_detail") or {}) else None


def _t_overview(args: dict) -> dict:
    """National totals and the shape of each sector."""
    d = _load()
    if not d:
        return {"error": "The public-sector PERM data is not in this bundle."}
    secs, dist = d.get("sectors", {}), d.get("distributions", {})
    out = {}
    for key, s in secs.items():
        di = dist.get(key, {})
        w, pe = di.get("wage", {}), di.get("filings_per_employer", {})
        cit = s.get("citizenship") or {}
        out[key] = {
            "filings": s.get("filings"),
            "employers": pe.get("employers"),
            "median_wage_offered": w.get("median"),
            "top_citizenships": sorted(cit.items(), key=lambda kv: -kv[1])[:5],
            "share_from_ten_busiest_employers_pct": pe.get("top10_share"),
        }
    return {
        "scope": "national",
        "window": d.get("window"),
        "total_filings": d.get("public_rows"),
        "sectors": out,
        "flagged_by_each_test": d.get("anomaly_totals"),
        "page": PAGE,
        "caveat": _SCOPE_NOTE,
        "window_note": _WINDOW_NOTE,
        "note": ("These are NATIONAL figures. For one state call "
                 "public_sector_by_state; do not quote a national total as a "
                 "state's own."),
    }


def _t_by_state(args: dict) -> dict:
    """One state's own figures, and every state-agency filing in it."""
    d = _load()
    if not d:
        return {"error": "The public-sector PERM data is not in this bundle."}
    raw = args.get("state") or ""
    st = _resolve(raw)
    detail = d.get("by_state_detail") or {}
    if not st or st not in detail:
        return {"error": f"No public-sector PERM data for {raw!r}.",
                "states_available": sorted(detail)}
    v = detail[st]
    sectors = {
        k: {"filings": s.get("filings"),
            "employers": s.get("employers"),
            "median_wage_offered": s.get("median_wage"),
            "top_employers": (s.get("top_employers") or [])[:8],
            "top_citizenships": sorted((s.get("citizenship") or {}).items(),
                                       key=lambda kv: -kv[1])[:8]}
        for k, s in (v.get("sectors") or {}).items()
    }
    agency = v.get("agency_filings") or []
    out = {
        "scope": st.title(),
        "window": d.get("window"),
        "filings_in_this_state": v.get("filings"),
        "sectors": sectors,
        #: Every one of them, not a sample. There are 87 in the country.
        "state_agency_filings": [
            {k: r.get(k) for k in
             ("fiscal_year", "employer", "job_title", "city", "citizenship",
              "birth_country", "visa_held", "wage", "decided", "source_file",
              "case_number")}
            for r in agency],
        "page": PAGE + "#state-" + st.replace(" ", "-"),
        "caveat": _SCOPE_NOTE,
        "window_note": _WINDOW_NOTE,
    }
    if not agency:
        #: An absence is a result, and it must be stated as one. Left to
        #: itself the model reads an empty list as "I could not find it" and
        #: reaches for the national figure instead.
        out["state_agency_filings_note"] = (
            f"No agency of the {st.title()} state government filed a certified "
            f"PERM case in this window. That is a finding, not missing data: "
            f"the files were read and this state is not in them.")
    return out


SCHEMAS = [
    {"type": "function", "function": {
        "name": "public_sector_overview",
        "description": (
            "NATIONAL totals for permanent-residence (PERM) filings by "
            "universities, school districts and state agencies, FY2013-FY2024, "
            "including the workers' citizenships. Use for 'how many', 'which "
            "sector', 'what do these jobs pay'. For one state use "
            "public_sector_by_state instead."),
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "public_sector_by_state",
        "description": (
            "ONE STATE's permanent-residence (PERM) filings by universities, "
            "school districts and state agencies, with the workers' "
            "citizenship and country of birth, and every state-agency filing "
            "in that state listed in full. Use whenever a question names a "
            "state. Never answer a state question with the national total."),
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string",
                      "description": "State name or two-letter code, "
                                     "e.g. 'Washington' or 'WA'."}},
            "required": ["state"]}}},
]

IMPL = {
    "public_sector_overview": _t_overview,
    "public_sector_by_state": _t_by_state,
}
