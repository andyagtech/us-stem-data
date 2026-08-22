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
