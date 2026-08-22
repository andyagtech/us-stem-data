# Employer Entity Resolution Notes

## Problem
Universities file H-1B/LCA/PERM under different legal entity names that change over time
and don't always match to a single campus. This needs systematic handling in the data pipeline.

## Known Multi-Campus Systems (single employer name, multiple campuses)
- "THE CURATORS OF THE UNIVERSITY OF MISSOURI" → covers U Missouri, Missouri S&T, UMKC, UMSL
- "UNIVERSITY OF CALIFORNIA" → need campus suffix (Berkeley, LA, SD, etc.)
- "STATE UNIVERSITY OF NEW YORK" → covers Stony Brook, Buffalo, Binghamton, etc.
- "UNIVERSITY OF ILLINOIS" → covers UIUC, UIC, UIS

## Known Name Variants (same university, different H-1B names)
- Virginia Tech: "VIRGINIA POLYTECHNIC INST & STATE UNIV", "VIRGINIA POLYTECHNIC INSTITUTE AND STATE UNIVERSITY", "VIRGINIA TECH"
- Penn State: "PENN STATE UNIVERSITY", "PENNSYLVANIA STATE UNIVERSITY", "THE PENNSYLVANIA STATE UNIVERSITY"
- Ohio State: "OHIO STATE UNIVERSITY", "THE OHIO STATE UNIVERSITY"
- Iowa State: "IOWA STATE UNIVERSITY", "IOWA STATE UNIVERSITY OF SCIENCE AND TECHNOLOGY"

## H-1B Data Hub vs LCA Naming
- H-1B Data Hub (USCIS): Uses employer name as registered
- LCA Disclosure (DOL): Uses employer name from the LCA filing — may differ
- Both are official government data but employer name standardization differs

## Future Pipeline Solution
Build an entity_map.json with:
```json
{
  "THE CURATORS OF THE UNIVERSITY OF MISSOURI": ["umissouri", "missouri_st"],
  "STATE UNIVERSITY OF NEW YORK AT BINGHAMTON": ["binghamton"],
  "UNIVERSITY OF NEVADA LAS VEGAS": ["unlv"],
  ...
}
```
With proportional splitting for multi-campus systems where needed.

## Name variants found 2026-08-22

Five registry universities matched **zero** LCA rows while appearing in H-1B,
PERM and OPT. Every H-1B petition requires a certified LCA first, so zero was
impossible: DOL simply files them under a different employer name. Scanning
`lca_FY2025_Q2.xlsx` for the actual strings:

| university | DOL employer name | filings in that quarter |
|---|---|---|
| `utaustin` | `THE UNIVERSITY OF TEXAS AT AUSTIN` | 69 |
| `bu` | `TRUSTEES OF BOSTON UNIVERSITY` | 58 |
| `rice` | `W.M. RICE UNIVERSITY` | 36 |
| `rice` | `W.M. RICE UNIVERSISTY` | 1 — DOL's own typo |
| `montana_state` | `MONTANA STATE UNIVERSITY` | 8 (no pattern existed at all) |

All added to `entity_map.json`. The match is exact on the trimmed, upper-cased
name, so a variant has to be listed to count — that strictness is deliberate,
and is what stopped the three-letter `MIT` pattern sweeping in INFOSYS LIMITED.
New patterns are additive and cannot broaden an existing one.

### cu_boulder is deliberately NOT mapped

DOL's Colorado employers are:

```
47  UNIVERSITY OF COLORADO
35  UNIVERSITY OF COLORADO DENVER
 2  UNIVERSITY OF COLORADO, DENVER
 2  UNIVERSITY OF COLORADO HEALTH
```

The bare `UNIVERSITY OF COLORADO` is the **system**, covering Boulder, Denver,
Colorado Springs and Anschutz. Mapping it to `cu_boulder` would credit one
campus with the whole system's filings — the same over-attribution that made
MIT's total 565,883. Boulder therefore shows no LCA data rather than a wrong
number. Resolving it needs a campus-level source, or the `h1b_system_note`
mechanism used elsewhere for system-level figures.
