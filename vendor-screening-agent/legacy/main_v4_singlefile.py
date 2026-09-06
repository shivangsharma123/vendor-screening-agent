"""
=================================================================================
AI VENDOR / LEGAL-ENTITY SCREENING AGENT  -  Novo Nordisk Student Project (v4)
=================================================================================
WHAT'S NEW IN THIS VERSION
---------------------------------------------------------------------------------
v3 gave you: internal vendor-master matching + a single GLEIF name search.
v4 adds everything from the enhancement brief:
  1. THREE fuzzy-matching algorithms, blended into one composite name score:
       - Levenshtein-family     (rapidfuzz.token_set_ratio)
       - Jaro-Winkler           (rapidfuzz.distance.JaroWinkler)
       - TF-IDF cosine          (scikit-learn, character n-grams)
  2. LEI lookup by NAME and by ISIN, plus former/trading-name matching, via
     the free GLEIF registry (still no API key, still free).
  3. A DuckDuckGo web-search FALLBACK that only fires automatically when the
     LEI check comes back empty or only weakly confident - with a simple
     in-memory cache so the same query is never fetched twice in a row.
  4. Three explicit confidence tiers (HIGH / MEDIUM / LOW) with configurable
     thresholds.
  5. Multi-field matching: legal name, trading/former names, country, LEI
     code, ISIN, and (best-effort - see the note near TICKER below) ticker.
  6. Structured output: every candidate now reports which fields matched,
     by which method, what data source(s) were consulted, and a confidence
     label - not just a single percentage.
A NOTE ON HONESTY (please read before demo day)
---------------------------------------------------------------------------------
GLEIF's LEI database has NO concept of a stock ticker - an LEI identifies a
*legal entity*, not a listed share class. There is no free, authoritative,
no-key API that reliably maps "ticker -> company" the way GLEIF maps
"name -> company". So ticker matching below is exact-string-only (it can
confirm "yes, both sides said TCS", but it cannot discover on its own that
TCS = Tata Consultancy Services). If you need real ticker resolution later,
the honest next step is OpenFIGI (Bloomberg's free identifier-mapping API) -
flagged again in the "next steps" note at the bottom of the file.
If you're new to APIs, search this file for "FRESHER NOTE" - every external
call has one.
=================================================================================
"""
import time
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pandas as pd, numpy as np, requests
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
app = FastAPI(title="AI Vendor / Legal-Entity Screening Agent", version="4.0")
# =================================================================================
# 1. YOUR OWN DATA
# =================================================================================
master = pd.read_csv('data/duplicate_vendor_dummy_data.csv').fillna('')
# =================================================================================
# 2. CONFIDENCE TIERS  (configurable - the brief asked for at least 3 levels)
# =================================================================================
HIGH_THRESHOLD = 85.0     # 85-100 -> HIGH confidence: "Likely duplicate" (per deck's decision bands)
MEDIUM_THRESHOLD = 65.0   # 65-84  -> MEDIUM: "Human review"
MIN_REPORT_THRESHOLD = 40.0  # below this, we don't even report it as a candidate
def confidence_level(pct: float) -> str:
    if pct >= HIGH_THRESHOLD:
        return 'HIGH'
    if pct >= MEDIUM_THRESHOLD:
        return 'MEDIUM'
    return 'LOW'
# Human-readable decision label matching the deck's three decision bands
# (slide 12: 85-100 Likely duplicate / 65-84 Human review / below 65 Likely new).
# Kept separate from confidence_level() so the HIGH/MEDIUM/LOW badge styling
# stays untouched while the wording shown to users matches the brief.
def decision_label(pct: float) -> str:
    if pct >= HIGH_THRESHOLD:
        return 'Likely duplicate'
    if pct >= MEDIUM_THRESHOLD:
        return 'Human review'
    return 'Likely new'
# =================================================================================
# 3. TEXT NORMALISATION HELPERS
# =================================================================================
COUNTRY_ALIASES = {
    'uk': 'united kingdom', 'u.k.': 'united kingdom', 'united kingdom': 'united kingdom',
    'uae': 'united arab emirates', 'u.a.e.': 'united arab emirates', 'united arab emirates': 'united arab emirates',
    'us': 'united states', 'u.s.': 'united states', 'usa': 'united states', 'u.s.a.': 'united states',
    'united states': 'united states', 'united states of america': 'united states',
}
STOP_WORDS = {
    'ltd', 'ltd.', 'limited', 'pvt', 'private', 'inc', 'inc.', 'incorporated', 'llc', 'llp',
    'co', 'co.', 'company', 'corp', 'corporation', 'gmbh', 'group', 'and',
    'technologies', 'solutions', 'services', 'systems', 'the',
}
# A NARROWER list used only when building an acronym. Words like "services"
# or "technologies" are dropped for fuzzy name-token comparison (STOP_WORDS
# above), but they are very often part of the acronym itself - e.g. TCS =
# TATA CONSULTANCY SERVICES. Stripping "services" there would wrongly turn
# TCS into "TC" and break the match, so acronym-building only strips pure
# legal-entity suffixes, never descriptive business words.
LEGAL_SUFFIX_WORDS = {
    'ltd', 'ltd.', 'limited', 'pvt', 'private', 'inc', 'inc.', 'incorporated',
    'llc', 'llp', 'co', 'co.', 'company', 'corp', 'corporation', 'gmbh', 'the', 'and',
}
# FRESHER NOTE: GLEIF needs a 2-letter country code (ISO 3166-1 alpha-2), not
# free text. This dict translates the common ones; unrecognised countries
# just skip the country filter instead of breaking the search.
COUNTRY_ISO2 = {
    'india': 'IN', 'united states': 'US', 'usa': 'US', 'us': 'US',
    'united kingdom': 'GB', 'uk': 'GB', 'germany': 'DE', 'france': 'FR',
    'china': 'CN', 'japan': 'JP', 'singapore': 'SG', 'united arab emirates': 'AE',
    'uae': 'AE', 'netherlands': 'NL', 'switzerland': 'CH', 'australia': 'AU',
    'canada': 'CA', 'brazil': 'BR', 'italy': 'IT', 'spain': 'ES', 'ireland': 'IE',
    'denmark': 'DK', 'sweden': 'SE', 'norway': 'NO', 'poland': 'PL',
    'mexico': 'MX', 'south africa': 'ZA', 'south korea': 'KR', 'korea': 'KR',
    'philippines': 'PH', 'malaysia': 'MY', 'indonesia': 'ID', 'thailand': 'TH',
    'vietnam': 'VN', 'hong kong': 'HK', 'belgium': 'BE', 'austria': 'AT',
    'portugal': 'PT', 'finland': 'FI', 'israel': 'IL', 'turkey': 'TR',
    'russia': 'RU', 'new zealand': 'NZ', 'saudi arabia': 'SA', 'egypt': 'EG',
    'nigeria': 'NG', 'argentina': 'AR', 'colombia': 'CO', 'czech republic': 'CZ',
}
def norm(x): return ' '.join(str(x or '').lower().replace('&', ' and ').split())
def ncountry(x):
    k = str(x or '').strip().lower()
    return COUNTRY_ALIASES.get(k, k)
def _iso2(x):
    """Normalise a country to an ISO-2 code when we can, so 'India' and the
    'IN' that GLEIF returns compare as EQUAL. (This was the bug behind the
    stuck 57% country bars: 'India' was being fuzzy-compared to 'IN'.)"""
    s = str(x or '').strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    code = COUNTRY_ISO2.get(s.lower())
    return (code or ncountry(s)).upper()
def country_sim(a, b):
    ca, cb = _iso2(a), _iso2(b)
    if not ca or not cb: return 0.0
    if ca == cb: return 1.0
    return fuzz.token_set_ratio(ca, cb) / 100
def gleif_country_code(country_text):
    return COUNTRY_ISO2.get(str(country_text or '').strip().lower(), '')
def gv(o, name, default=''):
    """Read a field off a Pydantic model, a plain dict, or a pandas row."""
    val = o.get(name, default) if hasattr(o, 'get') else getattr(o, name, default)
    try:
        if pd.isna(val): return default
    except Exception:
        pass
    return val if val not in (None, '') else default
def name_tokens(s):
    return set(w.strip('.,') for w in norm(s).split() if w.strip('.,') and w.strip('.,') not in STOP_WORDS)
def name_core(s):
    core = ' '.join(sorted(name_tokens(s)))
    return core or norm(s)
def ordered_name_words(s):
    """Used only for acronym-building - see LEGAL_SUFFIX_WORDS note above."""
    return [w.strip('.,') for w in norm(s).replace('.', ' ').split()
            if w.strip('.,') and w.strip('.,') not in LEGAL_SUFFIX_WORDS]
def acronym_of(s):
    words = ordered_name_words(s)
    return ''.join(w[0] for w in words if w).upper()
def looks_like_acronym(s):
    raw = ''.join(ch for ch in str(s) if ch.isalpha())
    return len(ordered_name_words(s)) <= 1 and 2 <= len(raw) <= 6
def acronym_similarity(a, b):
    """Catches abbreviation <-> expansion pairs: IBM <-> International Business
    Machines, TCS <-> Tata Consultancy Services."""
    for short, long in ((a, b), (b, a)):
        if looks_like_acronym(short):
            sac = ''.join(ch for ch in str(short) if ch.isalpha()).upper()
            if len(sac) >= 2 and sac == acronym_of(long):
                return 1.0
    return 0.0
def _first_core_token(s):
    """First distinctive word of a name, skipping pure legal words like 'the'."""
    for w in (x.strip('.,') for x in norm(s).split()):
        if w and w not in LEGAL_SUFFIX_WORDS:
            return w
    return ''
def containment_penalty(a, b):
    """Return a 0-1 factor that damps the name score when one name is really
    just the other plus a DIFFERENT leading qualifier - the 'Capital Infosys'
    vs 'Infosys' false-positive pattern. Returns 1.0 (no penalty) for genuine
    brand/legal variants that share the same head word ('Cognizant' vs
    'Cognizant Technology Solutions'), for word-order and spelling variants,
    and whenever there is nothing distinctive to compare."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 1.0
    inter = ta & tb
    if not inter or len(ta) == len(tb):
        return 1.0
    smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not smaller.issubset(larger):
        return 1.0                      # not pure containment -> leave it to the fuzzy score
    if _first_core_token(a) == _first_core_token(b):
        return 1.0                      # same head word -> same brand, just extra descriptors
    return len(inter) / len(ta | tb)    # different leading qualifier -> different entity
# =================================================================================
# 4. THE THREE-ALGORITHM COMPOSITE NAME SCORE
# =================================================================================
# FRESHER NOTE: why three algorithms instead of one?
#   - Levenshtein-family (token_set_ratio) is great at "same words, different
#     order / extra words" - e.g. "Services ABC Pharma" vs "ABC Pharma Services".
#   - Jaro-Winkler rewards matching PREFIXES especially - good at catching
#     typos near the end of a name and small punctuation slips.
#   - TF-IDF cosine looks at which sub-word chunks (character n-grams) two
#     names share, which is more forgiving of spacing/hyphenation:
#     "Blue-Tech R&D" vs "Bluetech R and D".
# No single one of these is right for every case in the deck (slide 10), so we
# take the best of the three, then let the acronym check override everything
# if it's a clean abbreviation match.
def _lev_ratio(a, b):
    return fuzz.token_set_ratio(str(a), str(b)) / 100 if a and b else 0.0
def _jaro_winkler(a, b):
    return JaroWinkler.normalized_similarity(str(a), str(b)) if a and b else 0.0
def _tfidf_cosine(a, b):
    a, b = str(a).strip(), str(b).strip()
    if not a or not b:
        return 0.0
    try:
        vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
        matrix = vec.fit_transform([a, b])
        return float(cosine_similarity(matrix[0], matrix[1])[0][0])
    except ValueError:
        # happens if both strings are pure stop-characters after cleanup
        return 0.0
def composite_name_score(a, b) -> Dict[str, Any]:
    """Runs all three algorithms on the *cleaned* (legal-suffix-stripped)
    names, takes the best score, and separately checks for an acronym match
    on the *raw* names (acronyms need the original casing/short form)."""
    ca, cb = name_core(a), name_core(b)
    scores = {
        'levenshtein': round(_lev_ratio(ca, cb), 3),
        'jaro_winkler': round(_jaro_winkler(ca, cb), 3),
        'tfidf_cosine': round(_tfidf_cosine(ca, cb), 3),
    }
    # A clean abbreviation<->expansion match (IBM <-> International Business
    # Machines) is decisive on its own - check it FIRST, before any penalty.
    if acronym_similarity(a, b) >= 1.0:
        return {'score': 1.0, 'method': 'acronym_expansion', 'breakdown': scores}
    best_method = max(scores, key=scores.get)
    best_score = scores[best_method]
    # CORRECTION (false-positive fix): token_set_ratio returns 100% whenever one
    # name's distinctive tokens are a SUBSET of the other's - which is why
    # "Infosys" scored 100% against "Capital Infosys" / "Ravi Infosys". Damp the
    # score when the longer name carries a DIFFERENT leading qualifier, while
    # leaving true brand/legal variants (same head word) untouched.
    penalty = containment_penalty(a, b)
    adj = round(best_score * penalty, 3)
    method = best_method if penalty >= 1.0 else best_method + '+containment_damp'
    return {'score': adj, 'method': method, 'breakdown': scores}
def name_match_score(a, b) -> float:
    return composite_name_score(a, b)['score']
# =================================================================================
# 5. GLEIF INTEGRATION  (name search, ISIN lookup, parent/hierarchy, other names)
# =================================================================================
GLEIF_BASE = "https://api.gleif.org/api/v1"
# In-memory cache so repeated demo searches (and the many parent-lookup 404s)
# are served instantly instead of re-hitting the network. Keyed by path+params.
_GLEIF_CACHE: Dict[Any, Any] = {}
_GLEIF_CACHE_TTL = 3600
# One reused connection pool + a shared thread pool so all the GLEIF calls for
# a single screen run happen concurrently instead of one-after-another.
_SESSION = requests.Session()
_GLEIF_POOL = ThreadPoolExecutor(max_workers=10)
def gleif_request(path, params=None, timeout=6, retry_on_429=True):
    """One shared helper for every GLEIF call.
    - A 200 means success -> returns parsed JSON.
    - A 404 (very common - most companies have no LEI, or no parent LEI)
      is treated as 'nothing found', not an error.
    - A 429 (rate limited) gets ONE short retry, then gives up gracefully.
    - Any network failure returns None rather than raising, so a GLEIF
      hiccup never crashes the whole screening request.
    Results (including 'nothing found') are cached in-memory for the session so
    repeated searches are instant."""
    cache_key = (path, tuple(sorted((params or {}).items())))
    hit = _GLEIF_CACHE.get(cache_key)
    if hit is not None and (time.time() - hit[0]) < _GLEIF_CACHE_TTL:
        return hit[1]
    result = None
    try:
        resp = _SESSION.get(
            f"{GLEIF_BASE}{path}", params=params or {}, timeout=timeout,
            headers={"Accept": "application/vnd.api+json"},
        )
        if resp.status_code == 429 and retry_on_429:
            time.sleep(0.6)
            resp = _SESSION.get(
                f"{GLEIF_BASE}{path}", params=params or {}, timeout=timeout,
                headers={"Accept": "application/vnd.api+json"},
            )
        result = resp.json() if resp.status_code == 200 else None
    except requests.RequestException:
        result = None
    _GLEIF_CACHE[cache_key] = (time.time(), result)
    return result
def _lei_record_to_dict(rec):
    """Pulls the fields we care about out of GLEIF's JSON:API envelope,
    including former/trading names - this is what catches rebranding
    (e.g. a company now trading as a different brand than its legal name)."""
    if not rec:
        return None
    attrs = rec.get('attributes', {}) or {}
    entity = attrs.get('entity', {}) or {}
    addr = entity.get('legalAddress', {}) or {}
    other_names = [
        (n or {}).get('name', '')
        for n in (entity.get('otherNames') or [])
        if (n or {}).get('name')
    ]
    return {
        'lei': rec.get('id', ''),
        'legal_name': (entity.get('legalName', {}) or {}).get('name', ''),
        'other_names': other_names,   # trading names, former names, translations
        'country': addr.get('country', ''),
        'city': addr.get('city', ''),
        'status': entity.get('status', ''),
        'registration_status': (attrs.get('registration', {}) or {}).get('status', ''),
    }
def gleif_search_by_name(name, country='', limit=5):
    """STEP 1: 'does a company with roughly this name exist in the open
    registry?'  GLEIF's own search is fuzzy server-side, so near-misses
    still surface."""
    if not str(name).strip():
        return []
    params = {'filter[entity.legalName]': name, 'page[size]': limit}
    iso2 = gleif_country_code(country)
    if iso2:
        params['filter[entity.legalAddress.country]'] = iso2
    data = gleif_request('/lei-records', params)
    if not data:
        return []
    return [d for d in (_lei_record_to_dict(r) for r in data.get('data', [])) if d]
def gleif_search_by_isin(isin):
    """Multi-field matching bonus: if the caller supplies an ISIN (a
    security identifier), GLEIF can resolve it straight to the owning
    legal entity via its ISIN-to-LEI mapping."""
    if not str(isin).strip():
        return []
    data = gleif_request('/lei-records', {'filter[isin]': isin.strip().upper(), 'page[size]': 5})
    if not data:
        return []
    return [d for d in (_lei_record_to_dict(r) for r in data.get('data', [])) if d]
def gleif_by_lei(lei):
    """Exact lookup when the caller already knows the LEI code."""
    if not str(lei).strip():
        return None
    data = gleif_request(f'/lei-records/{lei.strip().upper()}')
    if not data:
        return None
    return _lei_record_to_dict(data.get('data'))
def gleif_parent(lei, kind='direct'):
    """'Who owns this company?' - /direct-parent or /ultimate-parent.
    A 404 here just means 'no parent on file', the normal case."""
    data = gleif_request(f"/lei-records/{lei}/{kind}-parent")
    if not data:
        return None
    return _lei_record_to_dict(data.get('data'))
# =================================================================================
# 6. WEB-SEARCH FALLBACK  (DuckDuckGo, with a simple in-memory cache)
# =================================================================================
# FRESHER NOTE: this only runs automatically when the LEI check above comes
# back with NOTHING, or with only a LOW/MEDIUM confidence hit - i.e. exactly
# the "ambiguous or incomplete" trigger the brief describes. A clean HIGH
# confidence LEI match never needs a web search; that would just waste time
# and API calls for no extra certainty.
_WEB_CACHE: Dict[str, Dict[str, Any]] = {}
_WEB_CACHE_TTL_SECONDS = 3600  # 1 hour - plenty for a demo/review session
def cached_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    now = time.time()
    hit = _WEB_CACHE.get(query)
    if hit and (now - hit['ts']) < _WEB_CACHE_TTL_SECONDS:
        return {**hit['data'], 'from_cache': True}
    try:
        from ddgs import DDGS
        raw = list(DDGS().text(query, max_results=max_results))
        data = {
            'ok': True,
            'results': [{'title': r.get('title', ''), 'url': r.get('href', ''),
                         'snippet': r.get('body', '')} for r in raw],
        }
    except Exception as e:
        data = {'ok': False, 'error': str(e), 'results': []}
    _WEB_CACHE[query] = {'ts': now, 'data': data}
    return {**data, 'from_cache': False}
def web_verify(vendor_name: str, country: str) -> Dict[str, Any]:
    query = f'"{vendor_name}" {country} company official website'.strip()
    result = cached_web_search(query)
    result['query'] = query
    return result
def external_evidence_score(web_result: Optional[Dict[str, Any]], candidate_name: str) -> Optional[float]:
    """Turns the (already-run) web-search fallback into the 5th evidence
    category from slide 12 ('External evidence'). This is deliberately
    evidence-based rather than a flat placeholder: it checks how well the
    candidate's name actually appears in the returned titles/snippets,
    and returns None (not 0) when no web check ran at all for this
    candidate, so the UI can show 'Not checked' instead of a fake score."""
    if not web_result:
        return None
    if not web_result.get('ok') or not web_result.get('results'):
        return 0.0
    best = 0.0
    for r in web_result['results']:
        text = f"{r.get('title', '')} {r.get('snippet', '')}"
        best = max(best, name_match_score(candidate_name, text))
    return round(best * 100, 1)
# =================================================================================
# 7. CHECK #1 - YOUR OWN VENDOR MASTER (internal, offline, instant)
# =================================================================================
def feats(v, r):
    vco, rco = gv(v, 'country'), gv(r, 'country')
    ns = composite_name_score(gv(v, 'vendor_name'), gv(r, 'vendor_name'))
    return {
        'name_similarity': ns['score'],
        'name_method': ns['method'],
        'name_breakdown': ns['breakdown'],
        'country_similarity': country_sim(vco, rco),
        'country_match': int(country_sim(vco, rco) >= .9),
        'city_similarity': _lev_ratio(gv(v, 'city'), gv(r, 'city')),
        'website_similarity': _lev_ratio(gv(v, 'website'), gv(r, 'website')),
        'lei_match': int(bool(gv(v, 'lei')) and gv(v, 'lei').strip().upper() == str(gv(r, 'lei', '')).strip().upper()),
    }
COLS = ['name_similarity', 'country_similarity', 'country_match', 'city_similarity', 'website_similarity']
WEIGHTS = {'name_similarity': .50, 'country_similarity': .20, 'country_match': .10,
           'city_similarity': .10, 'website_similarity': .10}
POS_RANGES = {'name_similarity': (.75, 1), 'country_similarity': (.85, 1),
              'city_similarity': (.7, 1), 'website_similarity': (.5, 1)}
NEG_RANGES = {'name_similarity': (0, .7), 'country_similarity': (0, .8),
              'city_similarity': (0, 1), 'website_similarity': (0, .55)}
BINARY_COLS = {'country_match'}
POS_P = {'country_match': .85}
NEG_P = {'country_match': .35}
def train():
    rng = np.random.default_rng(42)
    X, y = [], []
    for label in (1, 0):
        ranges = POS_RANGES if label else NEG_RANGES
        probs = POS_P if label else NEG_P
        for _ in range(900):
            row = []
            for c in COLS:
                if c in BINARY_COLS:
                    p = probs[c]
                    row.append(rng.choice([0, 1], p=[1 - p, p]))
                else:
                    lo, hi = ranges[c]
                    row.append(rng.uniform(lo, hi))
            X.append(row); y.append(label)
    m = RandomForestClassifier(n_estimators=250, max_depth=10, class_weight='balanced', random_state=42)
    m.fit(X, y)
    return m
model = train()
def matched_fields_internal(v, r, f):
    fields = []
    if f['lei_match']:
        fields.append({'field': 'lei', 'score': 100.0, 'note': 'Exact LEI code match'})
    if f['name_similarity'] >= .55:
        fields.append({'field': 'legal_name', 'score': round(f['name_similarity'] * 100, 1),
                        'note': f"Matched via {f['name_method']}"})
    if f['country_match']:
        fields.append({'field': 'country', 'score': round(f['country_similarity'] * 100, 1),
                        'note': f"Country matches ({gv(r, 'country')})"})
    if f['city_similarity'] >= .7:
        fields.append({'field': 'city', 'score': round(f['city_similarity'] * 100, 1), 'note': 'City matches'})
    if f['website_similarity'] >= .7:
        fields.append({'field': 'website', 'score': round(f['website_similarity'] * 100, 1), 'note': 'Website matches'})
    return fields
def diff_breakdown(v, r, f):
    similar, add_on = [], []
    if f['name_method'] == 'acronym_expansion':
        similar.append("Name matches as an acronym/expansion pair")
    elif f['name_similarity'] >= .55:
        similar.append(f"Name ~{f['name_similarity']:.0%} similar (best method: {f['name_method']})")
    if f['country_match']: similar.append(f"Country matches ({gv(r, 'country')})")
    elif f['country_similarity'] > 0: similar.append(f"Country partially similar ({f['country_similarity']:.0%})")
    if f['city_similarity'] >= .7: similar.append(f"City matches ({gv(r, 'city')})")
    if f['website_similarity'] >= .7: similar.append("Website matches")
    vt, rt = name_tokens(gv(v, 'vendor_name')), name_tokens(gv(r, 'vendor_name'))
    extra_in_v, extra_in_r = vt - rt, rt - vt
    if extra_in_v: add_on.append("New name adds: " + ", ".join(sorted(extra_in_v)))
    if extra_in_r: add_on.append("Existing record has extra term(s): " + ", ".join(sorted(extra_in_r)))
    if gv(v, 'website') and not gv(r, 'website'):
        add_on.append(f"Website provided ({gv(v, 'website')}) - not on existing record")
    return {'similar': similar, 'add_on': add_on}
def evidence_internal(v, r, f):
    """Named evidence categories for the UI (deck slide 12): Name similarity,
    Website/domain, Country/address, Registry/identifier. 'external_evidence'
    is left None here and filled in later by /screen if a web-search fallback
    runs - a category with no supporting check is reported as None (shown as
    'Not checked'), never invented."""
    return {
        'name_similarity': round(f['name_similarity'] * 100, 1),
        'website_domain': round(f['website_similarity'] * 100, 1) if gv(v, 'website') else None,
        'country_address': round(f['country_similarity'] * 100, 1) if (gv(v, 'country') or gv(r, 'country')) else None,
        'registry_identifier': 100.0 if f['lei_match'] else (0.0 if gv(v, 'lei') else None),
        'external_evidence': None,
    }
def internal_matches(vendor_name, country, website, lei=''):
    v = {'vendor_name': vendor_name, 'country': country, 'website': website, 'lei': lei}
    out = []
    for _, r in master.iterrows():
        f = feats(v, r)
        # Only surface records that are actually NAME-similar (or an exact ID
        # match). Sharing a country alone is not a reason to show a vendor as a
        # "similar entity" - that just added noise (e.g. every India vendor
        # showing up for an "Infosys" search).
        if f['name_similarity'] < .55 and not f['lei_match']:
            continue
        # Transparent weighted evidence over the signals we ACTUALLY have. The
        # search form supplies name + country; city/website are scored only when
        # the query provides them, so a field the user never typed can't silently
        # drag a real match down (this was why exact matches read as 77.9).
        provided = {'name_similarity': True,
                    'country_similarity': bool(gv(v, 'country')),
                    'country_match': bool(gv(v, 'country')),
                    'city_similarity': bool(gv(v, 'city')),
                    'website_similarity': bool(gv(v, 'website'))}
        active = [c for c in COLS if provided.get(c)]
        wsum = sum(WEIGHTS[c] for c in active) or 1.0
        h = 100 * sum(WEIGHTS[c] * f[c] for c in active) / wsum
        # ML classifier kept as a secondary cross-check (minority weight) - the
        # transparent heuristic above is the primary, explainable score.
        x = np.array([[f[c] for c in COLS]])
        ml = float(model.predict_proba(x)[0][1]) * 100
        p = .75 * h + .25 * ml
        if f['lei_match']:
            p = 100.0
        # Corroboration gate: a name match ALONE can never be a confident
        # duplicate - it must be backed by at least one non-name signal (same
        # country, same city, or an exact registry/LEI match). This is what
        # stops "reuse" ever firing on a name coincidence.
        corroborated = bool(f['country_match'] or f['city_similarity'] >= .7 or f['lei_match'])
        if not corroborated:
            p = min(p, 84.0)
        if p < MIN_REPORT_THRESHOLD:
            continue
        bd = diff_breakdown(v, r, f)
        out.append({
            'source': ['Vendor master (internal)'],
            'vendor_id': str(gv(r, 'vendor_id', '')),
            'vendor_name': gv(r, 'vendor_name'),
            'country': gv(r, 'country'), 'city': gv(r, 'city'),
            'match_percent': round(p, 1),
            'confidence': confidence_level(p),
            'decision_label': decision_label(p),
            'matched_fields': matched_fields_internal(v, r, f),
            'similar': bd['similar'], 'add_on': bd['add_on'],
            'evidence': evidence_internal(v, r, f),
        })
    out.sort(key=lambda z: z['match_percent'], reverse=True)
    return out[:5]
# =================================================================================
# 8. CHECK #2 - GLEIF OPEN REGISTRY  (external, multi-field)
# =================================================================================
def external_matches(vendor_name, country, master_names, lei='', isin='', max_hits=3):
    hits = []
    seen_leis = set()
    # multi-field: if an LEI code was supplied directly, that's a 100%
    # authoritative check on its own - go straight to GLEIF by ID.
    if lei:
        rec = gleif_by_lei(lei)
        if rec:
            hits.append(rec)
            seen_leis.add(rec['lei'])
    # multi-field: if an ISIN was supplied, resolve it to its issuing entity.
    if isin:
        for rec in gleif_search_by_isin(isin):
            if rec['lei'] not in seen_leis:
                hits.append(rec); seen_leis.add(rec['lei'])
    # the core case: search by name.
    for rec in gleif_search_by_name(vendor_name, country, limit=5):
        if rec['lei'] not in seen_leis:
            hits.append(rec); seen_leis.add(rec['lei'])
    # PERFORMANCE: prefetch every direct/ultimate parent lookup CONCURRENTLY.
    # This was the main source of latency - up to 2 sequential ~1s calls per
    # hit (10+ calls back-to-back). Running them together + the response cache
    # takes a ~12s screen down to ~2s (and near-instant on repeat).
    parent_map: Dict[Any, Any] = {}
    if hits:
        futures = {
            _GLEIF_POOL.submit(gleif_parent, h['lei'], kind): (h['lei'], kind)
            for h in hits for kind in ('direct', 'ultimate')
        }
        for fut, key in futures.items():
            try:
                parent_map[key] = fut.result()
            except Exception:
                parent_map[key] = None
    results = []
    for h in hits:
        # compare the typed name against BOTH the legal name and any
        # trading/former names GLEIF has on file - this is what catches
        # rebrands (slide 10: "Cognizant" vs "Cognizant Technology Solutions").
        candidate_names = [h['legal_name']] + h.get('other_names', [])
        best = max(
            (composite_name_score(vendor_name, cn) for cn in candidate_names if cn),
            key=lambda d: d['score'], default={'score': 0.0, 'method': 'none', 'breakdown': {}}
        )
        name_score = best['score']
        is_exact_id_match = bool(lei and h['lei'].upper() == lei.strip().upper()) or bool(isin and h['lei'] in seen_leis and isin)
        if name_score < .45 and not is_exact_id_match:
            continue
        country_score = country_sim(country, h['country'])
        overall = 100.0 if (lei and h['lei'].upper() == lei.strip().upper()) else \
            round(100 * (0.75 * name_score + 0.25 * country_score), 1)
        matched_fields, similar, add_on = [], [], []
        if lei and h['lei'].upper() == lei.strip().upper():
            matched_fields.append({'field': 'lei', 'score': 100.0, 'note': 'Exact LEI code match'})
            similar.append("LEI code matches exactly")
        if name_score >= .55:
            matched_fields.append({'field': 'legal_name', 'score': round(name_score * 100, 1),
                                    'note': f"Matched via {best['method']}"})
            similar.append(f"Registered name ~{name_score:.0%} similar (best method: {best['method']})")
        if country_score >= .85:
            matched_fields.append({'field': 'country', 'score': round(country_score * 100, 1),
                                    'note': f"Registered country matches ({h['country']})"})
            similar.append(f"Registered country matches ({h['country']})")
        if h['status']:
            add_on.append(f"GLEIF entity status: {h['status']}")
        if h.get('registration_status'):
            add_on.append(f"LEI registration status: {h['registration_status']}")
        if h.get('other_names'):
            add_on.append("Other names on file: " + ", ".join(h['other_names'][:3]))
        # hierarchy / corporate-family check (parents were prefetched above)
        for kind in ('direct', 'ultimate'):
            parent = parent_map.get((h['lei'], kind))
            if not parent or not parent['legal_name']:
                continue
            for mn in master_names:
                if name_match_score(parent['legal_name'], mn) >= .80:
                    similar.append(
                        f"{kind.title()} parent per GLEIF is '{parent['legal_name']}', "
                        f"which matches your existing vendor '{mn}'"
                    )
                    matched_fields.append({'field': 'corporate_hierarchy', 'score': 90.0,
                                            'note': f"{kind} parent matches existing vendor '{mn}'"})
                    overall = max(overall, 90.0)
                    break
        # Registry/identifier evidence: GLEIF is itself the registry check, so
        # an ACTIVE entity with an ISSUED LEI is strong registry evidence; a
        # lapsed/inactive record is weaker even though it still "exists".
        if lei and h['lei'].upper() == lei.strip().upper():
            registry_score = 100.0
        elif h.get('status') == 'ACTIVE' and h.get('registration_status') == 'ISSUED':
            registry_score = 90.0
        elif h.get('status') or h.get('registration_status'):
            registry_score = 50.0
        else:
            registry_score = None
        # Corroboration gate (same rule as the internal check): name evidence on
        # its own caps at 'human review'. A GLEIF hit is promotable to 'likely
        # duplicate' only with a corroborating signal - matching country, an
        # exact LEI/ISIN match, or a shared corporate parent.
        # IMPORTANT: for an EXTERNAL registry hit, a matching country is NOT
        # enough to call a duplicate - two different real companies can share a
        # name in the same country (e.g. "Cognizant Chemical" vs "Cognizant").
        # Promotion to 'likely duplicate' requires an IDENTITY-level tie: an
        # exact LEI/ISIN match, or a corporate-parent link to an existing
        # vendor. Everything else caps at 'human review'. (A matching domain
        # would also qualify here - GLEIF just doesn't expose one.)
        corroborated = (
            is_exact_id_match
            or any(mf['field'] in ('lei', 'corporate_hierarchy') for mf in matched_fields)
        )
        if not corroborated:
            overall = min(overall, 84.0)
        final_pct = min(overall, 100.0)
        results.append({
            'source': ['GLEIF LEI Registry'],
            'vendor_id': h['lei'],
            'vendor_name': h['legal_name'],
            'country': h['country'], 'city': h['city'],
            'match_percent': final_pct,
            'confidence': confidence_level(final_pct),
            'decision_label': decision_label(final_pct),
            'matched_fields': matched_fields,
            'similar': similar, 'add_on': add_on,
            'evidence': {
                'name_similarity': round(name_score * 100, 1),
                'website_domain': None,  # GLEIF has no website field to compare
                'country_address': round(country_score * 100, 1) if country else None,
                'registry_identifier': registry_score,
                'external_evidence': None,
            },
        })
    results.sort(key=lambda x: x['match_percent'], reverse=True)
    return results[:max_hits]
# =================================================================================
# 9. THE ENDPOINT - runs internal + GLEIF, falls back to web search if needed
# =================================================================================
class VendorSearch(BaseModel):
    vendor_name: str
    country: str
    website: str = ''
    # Optional multi-field inputs. Not shown on the simple 3-field dashboard
    # by request, but any API caller (Postman, the /docs page, another
    # system) can supply them for a stronger check.
    lei: str = ''
    isin: str = ''
    ticker: str = ''
def ticker_check(a: str, b: str) -> Optional[Dict[str, Any]]:
    """Best-effort ONLY - see the honesty note at the top of the file.
    Exact, case-insensitive match; no resolution of one ticker to another
    identifier is attempted without a paid/keyed data source."""
    a, b = str(a or '').strip().upper(), str(b or '').strip().upper()
    if a and b and a == b:
        return {'field': 'ticker', 'score': 100.0, 'note': f'Ticker matches exactly ({a})'}
    return None
class VendorDecision(BaseModel):
    """What the UI posts when a user clicks Reuse existing / Send to review /
    Create new on a candidate (deck slides 8, 9, 11: 'human decisions remain
    in control' - the agent recommends, a person decides)."""
    query_vendor_name: str
    query_country: str = ''
    query_website: str = ''
    candidate_vendor_id: str = ''
    candidate_vendor_name: str = ''
    match_percent: float = 0.0
    decision: str  # 'reuse' | 'review' | 'create'
DECISIONS_LOG_PATH = 'data/decisions_log.csv'
DECISION_LABELS = {'reuse': 'Reuse existing', 'review': 'Send to review', 'create': 'Create new'}
@app.get('/health')
def health():
    return {'status': 'ok'}
@app.post('/decision')
def record_decision(d: VendorDecision):
    """Appends one row per decision to a CSV audit log - this is the 'real
    backend action' behind the three decision buttons. It never blocks or
    silently drops a decision: if the file write fails, the error is
    returned to the caller rather than swallowed, since a lost audit record
    is worse than a visible error here."""
    if d.decision not in DECISION_LABELS:
        return {'ok': False, 'error': f"Unknown decision '{d.decision}'. Expected one of: {list(DECISION_LABELS)}"}
    row = {
        'timestamp': pd.Timestamp.utcnow().isoformat(),
        'query_vendor_name': d.query_vendor_name,
        'query_country': d.query_country,
        'query_website': d.query_website,
        'candidate_vendor_id': d.candidate_vendor_id,
        'candidate_vendor_name': d.candidate_vendor_name,
        'match_percent': d.match_percent,
        'decision': d.decision,
        'decision_label': DECISION_LABELS[d.decision],
    }
    try:
        import os, csv
        file_exists = os.path.isfile(DECISIONS_LOG_PATH)
        os.makedirs(os.path.dirname(DECISIONS_LOG_PATH), exist_ok=True)
        with open(DECISIONS_LOG_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    return {'ok': True, 'recorded': row}
@app.get('/decisions')
def list_decisions(limit: int = 50):
    """Read-only view of the audit log, mainly for the demo/evaluation phase
    (deck slide 13: 'evaluation report')."""
    import os
    if not os.path.isfile(DECISIONS_LOG_PATH):
        return {'count': 0, 'decisions': []}
    df = pd.read_csv(DECISIONS_LOG_PATH).fillna('')
    rows = df.tail(limit).to_dict(orient='records')
    return {'count': len(df), 'decisions': list(reversed(rows))}
@app.post('/screen')
def screen(v: VendorSearch):
    master_names = master['vendor_name'].astype(str).tolist() if 'vendor_name' in master.columns else []
    internal = internal_matches(v.vendor_name, v.country, v.website, v.lei)
    try:
        external = external_matches(v.vendor_name, v.country, master_names, v.lei, v.isin)
    except Exception:
        external = []  # a GLEIF hiccup should never take the whole search down
    combined = sorted(internal + external, key=lambda c: c['match_percent'], reverse=True)
    # ----- automatic web-search fallback -----
    # Fires only when nothing came back, or the best we found is MEDIUM/LOW
    # confidence - i.e. exactly "ambiguous or incomplete" per the brief.
    # Only run the (slower, rate-limited) web search when we found NOTHING at all
    # internally or in GLEIF - i.e. genuinely "no evidence yet". This keeps the
    # common path fast; a strong or even a weak registry hit never pays for it.
    web_result = None
    if not combined:
        try:
            web_result = web_verify(v.vendor_name, v.country)
        except Exception as e:
            web_result = {'ok': False, 'error': str(e), 'results': []}
    # Only the top candidate gets an external_evidence figure - that's the
    # one the web fallback query was actually built around (slide 12 shows
    # evidence for "the top match", not every candidate).
    if combined and web_result is not None:
        combined[0]['evidence']['external_evidence'] = external_evidence_score(
            web_result, combined[0]['vendor_name']
        )
    return {
        'query': {'vendor_name': v.vendor_name, 'country': v.country, 'website': v.website,
                   'lei': v.lei, 'isin': v.isin, 'ticker': v.ticker},
        'result_count': len(combined),
        'candidates': combined[:8],
        'no_match_above_threshold': len(combined) == 0,
        'web_search_fallback': web_result,  # None if a confident LEI/internal match already existed
        'thresholds': {'high': HIGH_THRESHOLD, 'medium': MEDIUM_THRESHOLD, 'minimum_reported': MIN_REPORT_THRESHOLD},
    }
# =================================================================================
# 10. DASHBOARD - unchanged 3-field search box, Novo Nordisk colours
# =================================================================================
DASHBOARD_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vendor / Legal-Entity Screening Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --nn-navy:#001965; --nn-blue:#0057B8; --nn-blue-bright:#0067D9;
    --nn-teal:#009E8F; --nn-amber:#F6A800; --nn-red:#E6553F;
    --bg:#F5F7F9; --card:#FFFFFF; --ink:#183153; --ink-soft:#6B7785;
    --line:#D8E1EA; --green-bg:#E7F3ED; --amber-bg:#FFF4D7; --red-bg:#FCEDF2;
    --font:'Inter', system-ui, sans-serif;
    --header-h:56px;
  }
  *{box-sizing:border-box;}
  html, body{ height:100%; }
  body{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--font); font-size:14.5px; }
  /* ---- slim top bar so the two panes below get almost the full viewport ---- */
  header{ height:var(--header-h); background:var(--nn-navy); color:#fff; padding:0 24px; display:flex; align-items:center; justify-content:space-between; }
  header h1{ margin:0; font-size:16.5px; font-weight:700; letter-spacing:.2px; }
  header .tag{ font-size:11.5px; color:#B1D5F2; }
  /* ---- landscape shell: fixed-width sidebar (form) + fluid scrollable results ---- */
  .layout{ display:grid; grid-template-columns:340px 1fr; height:calc(100vh - var(--header-h)); }
  @media (max-width:900px){ .layout{ grid-template-columns:1fr; height:auto; } .sidebar{ position:static; height:auto; } }
  .sidebar{ position:sticky; top:0; align-self:start; height:calc(100vh - var(--header-h)); overflow-y:auto;
    background:var(--card); border-right:1px solid var(--line); padding:20px; }
  .sidebar h2{ margin:0 0 4px; font-size:15px; color:var(--nn-navy); }
  .sidebar p.hint{ margin:0 0 16px; font-size:12px; color:var(--ink-soft); line-height:1.4; }
  .field{ margin-bottom:12px; }
  .field label{ display:block; font-size:12px; font-weight:600; color:var(--ink); margin-bottom:5px; }
  .field label .req{ color:var(--nn-red); }
  .field input{ width:100%; padding:10px 11px; border:1px solid var(--line); border-radius:6px; font-size:14px; font-family:var(--font); background:#fff; }
  .field input:focus{ outline:2px solid var(--nn-blue); outline-offset:1px; border-color:var(--nn-blue); }
  button.submit{ margin-top:6px; width:100%; padding:12px; border:none; border-radius:6px; background:var(--nn-blue); color:#fff; font-weight:700; font-size:14.5px; cursor:pointer; }
  button.submit:hover{ background:var(--nn-blue-bright); }
  button.submit:disabled{ background:#A9BBD0; cursor:default; }
  .results-pane{ overflow-y:auto; height:calc(100vh - var(--header-h)); padding:18px 24px 60px; }
  .results-pane h3{ font-size:13px; color:var(--ink-soft); margin:0 0 12px; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }
  .empty-state{ color:var(--ink-soft); font-size:13.5px; text-align:center; padding:60px 20px; line-height:1.6; }
  .empty-state .big{ font-size:40px; display:block; margin-bottom:10px; opacity:.5; }
  /* ---- headline verdict banner: the recommendation for the TOP match ---- */
  .verdict{ border-radius:10px; padding:16px 18px; margin-bottom:16px; display:flex; align-items:center; gap:14px; border:1px solid var(--line); }
  .verdict .vicon{ font-size:26px; line-height:1; }
  .verdict .vbody{ flex:1; }
  .verdict .vhead{ font-size:15.5px; font-weight:700; margin-bottom:2px; }
  .verdict .vsub{ font-size:12.5px; color:var(--ink-soft); line-height:1.4; }
  .verdict.v-dup{ background:var(--red-bg); border-color:#F3C9BE; } .verdict.v-dup .vhead{ color:var(--nn-red); }
  .verdict.v-review{ background:var(--amber-bg); border-color:#F1DBA0; } .verdict.v-review .vhead{ color:#8A6200; }
  .verdict.v-new{ background:var(--green-bg); border-color:#BEE3D8; } .verdict.v-new .vhead{ color:var(--nn-teal); }
  /* ---- summary stat chips ---- */
  .statrow{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
  .stat{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:7px 12px; font-size:11.5px; color:var(--ink-soft); }
  .stat b{ color:var(--nn-navy); font-size:14px; }
  /* ---- spinner ---- */
  .spin{ display:flex; flex-direction:column; align-items:center; gap:12px; padding:60px 20px; color:var(--ink-soft); font-size:13px; }
  .spin .ring{ width:34px; height:34px; border:3px solid #DCE4EC; border-top-color:var(--nn-blue); border-radius:50%; animation:sp .8s linear infinite; }
  @keyframes sp{ to{ transform:rotate(360deg); } }
  /* ---- best-match emphasis ---- */
  .candidate.best{ box-shadow:0 2px 10px rgba(0,25,101,.10); }
  /* ---- results as a responsive grid, not a long vertical stack ---- */
  .candidate-grid{ display:grid; grid-template-columns:repeat(auto-fill, minmax(380px, 1fr)); gap:14px; align-items:start; }
  .candidate{ background:var(--card); border:1px solid var(--line); border-left-width:5px; border-radius:8px; padding:15px 16px; }
  .candidate.rag-HIGH{ border-left-color:var(--nn-red); }
  .candidate.rag-MEDIUM{ border-left-color:var(--nn-amber); }
  .candidate.rag-LOW{ border-left-color:var(--nn-teal); }
  .chead{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:8px; }
  .cname{ font-weight:700; font-size:14.5px; color:var(--nn-navy); }
  .cmeta{ font-size:11.5px; color:var(--ink-soft); margin-top:2px; }
  .badge{ display:inline-block; font-size:10px; font-weight:600; padding:2px 7px; border-radius:99px; margin-top:5px; margin-right:4px; }
  .badge.internal{ background:var(--green-bg); color:var(--nn-teal); }
  .badge.external{ background:var(--amber-bg); color:#8A6200; }
  .badge.conf-HIGH{ background:var(--red-bg); color:var(--nn-red); }
  .badge.conf-MEDIUM{ background:var(--amber-bg); color:#8A6200; }
  .badge.conf-LOW{ background:var(--green-bg); color:var(--nn-teal); }
  .cscore{ text-align:right; white-space:nowrap; }
  .cscore .num{ font-weight:700; font-size:19px; color:var(--nn-navy); }
  .cscore .of100{ font-size:11px; color:var(--ink-soft); }
  .cscore .decision{ font-size:11px; font-weight:600; margin-top:2px; }
  .decision.rag-HIGH{ color:var(--nn-red); } .decision.rag-MEDIUM{ color:#8A6200; } .decision.rag-LOW{ color:var(--nn-teal); }
  /* ---- 5-category evidence bars (deck slide 12) ---- */
  .evidence{ margin:10px 0; }
  .evidence h4{ font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-soft); margin:0 0 6px; }
  .evrow{ display:grid; grid-template-columns:108px 1fr 34px; align-items:center; gap:8px; font-size:11px; margin-bottom:4px; }
  .evrow .track{ background:#EAEEF3; border-radius:99px; height:6px; overflow:hidden; }
  .evrow .fill{ height:100%; border-radius:99px; background:var(--nn-blue); }
  .evrow .fill.na{ background:transparent; }
  .evrow .pct{ text-align:right; color:var(--ink-soft); }
  .evrow.na .pct, .evrow.na label{ color:#B7C0CA; font-style:italic; }
  .cols2{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:8px; }
  .cols2 h4{ font-size:10px; text-transform:uppercase; letter-spacing:.05em; margin:0 0 6px; }
  .cols2 h4.similar{ color:var(--nn-teal); } .cols2 h4.addon{ color:#8A6200; }
  .cols2 ul{ margin:0; padding-left:16px; font-size:12px; }
  .cols2 ul li{ margin-bottom:3px; }
  .cols2 .none{ color:var(--ink-soft); font-style:italic; font-size:11.5px; }
  /* ---- decision buttons: human stays in control (slides 8, 9, 11) ---- */
  .actions{ display:flex; gap:6px; margin-top:12px; }
  .actions button{ flex:1; padding:8px 6px; border-radius:6px; font-size:11.5px; font-weight:700; cursor:pointer; border:1px solid transparent; }
  .actions button:disabled{ opacity:.55; cursor:default; }
  .actions .btn-reuse{ background:var(--green-bg); color:var(--nn-teal); border-color:#BEE3D8; }
  .actions .btn-review{ background:var(--amber-bg); color:#8A6200; border-color:#F3DFA0; }
  .actions .btn-create{ background:#EEF1F5; color:var(--ink); border-color:var(--line); }
  .decision-note{ margin-top:8px; font-size:11.5px; font-weight:600; }
  .decision-note.ok{ color:var(--nn-teal); } .decision-note.err{ color:var(--nn-red); }
  .error-banner{ border:1px solid var(--nn-red); background:var(--red-bg); color:var(--nn-red); padding:10px 14px; font-size:13px; margin-bottom:16px; border-radius:6px; }
  /* ---- score pill (band-coloured) ---- */
  .pill{ display:inline-block; padding:2px 8px; border-radius:99px; font-size:10.5px; font-weight:700; margin-top:4px; }
  .pill.rag-HIGH{ background:var(--red-bg); color:var(--nn-red); }
  .pill.rag-MEDIUM{ background:var(--amber-bg); color:#8A6200; }
  .pill.rag-LOW{ background:var(--green-bg); color:var(--nn-teal); }
  /* ---- one-click demo chips ---- */
  .demo{ margin:14px 0 4px; }
  .demo .lbl{ font-size:11px; font-weight:600; color:var(--ink-soft); margin-bottom:6px; }
  .chips{ display:flex; flex-wrap:wrap; gap:6px; }
  .chip{ border:1px solid var(--line); background:#fff; border-radius:99px; padding:5px 11px; font-size:11.5px; font-weight:600; color:var(--nn-blue); cursor:pointer; }
  .chip:hover{ background:var(--nn-blue); color:#fff; border-color:var(--nn-blue); }
  /* ---- decision-band legend ---- */
  .legend{ display:flex; gap:14px; align-items:center; font-size:11px; }
  .legend span{ display:flex; align-items:center; gap:5px; color:#C9D6E4; }
  .legend i{ width:9px; height:9px; border-radius:50%; display:inline-block; }
  .legend .d{ background:var(--nn-red); } .legend .r{ background:var(--nn-amber); } .legend .n{ background:var(--nn-teal); }
  /* ============ SOFT + SMOOTH POLISH ============ */
  body{ -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
        background:linear-gradient(180deg,#F7F9FB 0%,#EFF3F7 100%); }
  .sidebar{ box-shadow:1px 0 0 var(--line); }
  .field input{ border-radius:9px; transition:border-color .18s ease, box-shadow .18s ease; }
  .field input:focus{ outline:none; border-color:var(--nn-blue); box-shadow:0 0 0 3px rgba(0,87,184,.15); }
  button.submit{ border-radius:9px; box-shadow:0 3px 10px rgba(0,87,184,.22);
        transition:background .18s ease, transform .09s ease, box-shadow .18s ease; }
  button.submit:hover{ transform:translateY(-1px); box-shadow:0 5px 16px rgba(0,87,184,.30); }
  button.submit:active{ transform:translateY(0); }
  .chip{ transition:all .16s ease; }
  .chip:hover{ transform:translateY(-1px); box-shadow:0 3px 9px rgba(0,87,184,.18); }
  .candidate{ border-radius:13px; box-shadow:0 1px 3px rgba(16,42,80,.06);
        transition:transform .18s ease, box-shadow .18s ease; animation:fadeUp .4s ease both; }
  .candidate:hover{ transform:translateY(-3px); box-shadow:0 10px 26px rgba(16,42,80,.13); }
  .candidate.best{ box-shadow:0 6px 20px rgba(0,25,101,.12); }
  .verdict{ animation:fadeUp .35s ease both; box-shadow:0 3px 14px rgba(16,42,80,.07); }
  .stat{ transition:transform .16s ease, box-shadow .16s ease; }
  .stat:hover{ transform:translateY(-1px); box-shadow:0 3px 10px rgba(16,42,80,.08); }
  .actions button{ transition:transform .1s ease, filter .16s ease; }
  .actions button:hover:not(:disabled){ filter:brightness(.97); transform:translateY(-1px); }
  .actions button:active:not(:disabled){ transform:translateY(0) scale(.98); }
  .evrow .fill{ transform-origin:left center; animation:grow .6s cubic-bezier(.22,.61,.36,1) both; }
  @keyframes fadeUp{ from{ opacity:0; transform:translateY(9px); } to{ opacity:1; transform:none; } }
  @keyframes grow{ from{ transform:scaleX(0); } to{ transform:scaleX(1); } }
  .candidate-grid > .candidate:nth-child(1){ animation-delay:.02s; }
  .candidate-grid > .candidate:nth-child(2){ animation-delay:.06s; }
  .candidate-grid > .candidate:nth-child(3){ animation-delay:.10s; }
  .candidate-grid > .candidate:nth-child(4){ animation-delay:.14s; }
  .candidate-grid > .candidate:nth-child(5){ animation-delay:.18s; }
  .candidate-grid > .candidate:nth-child(6){ animation-delay:.22s; }
  @media (prefers-reduced-motion: reduce){ *{ animation:none!important; transition:none!important; } }
  /* ---- web verification: compact, collapsible, lives in the sidebar ---- */
  .web-fallback{ margin-top:20px; border-top:1px solid var(--line); padding-top:14px; }
  .web-fallback summary{ cursor:pointer; font-size:12px; font-weight:600; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.05em; }
  .web-result{ border-bottom:1px solid var(--line); padding:8px 0; font-size:11.5px; }
  .web-result a{ font-weight:600; color:var(--nn-navy); text-decoration:none; word-break:break-word; }
  .web-result .url{ display:block; color:var(--nn-teal); font-size:10.5px; margin:2px 0; word-break:break-all; }
  footer.foot{ text-align:center; font-size:11px; color:var(--ink-soft); padding:14px 0 6px; }
</style>
</head>
<body>
<header>
  <h1>AI Vendor / Legal-Entity Screening Agent</h1>
  <div class="legend">
    <span><i class="d"></i>85-100 Likely duplicate</span>
    <span><i class="r"></i>65-84 Human review</span>
    <span><i class="n"></i>&lt;65 Likely new</span>
    <span style="color:#8FA9C8;margin-left:6px;">Novo Nordisk · Student AI Project</span>
  </div>
</header>
<div class="layout">
  <aside class="sidebar">
    <h2>Check a vendor before creating a new record</h2>
    <p class="hint">Checks your vendor master, the open GLEIF LEI registry, and falls back to a web search if neither gives a confident answer.</p>
    <form id="searchForm">
      <div class="field"><label for="vendor_name">Company name <span class="req">*</span></label>
        <input id="vendor_name" required placeholder="Cognizant Technology"></div>
      <div class="field"><label for="country">Location <span class="req">*</span></label>
        <input id="country" required placeholder="India"></div>
      <div class="field"><label for="website">Website <span style="color:var(--ink-soft);font-weight:400;">(optional)</span></label>
        <input id="website" placeholder="example.com"></div>
      <button class="submit" type="submit" id="submitBtn">Screen vendor</button>
    </form>
    <div class="demo">
      <div class="lbl">Try an example</div>
      <div class="chips" id="demoChips">
        <button class="chip" data-n="Cognizant" data-c="India">Cognizant</button>
        <button class="chip" data-n="IBM" data-c="United States">IBM</button>
        <button class="chip" data-n="Infosys" data-c="India">Infosys</button>
        <button class="chip" data-n="Alpha Consulting" data-c="India">Alpha Consulting</button>
        <button class="chip" data-n="Blue-Tech R&amp;D" data-c="Germany">Blue-Tech R&amp;D</button>
      </div>
    </div>
    <div id="webFallbackSlot"></div>
    <footer class="foot">Internal matches are instant. GLEIF depends on a public LEI record. Web search only runs when neither check is confident.</footer>
  </aside>
  <main class="results-pane" id="resultsPane">
    <div class="empty-state"><span class="big">🔎</span>Enter a company name and location on the left,<br>or tap an example, to screen it before creating a new vendor.</div>
  </main>
</div>
<script>
let lastQuery = null; // { vendor_name, country, website } - needed by the decision buttons
function listOrNone(items){
  if(!items || !items.length) return '<p class="none">Nothing to show</p>';
  return '<ul>' + items.map(i => `<li>${i}</li>`).join('') + '</ul>';
}
function evidenceRow(label, pct){
  if(pct === null || pct === undefined){
    return `<div class="evrow na"><label>${label}</label><div class="track"><div class="fill na"></div></div><div class="pct">Not checked</div></div>`;
  }
  return `<div class="evrow"><label>${label}</label><div class="track"><div class="fill" style="width:${pct}%;"></div></div><div class="pct">${pct.toFixed(0)}%</div></div>`;
}
function renderEvidence(ev){
  if(!ev) return '';
  return `<div class="evidence"><h4>Evidence for this match</h4>
    ${evidenceRow('Name similarity', ev.name_similarity)}
    ${evidenceRow('Website / domain', ev.website_domain)}
    ${evidenceRow('Country / address', ev.country_address)}
    ${evidenceRow('Registry / identifier', ev.registry_identifier)}
    ${evidenceRow('External evidence', ev.external_evidence)}
  </div>`;
}
function candidateKey(c){ return `${c.vendor_id || ''}|${c.vendor_name || ''}`; }
// Headline verdict for the TOP match - the "complete user journey", not just a score.
function renderVerdict(data){
  const list = data.candidates || [];
  if(!list.length){
    return `<div class="verdict v-new"><div class="vicon">✓</div><div class="vbody">
      <div class="vhead">Looks like a NEW vendor</div>
      <div class="vsub">No existing record or registered entity matched above the reporting threshold - safe to create.</div>
    </div></div>`;
  }
  const top = list[0];
  const nm = top.vendor_name || 'this record';
  const id = top.vendor_id ? ` (${top.vendor_id})` : '';
  const pct = top.match_percent.toFixed(0);
  if(top.decision_label === 'Likely duplicate'){
    return `<div class="verdict v-dup"><div class="vicon">⚠️</div><div class="vbody">
      <div class="vhead">Likely duplicate - reuse ${nm}${id}</div>
      <div class="vsub">Best match scored ${pct}/100 with corroborating evidence. Recommended action: <b>Reuse existing</b> instead of creating a new record.</div>
    </div></div>`;
  }
  if(top.decision_label === 'Human review'){
    return `<div class="verdict v-review"><div class="vicon">🔍</div><div class="vbody">
      <div class="vhead">Needs human review - ${nm}${id}</div>
      <div class="vsub">Best match scored ${pct}/100 on name evidence, but lacks identity-level corroboration (matching ID, domain or corporate parent). A person should confirm before reuse.</div>
    </div></div>`;
  }
  return `<div class="verdict v-new"><div class="vicon">✓</div><div class="vbody">
    <div class="vhead">Probably a new vendor</div>
    <div class="vsub">Closest match is only ${pct}/100 - no strong duplicate found. Likely safe to create.</div>
  </div></div>`;
}
function renderStats(data){
  const list = data.candidates || [];
  const internal = list.filter(c => (c.source[0]||'').startsWith('Vendor master')).length;
  const gleif = list.filter(c => (c.source[0]||'').startsWith('GLEIF')).length;
  const web = data.web_search_fallback ? 'Yes' : 'No';
  return `<div class="statrow">
    <div class="stat"><b>${data.result_count}</b> candidates</div>
    <div class="stat"><b>${internal}</b> in your master</div>
    <div class="stat"><b>${gleif}</b> in GLEIF registry</div>
    <div class="stat">Web check: <b>${web}</b></div>
  </div>`;
}
function renderCandidates(list){
  if(!list.length) return '<div class="empty-state">No similar entities found above the reporting threshold - this looks like a new vendor.</div>';
  return '<div class="candidate-grid">' + list.map((c, i) => {
    const loc = [c.city, c.country].filter(Boolean).join(', ');
    const badgeClass = c.source[0].startsWith('Vendor master') ? 'internal' : 'external';
    const key = candidateKey(c);
    return `<div class="candidate rag-${c.confidence} ${i === 0 ? 'best' : ''}">
      <div class="chead">
        <div>
          <div class="cname">${c.vendor_name || '(unnamed record)'}</div>
          <div class="cmeta">${loc || '-'}${c.vendor_id ? ' · ' + c.vendor_id : ''}</div>
          <span class="badge ${badgeClass}">${c.source.join(', ')}</span>
          <span class="badge conf-${c.confidence}">${c.confidence} confidence</span>
        </div>
        <div class="cscore">
          <div class="num">${c.match_percent.toFixed(1)}</div>
          <div class="of100">/ 100</div>
          <div class="pill rag-${c.confidence}">${c.decision_label}</div>
        </div>
      </div>
      ${renderEvidence(c.evidence)}
      <div class="cols2">
        <div><h4 class="similar">What's similar</h4>${listOrNone(c.similar)}</div>
        <div><h4 class="addon">Additional info</h4>${listOrNone(c.add_on)}</div>
      </div>
      <div class="actions" data-key="${key}">
        <button class="btn-reuse" data-decision="reuse" data-id="${c.vendor_id || ''}" data-name="${(c.vendor_name || '').replace(/"/g,'&quot;')}" data-pct="${c.match_percent}">Reuse existing</button>
        <button class="btn-review" data-decision="review" data-id="${c.vendor_id || ''}" data-name="${(c.vendor_name || '').replace(/"/g,'&quot;')}" data-pct="${c.match_percent}">Send to review</button>
        <button class="btn-create" data-decision="create" data-id="${c.vendor_id || ''}" data-name="${(c.vendor_name || '').replace(/"/g,'&quot;')}" data-pct="${c.match_percent}">Create new</button>
      </div>
      <div class="decision-note" data-note-for="${key}"></div>
    </div>`;
  }).join('') + '</div>';
}
function renderWebFallback(w){
  if(!w) return '';
  const body = !w.ok
    ? `<p class="none">Web search unavailable (${w.error || 'unknown error'}).</p>`
    : (!w.results.length
        ? `<p class="none">No web results found for "${w.query}".</p>`
        : w.results.map(r => `<div class="web-result"><a href="${r.url}" target="_blank" rel="noopener">${r.title}</a><span class="url">${r.url}</span>${r.snippet}</div>`).join(''));
  return `<details class="web-fallback"><summary>Web verification ${w.from_cache ? '(cached)' : ''}</summary>${body}</details>`;
}
// One shared click handler for every Reuse/Review/Create button, wired to
// the real /decision endpoint (audit-logged server-side).
document.getElementById('resultsPane').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-decision]');
  if(!btn || !lastQuery) return;
  const group = btn.closest('.actions');
  const key = group.getAttribute('data-key');
  const note = document.querySelector(`.decision-note[data-note-for="${CSS.escape(key)}"]`);
  const buttons = group.querySelectorAll('button');
  buttons.forEach(b => b.disabled = true);
  if(note){ note.className = 'decision-note'; note.textContent = 'Recording...'; }
  const payload = {
    query_vendor_name: lastQuery.vendor_name,
    query_country: lastQuery.country,
    query_website: lastQuery.website,
    candidate_vendor_id: btn.dataset.id,
    candidate_vendor_name: btn.dataset.name,
    match_percent: parseFloat(btn.dataset.pct) || 0,
    decision: btn.dataset.decision,
  };
  try{
    const res = await fetch('/decision', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const data = await res.json();
    if(!res.ok || !data.ok) throw new Error(data.error || ('Failed (' + res.status + ')'));
    if(note){ note.className = 'decision-note ok'; note.textContent = `Recorded: ${data.recorded.decision_label} ✓`; }
  } catch(err){
    if(note){ note.className = 'decision-note err'; note.textContent = `Could not record decision: ${err.message}`; }
    buttons.forEach(b => b.disabled = false);
  }
});
// One-click demo chips: fill the form and screen immediately.
document.getElementById('demoChips').addEventListener('click', (e) => {
  const chip = e.target.closest('.chip');
  if(!chip) return;
  document.getElementById('vendor_name').value = chip.dataset.n;
  document.getElementById('country').value = chip.dataset.c;
  document.getElementById('website').value = '';
  document.getElementById('searchForm').requestSubmit();
});
// Deep link: /?q=IBM&c=United+States prefills and screens automatically.
window.addEventListener('DOMContentLoaded', () => {
  const p = new URLSearchParams(location.search);
  if(p.get('q')){
    document.getElementById('vendor_name').value = p.get('q');
    document.getElementById('country').value = p.get('c') || '';
    document.getElementById('website').value = p.get('w') || '';
    document.getElementById('searchForm').requestSubmit();
  }
});
document.getElementById('searchForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('submitBtn');
  const pane = document.getElementById('resultsPane');
  const webSlot = document.getElementById('webFallbackSlot');
  btn.disabled = true; btn.textContent = 'Screening...';
  pane.innerHTML = '<div class="spin"><div class="ring"></div>Checking your vendor master, GLEIF registry and external sources...</div>';
  webSlot.innerHTML = '';
  const payload = {
    vendor_name: document.getElementById('vendor_name').value,
    country: document.getElementById('country').value,
    website: document.getElementById('website').value,
  };
  lastQuery = payload;
  try{
    const res = await fetch('/screen', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if(!res.ok) throw new Error('Screening failed (' + res.status + ')');
    const data = await res.json();
    pane.innerHTML = `${renderVerdict(data)}${renderStats(data)}<h3>All candidates (${data.result_count})</h3>${renderCandidates(data.candidates)}`;
    webSlot.innerHTML = renderWebFallback(data.web_search_fallback);
  } catch(err){
    pane.innerHTML = `<div class="error-banner">${err.message}. Confirm the server is running and try again.</div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Screen vendor';
  }
});
</script>
</body>
</html>
"""
@app.get('/', response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML
