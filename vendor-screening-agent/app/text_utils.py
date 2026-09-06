"""
Text-normalisation and comparison helpers.

These are the small, pure, well-tested building blocks the scoring engine relies
on: name cleaning/tokenising, country normalisation, acronym detection, and the
containment penalty that prevents "Infosys" from matching "Capital Infosys".
"""
from typing import Set

import pandas as pd
from rapidfuzz import fuzz

from .config import (
    COUNTRY_ALIASES, COUNTRY_ISO2, STOP_WORDS, LEGAL_SUFFIX_WORDS,
)


def norm(x) -> str:
    """Lower-case, collapse whitespace, and expand '&' to 'and'."""
    return " ".join(str(x or "").lower().replace("&", " and ").split())


def ncountry(x) -> str:
    k = str(x or "").strip().lower()
    return COUNTRY_ALIASES.get(k, k)


def gleif_country_code(country_text) -> str:
    """Free-text country -> ISO-2 code (or '' if unknown)."""
    return COUNTRY_ISO2.get(str(country_text or "").strip().lower(), "")


def _iso2(x) -> str:
    """
    Normalise a country to an ISO-2 code when possible, so 'India' and the 'IN'
    that GLEIF returns compare as EQUAL. (Without this, 'India' vs 'IN' scored a
    stuck ~57% and dragged country evidence down.)
    """
    s = str(x or "").strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    code = COUNTRY_ISO2.get(s.lower())
    return (code or ncountry(s)).upper()


def country_sim(a, b) -> float:
    ca, cb = _iso2(a), _iso2(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    return fuzz.token_set_ratio(ca, cb) / 100


def gv(o, name, default=""):
    """Read a field off a Pydantic model, a plain dict, or a pandas row."""
    val = o.get(name, default) if hasattr(o, "get") else getattr(o, name, default)
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val if val not in (None, "") else default


def name_tokens(s) -> Set[str]:
    """Distinctive tokens of a name (stop words / legal suffixes removed)."""
    return set(
        w.strip(".,") for w in norm(s).split()
        if w.strip(".,") and w.strip(".,") not in STOP_WORDS
    )


def name_core(s) -> str:
    """A canonical, order-independent form used for fuzzy comparison."""
    core = " ".join(sorted(name_tokens(s)))
    return core or norm(s)


def ordered_name_words(s):
    """Ordered words used only for acronym building (keeps descriptive words)."""
    return [
        w.strip(".,") for w in norm(s).replace(".", " ").split()
        if w.strip(".,") and w.strip(".,") not in LEGAL_SUFFIX_WORDS
    ]


def acronym_of(s) -> str:
    return "".join(w[0] for w in ordered_name_words(s) if w).upper()


def looks_like_acronym(s) -> bool:
    raw = "".join(ch for ch in str(s) if ch.isalpha())
    return len(ordered_name_words(s)) <= 1 and 2 <= len(raw) <= 6


def acronym_similarity(a, b) -> float:
    """Catch abbreviation<->expansion pairs: IBM <-> International Business Machines."""
    for short, long in ((a, b), (b, a)):
        if looks_like_acronym(short):
            sac = "".join(ch for ch in str(short) if ch.isalpha()).upper()
            if len(sac) >= 2 and sac == acronym_of(long):
                return 1.0
    return 0.0


def first_core_token(s) -> str:
    """First distinctive word of a name, skipping pure legal words like 'the'."""
    for w in (x.strip(".,") for x in norm(s).split()):
        if w and w not in LEGAL_SUFFIX_WORDS:
            return w
    return ""


def containment_penalty(a, b) -> float:
    """
    Damp the name score when one name is really just the other plus a DIFFERENT
    leading qualifier - the 'Capital Infosys' vs 'Infosys' false-positive pattern.

    Returns 1.0 (no penalty) for genuine brand/legal variants that share the same
    head word ('Cognizant' vs 'Cognizant Technology Solutions'), for word-order
    and spelling variants, and whenever there is nothing distinctive to compare.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 1.0
    inter = ta & tb
    if not inter or len(ta) == len(tb):
        return 1.0
    smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not smaller.issubset(larger):
        return 1.0                       # not pure containment -> leave to fuzzy score
    if first_core_token(a) == first_core_token(b):
        return 1.0                       # same head word -> same brand, extra descriptors
    return len(inter) / len(ta | tb)     # different leading qualifier -> different entity
