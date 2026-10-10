#!/usr/bin/env python3
"""Turn a federal employer string into something a person can read.

The disclosure files store employer names SHOUTED IN CAPITALS, as typed by
whoever filled the form. Python's str.title() is not the answer, and the
site used it in eight places:

  LOVE'S TRAVEL STOPS   -> Love'S Travel Stops     apostrophe capitalised
  JASANI'S INTERNATIONAL-> Jasani'S International  same
  PILOT TRAVEL CENTERS LLC -> Pilot Travel Centers Llc
  JOC, INC. DBA HOT SPOT   -> Joc, Inc. Dba Hot Spot
  FRENCHMANS CREEK INC &AMP; SUBSIDIARY            an escaped entity,
                                                   escaped a second time

So: title-case on word boundaries that are not apostrophes, drop the
corporate suffix, uppercase the initialisms that mean something, and undo
the double-escaping.

THE SUFFIX IS DROPPED, NOT HIDDEN. "Inc" and "Llc" carry no information a
reader of this site needs -- every filer is a company. But two filers can
differ ONLY by suffix ("Pilot Travel Centers Llc" and "Pilot Travel
Centers, Llc" are two separate rows in the federal files), so dropping the
suffix must never be used to MERGE rows. Use pretty() for display and the
raw string for identity.
"""
from __future__ import annotations

import html
import re

#: Dropped from the end of a name. Only at the end, so "Inc Magazine"
#: survives and "Pilot Travel Centers Inc." does not keep its tail.
SUFFIXES = {
    "inc", "inc.", "incorporated", "llc", "l.l.c.", "llc.", "l.l.c",
    "ltd", "ltd.", "limited", "corp", "corp.", "corporation",
    "co", "co.", "company", "plc", "lp", "l.p.", "llp", "l.l.p.",
    "pc", "p.c.", "pa", "p.a.", "pllc", "p.l.l.c.",
}

#: Kept in capitals. These are initialisms, not words.
UPPER = {
    "dba", "usa", "us", "uk", "it", "hr", "ai", "id",
    "rv", "tv", "pc", "us.", "ii", "iii", "iv", "vi", "vii", "viii",
    "ix", "xi", "xii", "hvac", "cpa", "md", "dds", "dvm", "cnc",
    "atm", "gps", "led", "pvc", "hr.", "r&d", "qa", "ui", "ux",
}

#: Real short words. Everything else of three letters or fewer is an
#: initialism in this corpus -- GDI, TFL, HES, SC -- and reads wrong in
#: title case. This list is what stops "Hot Spot" becoming "HOT SPOT".
SHORT_WORDS = {
    "the", "and", "for", "air", "oil", "gas", "new", "old", "big", "top",
    "sun", "key", "bay", "box", "car", "cab", "bus", "van", "inn", "spa",
    "pet", "toy", "eye", "ear", "law", "tax", "job", "day", "sea", "red",
    "hot", "ice", "joy", "one", "two", "six", "ten", "all", "our", "pro",
    "net", "web", "lab", "bio", "eco", "max", "mid", "sky", "art", "bar",
    "pub", "gym", "spc", "son", "bro", "pie", "tea", "egg", "nut", "oak",
    "elm", "bee", "fox", "cow", "pig", "dog", "cat", "hen", "ram", "owl",
    "fit", "run", "ski", "sew", "cut", "dry", "wet", "hub", "way", "end",
    "sub", "ltd", "mfg", "ave", "rd", "st", "dr", "ln", "ct", "pl", "pk",
    "of", "at", "in", "on", "to", "by", "or", "an", "a", "as", "is", "it",
    "up", "no", "so", "we", "my", "go", "do", "be", "he",
    #: Place-name particles. Short, real words, and common in US names:
    #: Los Angeles, Las Vegas, San Jose, De Soto, Rio Rancho.
    "los", "las", "la", "de", "del", "san", "rio", "el", "du", "da",
    #: Abbreviations that are read as words, not spelled out. They reach
    #: here with their period already stripped for comparison.
    "st", "mt", "ft", "jr", "sr", "no", "ave", "blvd", "rte", "hwy",
    "bros", "assn", "mgmt", "svcs", "intl", "natl", "univ", "dept",
}

#: Kept in lower case inside a name, never at the start.
#: "de", "la" and "los" are left OUT deliberately: in this corpus they
#: are nearly always part of a US place name ("The Los Angeles Country
#: Club", "De Soto"), not a grammatical particle, and lower-casing them
#: produced "The los Angeles Country Club".
LOWER = {"of", "and", "the", "for", "at", "in", "on", "to", "a", "an",
         "or", "by", "van", "von"}


def _word(w: str, first: bool, upper_context: bool = False) -> str:
    """Title-case one word, leaving what follows an apostrophe alone."""
    low = w.lower()
    if low in UPPER:
        return low.upper()
    #: A short token that is not a real word is an initialism.
    #: Compare on LETTERS ONLY. "st." did not match "st" in SHORT_WORDS,
    #: so it fell through to the initialism rule and
    #: "Washington University in St. Louis" came out "in ST. Louis".
    #: Same for Mt., No., Jr., Dr. -- 70 names in this corpus.
    letters = re.sub(r"[^a-z]", "", low)
    if letters in SHORT_WORDS and low not in UPPER:
        #: SHORT_WORDS says "this is a real word, not an initialism", so
        #: it is Title Case. LOWER is the separate, smaller set of
        #: grammatical particles that stay lower inside a name, and it
        #: is handled below.
        if letters in LOWER and not first:
            return low
        return low[:1].upper() + low[1:]
    if low in SUFFIXES or letters in ("inc", "llc", "ltd", "corp", "co"):
        #: A suffix that survived the strip sits mid-string. In running
        #: words -- "Frenchmans Creek Inc & Subsidiary" -- it reads as a
        #: word. Inside a parenthetical of initialisms -- "(D/B/A SEC
        #: FLORIDA LLC)" -- it reads as one of them. Keep the case the
        #: name itself is in.
        #: Rebuild around the letters so punctuation survives. Returning
        #: `letters` alone ate the closing bracket of
        #: "(D/B/A SEC FLORIDA LLC)".
        body = letters.upper() if upper_context else letters.capitalize()
        return re.sub(r"[a-z]+", body, low, count=1)
    if 0 < len(letters) <= 3 and low not in SHORT_WORDS and low not in LOWER:
        return low.upper()
    if low in LOWER and not first:
        return low
    #: Capitalise the first letter of each apostrophe-free run, so
    #: "love's" -> "Love's" and "o'brien" -> "O'Brien". The rule differs
    #: by position: a letter right after an apostrophe is part of the
    #: same word ("Love's"), unless the run is longer than one letter,
    #: which is a real name particle ("O'Brien").
    #: Capitalise the first LETTER, not the first character: a word that
    #: opens with a bracket or quote -- "(holdings" -- otherwise keeps
    #: its lower case because the bracket absorbed the upper().
    def cap(t: str) -> str:
        return re.sub(r"[a-z]", lambda m: m.group(0).upper(), t, count=1)

    parts = low.split("'")
    out = [cap(parts[0])]
    for seg in parts[1:]:
        out.append(cap(seg) if len(seg) > 1 else seg)
    s = "'".join(out)
    #: "T-TECH" -> "T-Tech", not "T-tech". A hyphen joins two words.
    return re.sub(r"(?<=-)([a-z])", lambda m: m.group(1).upper(), s)


def pretty(name: str, keep_suffix: bool = False) -> str:
    """A display form of a federal employer string."""
    if not name:
        return ""
    #: The files contain raw ampersands AND pre-escaped ones. Unescape
    #: twice so "&AMP;" and "&amp;amp;" both land on "&"; the renderer
    #: escapes once on the way out.
    s = html.unescape(html.unescape(str(name))).strip()
    s = re.sub(r"\s+", " ", s)

    if not keep_suffix:
        #: Strip trailing suffixes repeatedly: "FOO INC., LLC" has two.
        #: Never strip down to nothing -- a filer literally named "LLC"
        #: keeps its name.
        for _ in range(3):
            #: Only strip a suffix at the real end. A name ending in a
            #: bracket -- "... (D/B/A SEC FLORIDA LLC)" -- had its LLC
            #: taken and the closing bracket left behind.
            m = re.search(r"[,\s]+([A-Za-z.]+)\s*$", s)
            if not m or m.group(1).lower() not in SUFFIXES:
                break
            trimmed = s[: m.start()].rstrip(" ,.")
            if trimmed.count("(") != trimmed.count(")"):
                break
            if not trimmed:
                break
            s = trimmed

    if not keep_suffix:
        #: "JOC, INC. DBA HOT SPOT" carries its suffix in the middle, so
        #: the trailing strip above never sees it.
        s = re.sub(r"[,\s]+(?:inc\.?|llc\.?|l\.l\.c\.?|corp\.?|ltd\.?|"
                   r"co\.|incorporated|corporation|limited)"
                   r"(?=[,\s]+(?:dba|d/b/a)\b)", "", s, flags=re.I)

    words = s.split(" ")
    #: A token sits in an "upper context" when its neighbours are
    #: initialisms, which is how "(D/B/A SEC FLORIDA LLC)" keeps its LLC
    #: while "Frenchmans Creek Inc & Subsidiary" does not.
    def near_upper(i: int) -> bool:
        for j in (i - 2, i - 1, i + 1, i + 2):
            if 0 <= j < len(words):
                t = re.sub(r"[^a-z]", "", words[j].lower())
                if 1 < len(t) <= 4 and t not in SHORT_WORDS and t not in LOWER \
                        and t not in SUFFIXES:
                    return True
        return False

    out = [_word(w, i == 0, near_upper(i)) for i, w in enumerate(words)]
    s = " ".join(out)

    #: A suffix mid-name is a word ("Frenchmans Creek Inc & Subsidiary"),
    #: but a suffix the caller asked to KEEP is the legal form and reads
    #: as an initialism, as does a filer whose entire name is one.
    if keep_suffix or len(words) == 1:
        s = re.sub(r"\b(Llc|Inc|Ltd|Plc|Llp|Pllc|Lp|Pc|Pa)\b\.?\s*$",
                   lambda m: m.group(1).upper() + m.group(0)[len(m.group(1)):],
                   s)
    #: "Joc, Dba Hot Spot" reads better without the orphaned comma the
    #: dropped suffix left behind.
    s = re.sub(r",\s*(DBA)\b", r" \1", s)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    return s
