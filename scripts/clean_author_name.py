#!/usr/bin/env python3
"""Strip catalogue junk from an author name, and nothing else.

THE PAGES THIS AFFECTS ARE THE ONES THAT GET SHARED. The thesis and
dissertation lists are the most persuasive thing on this site, because they
are real people and real titles rather than a number. A mangled name on those
pages costs more than a mangled number elsewhere.

WHAT THE JUNK IS. Some repositories put the degree and the awarding
institution inside the author field, so the harvest faithfully recorded names
like:

    Chen, Hongge,Ph. D.Massachusetts Institute of Technology.
    Dai, Siyu(Scientist in mechanical engineering) Massachusetts Institute...
    Holloway, Jack Wade,1980-

THE TRAP, AND IT IS THE SAME ONE THIS REPO ALREADY FELL INTO ONCE. A first
pass stripped any ', S. M.' or ', M. Eng.' it found. That turned

    Mahmud, S. M. Naziur        into   Mahmud Naziur
    Islam, S. M. Zakirul        into   Islam Zakirul

because S. M. is a given name in Bangladeshi and other South Asian naming,
not a Master of Science. The cleaner destroyed real names to tidy catalogue
noise, which is the ACADEMY mistake in a different file.

SO A DEGREE IS ONLY A DEGREE WHEN IT TERMINATES THE NAME. A credential token
is stripped only where it sits at the end of the string, or immediately
before an institution name. A token with more name after it is part of the
name and is left alone. When in doubt the name is left exactly as the
repository recorded it, because an untidy real name beats a tidy wrong one.
"""
from __future__ import annotations

import re

#: Institutions that appear glued to the end of an author field.
INSTITUTION = re.compile(
    r"\s*,?\s*(Massachusetts Institute of Technology"
    r"|The University of Texas at Austin"
    r"|University of Texas at Austin)\s*\.?\s*", re.I)

#: A credential, only where the name has ended, and only where the token
#: cannot be read as initials. Case-sensitive on the letters so 'Meng' -- a
#: common Chinese given name -- can never read as 'M.Eng'.
#:
#: DELIBERATELY ABSENT: M.S., M.A., B.S., S.M., B.A. Every one of those is
#: shaped exactly like a pair of middle initials and cannot be told apart
#: from one without knowing the person. Including them turned
#:     Moussa, Alfred M. S.   into  Moussa, Alfred
#:     Oteafy, Ahmed M. A.    into  Oteafy, Ahmed
#:     Mahmud, S. M. Naziur   into  Mahmud Naziur
#: so a few hundred untidy credentials survive on the page. That is the
#: right trade: this list is the most-shared thing on the site and a wrong
#: name discredits it in a way a trailing 'M.S.' never will.
DEGREE_AT_END = re.compile(
    r",?\s*(Ph\.\s?D\.|M\.\s?Eng\.|Sc\.\s?D\.|M\.\s?B\.\s?A\."
    r"|Ed\.\s?D\.|D\.\s?Sc\.|D\.\s?Phil\.)"
    r"\s*\.?\s*$")

#: A department, where the cataloguer appended the awarding unit to the name:
#: 'Yang, Yang,Ph. D. Department of Electrical Engineering and Computer
#: Science.' Only matched after a degree token or at the very end, so an
#: author genuinely called 'Department' -- there is none -- would survive.
DEPARTMENT_TAIL = re.compile(
    r",?\s*(Ph\.\s?D\.|Sc\.\s?D\.|M\.\s?Eng\.)?\s*"
    r"(Department|Dept\.?|School|Division|Program|Center|Centre)\s+of\s+"
    r"[A-Z][^,]*\.?\s*$")

#: An occupational gloss the cataloguer added to disambiguate two authors.
GLOSS = re.compile(r"\s*\(\s*(Scientist|Professor|Engineer|Lecturer|Research"
                   r"|Student|Associate)\b[^)]*\)", re.I)

#: A life-dates suffix: 'Holloway, Jack Wade,1980-' or ',1942-2011'.
LIFE_DATES = re.compile(r",\s*\d{4}\s*-\s*\d{0,4}\s*\.?\s*$")


def clean_author_name(name: str) -> str:
    """Return the name with catalogue junk removed, or unchanged if unsure."""
    if not isinstance(name, str) or not name.strip():
        return name
    out = name

    #: Institution first: it is unambiguous, and removing it often exposes a
    #: degree token that is now genuinely terminal.
    out = INSTITUTION.sub(" ", out)
    out = GLOSS.sub("", out)
    out = DEPARTMENT_TAIL.sub("", out)
    out = LIFE_DATES.sub("", out)

    #: Then credentials, repeatedly, but only ever at the very end.
    for _ in range(3):
        stripped = DEGREE_AT_END.sub("", out)
        if stripped == out:
            break
        out = stripped

    out = re.sub(r"\s{2,}", " ", out).strip()
    out = out.rstrip(",.").strip() if out.endswith((",", ".,")) else out.strip()
    #: Never return an empty name or a bare comma -- fall back to the original.
    return out if out and out not in {",", "-"} else name
