"""
Central configuration for the screening engine.

Everything that a reviewer might want to tune - decision bands, signal weights,
and the text-normalisation lookup tables - lives here so it is easy to find and
change in one place (no magic numbers scattered through the code).
"""

# --------------------------------------------------------------------------- #
# File locations (relative to the project root; run uvicorn from there)
# --------------------------------------------------------------------------- #
MASTER_CSV_PATH = "data/duplicate_vendor_dummy_data.csv"
DECISIONS_LOG_PATH = "data/decisions_log.csv"

# --------------------------------------------------------------------------- #
# Decision bands (Novo deck slide 12)
#   85-100 -> Likely duplicate   (HIGH)
#   65-84  -> Human review       (MEDIUM)
#   <65    -> Likely new         (LOW)
# --------------------------------------------------------------------------- #
HIGH_THRESHOLD = 85.0
MEDIUM_THRESHOLD = 65.0
MIN_REPORT_THRESHOLD = 40.0        # below this, a candidate is not reported at all

# A candidate must be at least this name-similar (or an exact ID match) to be
# surfaced from the internal master. Raised from 0.55 -> 0.62 so gibberish
# input no longer produces weak "ghost" candidates.
INTERNAL_NAME_MIN = 0.62


def confidence_level(pct: float) -> str:
    if pct >= HIGH_THRESHOLD:
        return "HIGH"
    if pct >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def decision_label(pct: float) -> str:
    if pct >= HIGH_THRESHOLD:
        return "Likely duplicate"
    if pct >= MEDIUM_THRESHOLD:
        return "Human review"
    return "Likely new"


# Maps the three UI buttons to their audit-log labels.
DECISION_LABELS = {
    "reuse": "Reuse existing",
    "review": "Send to review",
    "create": "Create new",
}

# --------------------------------------------------------------------------- #
# Internal weighted-evidence model
# --------------------------------------------------------------------------- #
COLS = ["name_similarity", "country_similarity", "country_match",
        "city_similarity", "website_similarity"]
WEIGHTS = {"name_similarity": .50, "country_similarity": .20, "country_match": .10,
           "city_similarity": .10, "website_similarity": .10}
# Ranges used to synthesise the (secondary) ML classifier's training data.
POS_RANGES = {"name_similarity": (.75, 1), "country_similarity": (.85, 1),
              "city_similarity": (.7, 1), "website_similarity": (.5, 1)}
NEG_RANGES = {"name_similarity": (0, .7), "country_similarity": (0, .8),
              "city_similarity": (0, 1), "website_similarity": (0, .55)}
BINARY_COLS = {"country_match"}
POS_P = {"country_match": .85}
NEG_P = {"country_match": .35}

# --------------------------------------------------------------------------- #
# Text-normalisation tables
# --------------------------------------------------------------------------- #
COUNTRY_ALIASES = {
    "uk": "united kingdom", "u.k.": "united kingdom", "united kingdom": "united kingdom",
    "uae": "united arab emirates", "u.a.e.": "united arab emirates",
    "united arab emirates": "united arab emirates",
    "us": "united states", "u.s.": "united states", "usa": "united states",
    "u.s.a.": "united states", "united states": "united states",
    "united states of america": "united states",
}

# Words dropped before fuzzy NAME comparison (legal suffixes + generic business
# descriptors). Keeping these would make unrelated companies look similar.
STOP_WORDS = {
    "ltd", "ltd.", "limited", "pvt", "private", "inc", "inc.", "incorporated",
    "llc", "llp", "co", "co.", "company", "corp", "corporation", "gmbh", "group",
    "and", "technologies", "solutions", "services", "systems", "the",
}

# A NARROWER list used only when building an acronym. Descriptive words such as
# "services"/"technologies" are often part of the acronym itself (TCS = Tata
# Consultancy Services), so acronym-building strips only pure legal suffixes.
LEGAL_SUFFIX_WORDS = {
    "ltd", "ltd.", "limited", "pvt", "private", "inc", "inc.", "incorporated",
    "llc", "llp", "co", "co.", "company", "corp", "corporation", "gmbh", "the", "and",
}

# GLEIF needs an ISO 3166-1 alpha-2 code, not free text.
COUNTRY_ISO2 = {
    "india": "IN", "united states": "US", "usa": "US", "us": "US",
    "united kingdom": "GB", "uk": "GB", "germany": "DE", "france": "FR",
    "china": "CN", "japan": "JP", "singapore": "SG", "united arab emirates": "AE",
    "uae": "AE", "netherlands": "NL", "switzerland": "CH", "australia": "AU",
    "canada": "CA", "brazil": "BR", "italy": "IT", "spain": "ES", "ireland": "IE",
    "denmark": "DK", "sweden": "SE", "norway": "NO", "poland": "PL",
    "mexico": "MX", "south africa": "ZA", "south korea": "KR", "korea": "KR",
    "philippines": "PH", "malaysia": "MY", "indonesia": "ID", "thailand": "TH",
    "vietnam": "VN", "hong kong": "HK", "belgium": "BE", "austria": "AT",
    "portugal": "PT", "finland": "FI", "israel": "IL", "turkey": "TR",
    "russia": "RU", "new zealand": "NZ", "saudi arabia": "SA", "egypt": "EG",
    "nigeria": "NG", "argentina": "AR", "colombia": "CO", "czech republic": "CZ",
}

# --------------------------------------------------------------------------- #
# External services
# --------------------------------------------------------------------------- #
GLEIF_BASE = "https://api.gleif.org/api/v1"
GLEIF_TIMEOUT = 6
GLEIF_CACHE_TTL = 3600          # seconds
WEB_CACHE_TTL = 3600            # seconds
GLEIF_MAX_WORKERS = 10          # concurrent parent-lookup threads
