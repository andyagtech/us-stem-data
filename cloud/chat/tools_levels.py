"""
Degree-level rankings for the chat assistant.

WHY THIS MODULE EXISTS. Every other data tool on this assistant reports
RESEARCH DOCTORATES and only one of them said so. Asked "which university has
the highest non-resident share at master's level", the model reached for
``list_universities``, took the ``nra_site_figure`` -- which is a doctorate
figure, narrow-STEM, pooled 2015-2022 -- and answered "Missouri S&T, 74.3%".
The correct answer is New England College at 98.5%. The number it returned was
real; it was an answer to a different question.

That is the most dangerous failure this project has, because master's and
doctoral populations behave differently and support opposite conclusions: the
master's expansion went 60% to non-residents, while 57% of net new doctorate
places went to citizens and permanent residents. Conflating them discredits
both arguments at once.

So this module gives level-specific questions somewhere correct to go, and the
doctorate-only tools now say what they cover in the payload the model reads
back, not only in a schema description it saw once.

Exports the two names the registry expects:

    SCHEMAS : list of tool schema dicts
    IMPL    : dict tool name -> callable(args: dict) -> dict
"""
from __future__ import annotations

import json
import os

try:                                              # package layout
    from . import data_store as ds
except ImportError:                               # flat Lambda layout
    import data_store as ds

_CACHE: dict | None = None


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        path = os.path.join(ds.DATA_DIR, "level_rankings.json")
        with open(path, encoding="utf-8") as fh:
            _CACHE = json.load(fh)
    return _CACHE


def _fn(name, description, properties, required=None):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required or []}}}


SCHEMAS = [
    _fn(
        "level_rankings",
        "Non-resident share rankings SPLIT BY DEGREE LEVEL -- master's or "
        "doctorate -- for core-STEM completions, pooled over a recent window. "
        "THIS IS THE ONLY TOOL ON THIS ASSISTANT THAT CAN ANSWER A MASTER'S "
        "QUESTION. Every other data tool here reports research doctorates "
        "only, so if a question names master's, or asks which level is higher, "
        "or asks about the expansion in graduate places, call this and not "
        "nra_lookup or list_universities. Returns institutions, 4-digit "
        "programmes, the largest non-resident cohorts, and the "
        "within-institution contrast (two programmes at the same university "
        "far apart in share). Every ranking states the cohort floor it applied "
        "and how many units cleared it; quote the denominator, never a bare "
        "percentage.",
        {
            "level": {"type": "string", "enum": ["masters", "doctorate"],
                      "description": "Which degree level. Required -- there is no "
                                     "default, because guessing it is the bug this "
                                     "tool exists to prevent."},
            "cut": {"type": "string",
                    "enum": ["institutions", "programmes", "biggest", "contrasts"],
                    "description": "institutions = by institution; programmes = by "
                                   "4-digit CIP nationally; biggest = largest "
                                   "non-resident cohorts by count, not share; "
                                   "contrasts = the same university's highest and "
                                   "lowest programme side by side."},
            "limit": {"type": "integer", "description": "1-25, default 10."},
        },
        required=["level"],
    ),
]


def _t_level_rankings(args):
    data = _load()
    level = (args.get("level") or "").strip().lower()
    if level not in ("masters", "doctorate"):
        return {"error": "level must be 'masters' or 'doctorate'. This tool will "
                         "not guess: a doctorate figure quoted as a master's "
                         "figure is the exact error it exists to prevent."}
    cut = (args.get("cut") or "institutions").strip().lower()
    if cut not in ("institutions", "programmes", "biggest", "contrasts"):
        cut = "institutions"
    try:
        limit = max(1, min(25, int(args.get("limit", 10))))
    except (TypeError, ValueError):
        limit = 10

    L = data["levels"][level]
    lo, hi = data["windows"]["late"]
    floors = data["floors"][level]
    label = "master's" if level == "masters" else "doctoral"

    out = {
        "source": (f"IPEDS Completions, core-STEM CIP families "
                   f"{', '.join(data['cip_families'])}, {label} degrees pooled "
                   f"{lo}-{hi}"),
        "scope": (f"{label.upper()} DEGREES ONLY. Do not compare these figures "
                  f"with anything from nra_lookup, list_universities or "
                  f"get_university_facts, which all report research doctorates "
                  f"on a different window and a different basis. The two levels "
                  f"also OVERLAP as populations: a master's graduate may go on to "
                  f"a doctorate at the same institution and be counted in both. "
                  f"Never add a master's count to a doctorate count to get a "
                  f"total number of people \u2014 these are degrees conferred, "
                  f"not individuals."),
        "level": level,
        "window": [lo, hi],
        "national_share": L["national"]["share"],
        "national_counts": {"nra": L["national"]["nra"],
                            "total": L["national"]["total"]},
    }

    if cut == "contrasts":
        out["cut"] = "contrasts"
        out["floor"] = (f"{L['contrast_floor']}+ graduates in EACH of the two "
                        f"programmes")
        out["qualifying"] = L["contrasts_total"]
        out["rows"] = L["contrasts"][:limit]
        out["reading"] = ("The high side is typically computing, analytics and "
                          "engineering; the low side psychology, counselling and "
                          "education. That it tracks work-authorisation pathway "
                          "is a READING, not a finding: IPEDS records which "
                          "degrees were awarded, not who applied or was admitted. "
                          "Say so when you offer it.")
    elif cut == "biggest":
        out["cut"] = "biggest"
        out["floor"] = "none -- ranked by absolute non-resident count"
        out["rows"] = L["biggest"][:limit]
    else:
        key = "institutions" if cut == "institutions" else "programmes"
        out["cut"] = key
        out["floor"] = (f"{floors['inst' if key == 'institutions' else 'prog']}+ "
                        f"{label} degrees over {lo}-{hi}")
        out["qualifying"] = L[f"{key}_eligible"]
        out["rows"] = L[key][:limit]
        out["caution"] = ("A share is a ratio: always quote it with its "
                          "denominator, which is on every row.")
    return out


IMPL = {"level_rankings": _t_level_rankings}
