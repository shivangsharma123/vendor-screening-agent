"""
GLEIF LEI registry client (the external open-data source).

Free, no API key. Provides legal name, country, LEI code, entity/registration
status, former/trading names, and - crucially - direct/ultimate parent links
(how we catch subsidiaries like EdgeVerve -> Infosys).

All responses are cached in-memory and parent lookups run concurrently, which
takes a screen from ~12s down to ~2s (and near-instant on repeat).
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

from .config import GLEIF_BASE, GLEIF_TIMEOUT, GLEIF_CACHE_TTL, GLEIF_MAX_WORKERS
from .text_utils import gleif_country_code

_SESSION = requests.Session()
_POOL = ThreadPoolExecutor(max_workers=GLEIF_MAX_WORKERS)
_CACHE: Dict[Any, Any] = {}
_HEADERS = {"Accept": "application/vnd.api+json"}


def _request(path: str, params: Optional[dict] = None, retry_on_429: bool = True):
    """
    Shared GLEIF GET helper.
      - 200 -> parsed JSON; anything else (incl. the very common 404) -> None.
      - 429 -> one short retry, then give up gracefully.
      - Network error -> None (a GLEIF hiccup never crashes a screen).
    Successful and empty results are cached for the session.
    """
    cache_key = (path, tuple(sorted((params or {}).items())))
    cached = _CACHE.get(cache_key)
    if cached is not None and (time.time() - cached[0]) < GLEIF_CACHE_TTL:
        return cached[1]

    result = None
    try:
        resp = _SESSION.get(f"{GLEIF_BASE}{path}", params=params or {},
                            timeout=GLEIF_TIMEOUT, headers=_HEADERS)
        if resp.status_code == 429 and retry_on_429:
            time.sleep(0.6)
            resp = _SESSION.get(f"{GLEIF_BASE}{path}", params=params or {},
                                timeout=GLEIF_TIMEOUT, headers=_HEADERS)
        result = resp.json() if resp.status_code == 200 else None
    except requests.RequestException:
        result = None

    _CACHE[cache_key] = (time.time(), result)
    return result


def _to_dict(rec) -> Optional[dict]:
    """Flatten GLEIF's JSON:API envelope into the fields we use."""
    if not rec:
        return None
    attrs = rec.get("attributes", {}) or {}
    entity = attrs.get("entity", {}) or {}
    addr = entity.get("legalAddress", {}) or {}
    reg = attrs.get("registration", {}) or {}
    other_names = [
        (n or {}).get("name", "")
        for n in (entity.get("otherNames") or [])
        if (n or {}).get("name")
    ]
    address_full = ", ".join(
        [l for l in (addr.get("addressLines") or []) if l]
        + ([addr.get("postalCode")] if addr.get("postalCode") else [])
    )
    return {
        "lei": rec.get("id", ""),
        "legal_name": (entity.get("legalName", {}) or {}).get("name", ""),
        "other_names": other_names,       # trading / former names / translations
        "country": addr.get("country", ""),
        "city": addr.get("city", ""),
        "status": entity.get("status", ""),
        "registration_status": reg.get("status", ""),
        # richer detail for the card
        "registration_number": entity.get("registeredAs", "") or "",
        "address_full": address_full,
        "registered_since": (reg.get("initialRegistrationDate") or "")[:4],
        "last_verified": (reg.get("lastUpdateDate") or "")[:10],
        "next_renewal": (reg.get("nextRenewalDate") or "")[:10],
    }


def search_by_name(name: str, country: str = "", limit: int = 5) -> List[dict]:
    if not str(name).strip():
        return []
    params = {"filter[entity.legalName]": name, "page[size]": limit}
    iso2 = gleif_country_code(country)
    if iso2:
        params["filter[entity.legalAddress.country]"] = iso2
    data = _request("/lei-records", params)
    if not data:
        return []
    return [d for d in (_to_dict(r) for r in data.get("data", [])) if d]


def search_by_isin(isin: str) -> List[dict]:
    if not str(isin).strip():
        return []
    data = _request("/lei-records", {"filter[isin]": isin.strip().upper(), "page[size]": 5})
    if not data:
        return []
    return [d for d in (_to_dict(r) for r in data.get("data", [])) if d]


def by_lei(lei: str) -> Optional[dict]:
    if not str(lei).strip():
        return None
    data = _request(f"/lei-records/{lei.strip().upper()}")
    return _to_dict(data.get("data")) if data else None


def parent(lei: str, kind: str = "direct") -> Optional[dict]:
    """kind = 'direct' or 'ultimate'. A 404 just means 'no parent on file'."""
    data = _request(f"/lei-records/{lei}/{kind}-parent")
    return _to_dict(data.get("data")) if data else None


def prefetch_parents(hits: List[dict]) -> Dict[Any, Optional[dict]]:
    """
    Fetch every hit's direct + ultimate parent CONCURRENTLY.
    Returns {(lei, kind): parent_dict_or_None}. This is the main latency win.
    """
    parent_map: Dict[Any, Optional[dict]] = {}
    if not hits:
        return parent_map
    futures = {
        _POOL.submit(parent, h["lei"], kind): (h["lei"], kind)
        for h in hits for kind in ("direct", "ultimate")
    }
    for fut, key in futures.items():
        try:
            parent_map[key] = fut.result()
        except Exception:
            parent_map[key] = None
    return parent_map
