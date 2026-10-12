"""One module per institution, one entry per department.

Every department at every university publishes its people
differently, so this does not try to be a single clever reader. Each
institution gets a file; each department in it gets an entry naming
its directory URL and, where the shared reader fails, its own
function. Refining one department touches one entry.

A module exposes:
    INSTITUTION   the name this site uses for the university
    DEPARTMENTS   key -> {url, field, parse}
    targets()     the directories to walk
    reader_for(url)  that department's own reader, or None

Generated from the directories that answered a probe, then refined by
hand. Re-running the generator preserves any "parse" already written:
see tools/regen_site_parsers.py.
"""
